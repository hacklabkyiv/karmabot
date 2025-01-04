from collections import Counter
from datetime import datetime

from sqlalchemy import Float, cast

from .config import KarmabotConfig
from .logging import logger
from .orm import Karma, Voting, create_session_maker
from .transport import Transport
from .words import Color, Format


class KarmaManager:
    def __init__(self, config: KarmabotConfig, transport: Transport, fmt: Format) -> None:
        self._initial_value = config.karma.initial_value
        self._vote_timeout = config.karma.vote_timeout
        self._upvote_emoji = config.karma.upvote_emoji
        self._downvote_emoji = config.karma.downvote_emoji
        self._keep_history = config.karma.keep_history

        self._digest_channel = config.digest.channel

        self._transport = transport
        self._format = fmt
        self._session_maker = create_session_maker(config.db)

    def get(self, user_id: str, channel: str) -> None:
        with self._session_maker() as session:
            karma = session.query(Karma).filter_by(user_id=user_id).first()
            if karma:
                value = karma.karma
            else:
                value = self._initial_value

        username = self._transport.lookup_username(user_id)
        self._transport.post(channel, self._format.report_karma(username, value))

    def set(self, user_id: str, karma: int, channel: str) -> None:
        with self._session_maker() as session:
            karma_change = session.query(Karma).filter_by(user_id=user_id).first()
            if karma_change:
                karma_change.karma = karma
            else:
                session.add(Karma(user_id=user_id, karma=karma))
            session.commit()

        username = self._transport.lookup_username(user_id)
        self._transport.post(channel, self._format.report_karma(username, karma))

    def digest(self) -> None:
        result = ["*username* => *karma*"]
        with self._session_maker() as session:
            all_karma = (
                session.query(Karma).filter(Karma.karma != 0).order_by(Karma.karma.desc()).all()
            )
            for r in all_karma:
                username = self._transport.lookup_username(r.user_id)
                item = f"_{username}_ => *{r.karma}*"
                result.append(item)

        # TODO: add translations
        if len(result) == 1:
            message = "Seems like nothing to show. All the karma is zero"
        else:
            message = "\n".join(result)
        self._transport.post(self._digest_channel, self._format.message(Color.INFO, message))

    def pending(self, channel: str) -> None:
        result = ["*initiator* | *receiver* | *channel* | *karma* | *expired*"]
        with self._session_maker() as session:
            for r in session.query(Voting).all():
                dt = self._vote_timeout
                time_left = datetime.fromtimestamp(float(r.message_ts)) + dt
                item = f"{self._transport.lookup_username(r.initiator_id)} | {self._transport.lookup_username(r.target_id)} | {self._transport.lookup_channel_name(r.channel)} | {r.karma} | {time_left.isoformat()}"
                result.append(item)

        # TODO: add translations
        if len(result) == 1:
            message = "Seems like nothing to show"
        else:
            message = "\n".join(result)

        self._transport.post(channel, self._format.message(Color.INFO, message))
        return None

    def create(
        self,
        *,
        initiator_id: str,
        target_id: str,
        channel: str,
        text: str,
        ts: str,
        bot_message_ts: str,
        karma: int,
    ) -> None:
        # Check for an already existing voting
        with self._session_maker() as session:
            instance = session.query(Voting).filter_by(uuid=(ts, channel)).first()
            if instance:
                logger.fatal("Voting already exists: ts=%s, channel=%s", ts, channel)
                return

            session.add(
                Voting(
                    created=datetime.now(),
                    initiator_id=initiator_id,
                    target_id=target_id,
                    channel=channel,
                    message_ts=ts,
                    bot_message_ts=bot_message_ts,
                    message_text=text,
                    karma=karma,
                )
            )
            session.commit()

    def close_expired_votings(self) -> None:
        now = datetime.now().timestamp()
        with self._session_maker() as session:
            expired = session.query(Voting).filter(
                cast(Voting.bot_message_ts, Float) + self._vote_timeout < now
            )

            for e in expired.all():
                logger.info("Expired voting: %s", e)

                reactions = self._transport.reactions_get(
                    channel=e.channel,
                    initial_msg_ts=e.message_ts,
                    bot_msg_ts=e.bot_message_ts,
                )
                if reactions is None:
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
        logger.info("Reactions: %s", reactions)
        upvotes = [reactions[r] for r in self._upvote_emoji if r in reactions]
        downvotes = [reactions[r] for r in self._downvote_emoji if r in reactions]
        logger.info("Upvotes: %s\nDownvotes: %s", upvotes, downvotes)
        return sum(upvotes) - sum(downvotes) > 0
