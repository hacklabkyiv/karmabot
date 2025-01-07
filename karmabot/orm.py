import datetime

import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


class OrmBase(DeclarativeBase):
    pass


def create_session_maker(db_uri: str):
    engine = sa.create_engine(db_uri)
    OrmBase.metadata.create_all(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    return Session


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
        sa.DateTime, nullable=False, default=sa.func.now()
    )
    closed: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    initiator_id: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    target_id: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    channel: Mapped[str] = mapped_column(sa.String(256), nullable=False)
    message_ts: Mapped[str] = mapped_column(sa.String, nullable=False)
    bot_message_ts: Mapped[str] = mapped_column(sa.String, nullable=False)
    message_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    karma: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    @hybrid_property
    def uuid(self):
        return self.message_ts, self.channel
