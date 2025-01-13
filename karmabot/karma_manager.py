from collections import Counter
from datetime import datetime

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
            karma = session.execute(stmt).first()
            if karma:
                value = karma.karma
            else:
                value = self._initial_value
        return value

    def set(self, user_id: str, karma: int) -> None:
        stmt = sa.select(Karma).filter_by(user_id=user_id).limit(1)
        with self._session_maker() as session:
            karma_change = session.execute(stmt).first()
            if karma_change:
                karma_change.karma = karma
            else:
                session.add(Karma(user_id=user_id, karma=karma))
            session.commit()

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
        # Check for an already existing voting
        with self._session_maker() as session:
            stmt = sa.select(Voting).filter_by(uuid=(ts, channel))
            instance = session.execute(stmt).first()
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

    def get_expired_votings(self) -> list[Voting]:
        now = datetime.now().timestamp()
        stmt = sa.select(Voting).filter(
            sa.cast(Voting.bot_message_ts, sa.Float) + self._vote_timeout < now
        )
        with self._session_maker() as session:
            return session.execute(stmt).scalars().all()

    def remove_old_votings(self) -> None:
        now = datetime.now()
        stmt = sa.select(Voting).filter(
            Voting.closed == True and (now - Voting.created) >= self._keep_history
        )
        with self._session_maker() as session:
            old = session.execute(stmt).scalars().all()
            for o in old:
                session.delete(o)
            session.commit()

    def close_voting(self, voting: Voting, reactions: Counter[str] | None = None) -> bool:
        success = False
        with self._session_maker() as session:
            if reactions is None:
                logger.error("Failed to get messages for: %s", voting)
                session.delete(voting)
            elif self._determine_success(reactions):
                stmt = sa.select(Karma).filter_by(user_id=voting.target_id)
                karma = session.execute(stmt).first()
                if karma:
                    karma.karma += voting.karma
                else:
                    new_record = Karma(
                        user_id=voting.target_id, karma=self._initial_value + voting.karma
                    )
                    session.add(new_record)
                success = True
                stmt = sa.update(Voting).where(Voting.id == voting.id).values(closed=True)
            session.execute(stmt)
            session.commit()
        return success

    def _determine_success(self, reactions: Counter[str]) -> bool:
        logger.info("Reactions: %s", reactions)
        upvotes = [reactions[r] for r in self._upvote_emoji if r in reactions]
        downvotes = [reactions[r] for r in self._downvote_emoji if r in reactions]
        logger.info("Upvotes: %s\nDownvotes: %s", upvotes, downvotes)
        return sum(upvotes) - sum(downvotes) > 0
