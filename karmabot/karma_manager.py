from collections import Counter
from datetime import datetime

from sqlalchemy import Float, cast

from .config import KarmabotConfig
from .logging import logger
from .orm import Karma, Voting, create_session_maker
from .parse import Parse
from .transport import Transport
from .words import Color, Format


class KarmaManager:
    def __init__(self, config: KarmabotConfig, transport: Transport, fmt: Format) -> None:
        self._initial_value = config.karma.initial_value
        self._max_diff = config.karma.max_diff
        self._self_karma = config.karma.self_karma
        self._vote_timeout = config.karma.vote_timeout
        self._upvote_emoji = config.karma.upvote_emoji
        self._downvote_emoji = config.karma.downvote_emoji
        self._keep_history = config.karma.keep_history

        self._digest_channel = config.digest.channel

        self._transport = transport
        self._format = fmt
        self._session_maker = create_session_maker(config.db)

    def get(self, user_id: str, channel: str) -> bool:
        with self._session_maker() as session:
            karma = session.query(Karma).filter_by(user_id=user_id).first()
            if karma:
                value = karma.karma
            else:
                value = self._initial_value
                session.add(Karma(user_id=user_id, karma=value))
                session.commit()

        username = self._transport.lookup_username(user_id)
        self._transport.post(channel, self._format.report_karma(username, value))
        return True

    def set(self, user_id: str, karma: int, channel: str) -> bool:
        with self._session_maker() as session:
            karma_change = session.query(Karma).filter_by(user_id=user_id).first()
            if karma_change:
                karma_change.karma = karma
            else:
                session.add(Karma(user_id=user_id, karma=karma))
            session.commit()

        username = self._transport.lookup_username(user_id)
        self._transport.post(channel, self._format.report_karma(username, karma))
        return True

    def digest(self) -> bool:
        result = ["*username* => *karma*"]
        with self._session_maker() as session:
            for r in (
                session.query(Karma).filter(Karma.karma != 0).order_by(Karma.karma.desc()).all()
            ):
                item = f"_{self._transport.lookup_username(r.user_id)}_ => *{r.karma}*"
                result.append(item)

        # TODO: add translations
        if len(result) == 1:
            message = "Seems like nothing to show. All the karma is zero"
        else:
            message = "\n".join(result)

        self._transport.post(self._digest_channel, self._format.message(Color.INFO, message))
        return True

    def pending(self, channel: str) -> bool:
        result = ["*initiator* | *receiver* | *channel* | *karma* | *expired*"]
        with self._session_maker() as session:
            for r in session.query(Voting).all():
                dt = self._vote_timeout
                time_left = datetime.fromtimestamp(float(r.message_ts)) + dt
                item = f"{self._transport.lookup_username(r.initiator_id)} | {self._transport.lookup_username(r.target_id)} | {self._transport.lookup_channel_name(r.channel)} | {r.karma} | {time_left.isoformat()}"
                result.append(item)

        if len(result) == 1:
            message = "Seems like nothing to show"
        else:
            message = "\n".join(result)

        self._transport.post(channel, self._format.message(Color.INFO, message))
        return True

    def create(self, initiator_id: str, channel: str, text: str, ts: str) -> None:
        # Check for an already existing voting
        with self._session_maker() as session:
            instance = session.query(Voting).filter_by(uuid=(ts, channel)).first()
            if instance:
                logger.fatal("Voting already exists: ts=%s, channel=%s", ts, channel)
                return

            # Report an error if a request has not been parsed
            result = Parse.karma_change(text)
            if not result:
                self._transport.post(channel, self._format.parsing_error(), ts=ts)
                return

            bot_id, user_id, points = result
            error = self._karma_change_sanity_check(initiator_id, user_id, bot_id, points)
            if error:
                self._transport.post(channel, error, ts=ts)
                return

            username = self._transport.lookup_username(user_id)
            msg = self._format.new_voting(username, points)

            response = self._transport.post(channel, msg, ts=ts)

            session.add(
                Voting(
                    created=datetime.now(),
                    initiator_id=initiator_id,
                    target_id=user_id,
                    channel=channel,
                    message_ts=ts,
                    bot_message_ts=response["ts"],
                    message_text=text,
                    karma=points,
                )
            )
            session.commit()

    def close_expired_votings(self, now):
        result = True
        with self._session_maker() as session:
            expired = session.query(Voting).filter(
                cast(Voting.bot_message_ts, Float) + self._vote_timeout < now
            )

            for e in expired.all():
                logger.debug("Expired voting: %s", e)

                reactions = self._transport.reactions_get(
                    e.channel, e.message_ts, e.bot_message_ts
                )
                if reactions is None:
                    result = False
                    logger.error("Failed to get messages for: %s", e)
                    session.delete(e)
                    continue

                success = self._determine_success(reactions)
                if success:
                    karma = session.query(Karma).filter_by(user_id=e.target_id).first()
                    if karma:
                        karma.karma += e.karma
                    else:
                        session.add(
                            Karma(user_id=e.target_id, karma=self._initial_value + e.karma)
                        )

                self._close(e, success)

            session.commit()
        return result

    def remove_old_votings(self) -> None:
        now = datetime.now()
        with self._session_maker() as session:
            old = session.query(Voting).filter(
                Voting.closed == False and (now - Voting.created) >= self._keep_history
            )

            for o in old.all():
                session.delete(o)
            session.commit()

    def _close(self, karma_change, success) -> None:
        karma_change.closed = True
        username = self._transport.lookup_username(karma_change.target_id)
        result = self._format.voting_result(username, karma_change.karma, success)
        self._transport.update(karma_change.channel, result, karma_change.bot_message_ts)

    def _determine_success(self, reactions: Counter[str]) -> bool:
        logger.debug("Reactions: %s", reactions)
        upvotes = [reactions[r] for r in self._upvote_emoji if r in reactions]
        downvotes = [reactions[r] for r in self._downvote_emoji if r in reactions]
        logger.debug("Upvotes: %s\nDownvotes: %s", upvotes, downvotes)
        return sum(upvotes) - sum(downvotes) > 0

    def _karma_change_sanity_check(
        self, initiator_id: str, user_id: str, bot_id: str, karma: int
    ) -> dict | None:
        if not self._self_karma and initiator_id == user_id:
            return self._format.strange_error()
        if user_id == bot_id:
            return self._format.robo_error()
        if abs(karma) > self._max_diff:
            return self._format.max_diff_error(self._max_diff)
        return None
