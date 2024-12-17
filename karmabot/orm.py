from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class OrmBase(DeclarativeBase):
    pass


def create_session_maker(db_uri: str):
    engine = create_engine(db_uri)
    OrmBase.metadata.create_all(engine, checkfirst=True)
    Session = sessionmaker(bind=engine)
    return Session


class Karma(OrmBase):
    __tablename__ = "karmabot_karma"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(256), unique=True, nullable=False)
    karma = Column(Integer, nullable=False)

    def __repr__(self):
        return f"<Karma(user_id={self.user_id}, karma={self.karma})>"


class Voting(OrmBase):
    __tablename__ = "karmabot_voting"

    id = Column(Integer, primary_key=True)
    created = Column(DateTime, nullable=False, default=datetime.now())
    closed = Column(Boolean, nullable=False, default=False)
    initiator_id = Column(String(256), nullable=False)
    target_id = Column(String(256), nullable=False)
    channel = Column(String(256), nullable=False)
    message_ts = Column(String, nullable=False)
    bot_message_ts = Column(String, nullable=False)
    message_text = Column(Text, nullable=False)
    karma = Column(Integer, nullable=False)

    @hybrid_property
    def uuid(self):
        return self.message_ts, self.channel
