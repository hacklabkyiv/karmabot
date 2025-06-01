import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class OrmBase(DeclarativeBase):
    pass


def create_session_maker(db_uri: str):
    engine = sa.create_engine(db_uri, connect_args={"options": "-c timezone=utc"})
    OrmBase.metadata.create_all(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    return Session


class TimezoneAwereTimestamp(sa.TypeDecorator):
    "Returns a timezone aware datetime objecto from UTC timestamp."

    impl = sa.TIMESTAMP
    cache_ok = True

    def process_bind_param(self, value: Any | None, dialect: sa.Dialect):
        if isinstance(value, datetime.datetime):
            return value.astimezone(datetime.timezone.utc)
        return value

    def process_result_value(self, value: Any | None, dialect: sa.Dialect):
        if isinstance(value, datetime.datetime):
            return value.replace(tzinfo=datetime.timezone.utc)
        return value


class Karma(OrmBase):
    __tablename__ = "karmabot_karma"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    user_id: Mapped[str] = mapped_column(sa.String(256), unique=True, nullable=False)
    karma: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    def __repr__(self):
        return f"<Karma(user_id={self.user_id}, karma={self.karma})>"


class Voting(OrmBase):
    __tablename__ = "karmabot_voting"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True)
    created: Mapped[datetime.datetime] = mapped_column(
        TimezoneAwereTimestamp,
        nullable=False,
        default=lambda: datetime.datetime.now(tz=datetime.timezone.utc),
    )
    closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    initiator_id: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    target_id: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    message_ts: Mapped[datetime.datetime] = mapped_column(TimezoneAwereTimestamp, nullable=False)
    bot_message_ts: Mapped[datetime.datetime] = mapped_column(
        TimezoneAwereTimestamp, nullable=False
    )
    message_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    karma: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    @hybrid_property
    def uuid(self) -> tuple[datetime.datetime, str]:
        return self.message_ts, self.channel
