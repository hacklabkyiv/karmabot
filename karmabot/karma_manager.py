from collections import Counter
from datetime import datetime, timezone

import sqlalchemy as sa

from .config import KarmabotConfig
from .logging import logger
from .orm import Karma, Voting, create_session_maker


class KarmaManager:
    def __init__(self, config: KarmabotConfig) -> None:
        self._initial_value = config.karma.initial_value
        self._vote_timeout = config.karma.vote_timeout
        self._upvote_emoji = config.karma.upvote_emoji
        self._downvote_emoji = config.karma.downvote_emoji
        self._keep_history = config.karma.keep_history
        self._session_maker = create_session_maker(config.db)

    def get(self, user_id: str) -> int:
        stmt = sa.select(Karma).filter_by(user_id=user_id).limit(1)
        with self._session_maker() as session:
            karma = session.execute(stmt).scalar_one_or_none()
            if karma is not None:
                value = karma.karma
            else:
                value = self._initial_value
        return value

    def set(self, user_id: str, karma: int) -> None:
        stmt = sa.select(Karma).filter_by(user_id=user_id).limit(1)
        with self._session_maker.begin() as session:
            karma_change = session.execute(stmt).scalar_one_or_none()
            if karma_change is not None:
                karma_change.karma = karma
            else:
                session.add(Karma(user_id=user_id, karma=karma))

    def digest(self) -> list[Karma]:
        stmt = sa.select(Karma).filter(Karma.karma != 0).order_by(Karma.karma.desc())
        with self._session_maker() as session:
            return session.execute(stmt).scalars().all()

    def pending(self) -> list[Voting]:
        stmt = sa.select(Voting).filter(Voting.closed == False)
        with self._session_maker() as session:
            return session.execute(stmt).scalars().all()

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
        ts_dt = datetime.fromtimestamp(float(ts), tz=timezone.utc)
        bot_message_ts_dt = datetime.fromtimestamp(float(bot_message_ts), tz=timezone.utc)
        with self._session_maker.begin() as session:
            # Check for an already existing voting
            stmt = sa.select(Voting).filter_by(uuid=(ts_dt, channel))
            instance = session.execute(stmt).scalar_one_or_none()
            if instance is not None:
                logger.fatal("Voting already exists: ts=%s, channel=%s", ts, channel)
                return

            session.add(
                Voting(
                    initiator_id=initiator_id,
                    target_id=target_id,
                    channel=channel,
                    message_ts=ts_dt,
                    bot_message_ts=bot_message_ts_dt,
                    message_text=text,
                    karma=karma,
                )
            )

    def get_expired_votings(self) -> list[Voting]:
        now = datetime.now(tz=timezone.utc)
        filter_ = sa.and_(
            Voting.closed == False,
            Voting.bot_message_ts <= now - self._vote_timeout,
        )
        stmt = sa.select(Voting).filter(filter_)
        with self._session_maker() as session:
            return session.execute(stmt).scalars().all()

    def remove_old_votings(self) -> None:
        now = datetime.now(tz=timezone.utc)
        filter_ = sa.and_(Voting.closed == True, Voting.created <= now - self._keep_history)
        stmt = sa.select(Voting).filter(filter_)
        with self._session_maker.begin() as session:
            old = session.execute(stmt).scalars().all()
            for o in old:
                session.delete(o)

    def close_voting(self, voting: Voting, reactions: Counter[str] | None = None) -> bool:
        success = False
        with self._session_maker.begin() as session:
            if reactions is None:
                logger.error("Failed to get messages for: %s", voting)
                session.delete(voting)
            elif self._determine_success(reactions):
                stmt = sa.select(Karma).filter_by(user_id=voting.target_id)
                karma = session.execute(stmt).scalar_one_or_none()
                if karma is not None:
                    karma.karma += voting.karma
                else:
                    new_record = Karma(
                        user_id=voting.target_id, karma=self._initial_value + voting.karma
                    )
                    session.add(new_record)
                success = True
                update_stmt = sa.update(Voting).where(Voting.id == voting.id).values(closed=True)
                session.execute(update_stmt)
        return success

    def _determine_success(self, reactions: Counter[str]) -> bool:
        logger.info("Reactions: %s", reactions)
        upvotes = [reactions[r] for r in self._upvote_emoji if r in reactions]
        downvotes = [reactions[r] for r in self._downvote_emoji if r in reactions]
        logger.info("Upvotes: %s\nDownvotes: %s", upvotes, downvotes)
        return sum(upvotes) - sum(downvotes) > 0
