from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Float, Text
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy import cast


ORM_BASE = declarative_base()


def get_scoped_session(db_name):
    engine = create_engine(db_name)
    ORM_BASE.metadata.create_all(engine)
    ORM_BASE.metadata.bind = engine
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    return Session()


class Karma(ORM_BASE):
    __tablename__ = 'karma'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(256), unique=True, nullable=False)
    karma = Column(Integer, nullable=False)

    def __repr__(self):
        return f'<Karma(user_id={self.user_id}, karma={self.karma})>'


class Voting(ORM_BASE):
    __tablename__ = 'pending'

    id = Column(Integer, primary_key=True)
    initial_msg_ts = Column(String, nullable=False)
    bot_msg_ts = Column(String, nullable=False)
    channel = Column(String(256), nullable=False)
    user_id = Column(String(256), nullable=False)
    initiator_id = Column(String(256), nullable=False)
    karma = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)

    @hybrid_property
    def uuid(self):
        return self.initial_msg_ts, self.channel

    def __repr__(self):
        return f'<Voting(initial_msg_ts={self.initial_msg_ts}, bot_msg_ts={self.bot_msg_ts}, channel={self.channel}, \
used_id={self.user_id}, initiator_id={self.initiator_id}, karma={self.karma}, text={self.text})>'
