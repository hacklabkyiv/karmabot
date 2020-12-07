from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.hybrid import hybrid_property


ORM_BASE = declarative_base()


def make_db_uri(cfg):
    db_type = cfg['type']
    if db_type == 'sqlite':
        return 'sqlite:///' + cfg['name']

    user = cfg.get('user', '')
    password = cfg.get('password', '') if user else ''
    auth = f'{user}:{password}@' if user and password else ''

    host = cfg.get('host', '127.0.0.1')
    port = cfg.get('port', '5432')

    db_name = cfg['name']
    return f'db_type://{auth}{host}:{port}/{db_name}'


def get_scoped_session(db_config):
    db_uri = make_db_uri(db_config)
    engine = create_engine(db_uri)
    ORM_BASE.metadata.create_all(engine)
    ORM_BASE.metadata.bind = engine
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    return Session()


class Karma(ORM_BASE):
    __tablename__ = 'karmabot_karma'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(256), unique=True, nullable=False)
    karma = Column(Integer, nullable=False)

    def __repr__(self):
        return f'<Karma(user_id={self.user_id}, karma={self.karma})>'


class Voting(ORM_BASE):
    __tablename__ = 'karmabot_voting'

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
