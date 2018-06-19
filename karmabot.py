import logging
import time
from collections import Counter
from orm import get_scoped_session, Karma, Voting
from transport import Transport
from parse import Parse
from config import Config
import words


class Bot:
    def __init__(self, cfg):
        self._config = cfg
        self._session = get_scoped_session(config.DB_URI)
        self._transport = Transport(config)

    def listen(self):
        required_fields = ('type', 'client_msg_id', 'channel')

        while True:
            events = self._transport.read()
            for event in events:
                if not all(r in event for r in required_fields):
                    logging.debug(f'Skipping message: {event}')
                    continue

                channel = event['channel']
                if channel.startswith('D'):
                    r = self._handle_cmd(event)
                else:
                    r = self._handle_message(event)

                if not r:
                    logging.debug(f'Unhandled event: {event}')

            self._cmd_close_expired_votes()

            if not events:
                time.sleep(0.5)

    def _handle_cmd(self, event):
        logging.debug(f'Resolving a command. Text: {event}')

        initiator_id = event['user']
        channel = event['channel']
        text = event['text']

        if text.startswith('set'):
            if not self._check_admin_permissions(initiator_id):
                return True

            if not self._cmd_set_user_karma(text, channel):
                logging.fatal(f'Could not handle SET command: {text}')
        elif text.startswith('get'):
            if not self._cmd_get_user_karma(text, channel):
                logging.fatal(f'Could not handle GET command: {text}')
        else:
            self._cmd_help(channel)

        return True

    def _handle_message(self, event):
        logging.debug(f'Processing message: {event}')

        event_type = event['type']
        if event_type == 'team_join':
            user_id = event['user']['id']
            self._transport.send_hello(user_id=user_id)
            logging.info(f'Team joined by user_id={user_id}')
            return True
        elif event_type == 'channel_joined':
            channel = event['channel']
            self._transport.send_hello(channel=channel)
            logging.info(f'Bot joined a channel={channel}')
            return True
        elif event_type == 'message':
            initiator_id = event['user']
            channel = event['channel']
            text = event['text']
            ts = float(event['ts'])

            return self._cmd_init_karma_voting(initiator_id=initiator_id,
                                               channel=channel,
                                               text=text,
                                               ts=ts)

        return False

    def _cmd_init_karma_voting(self, initiator_id, channel, text, ts):
        user_id = Parse.user_mention(text)
        if not user_id or self._transport.lookup_username(user_id) != 'karmabot':
            return False

        result, error = Parse.karma_change(text)
        if error:
            self._transport.send_error(error, channel, ts=ts)
            return False

        if not result:
            return False

        bot_id, user_id, points = result
        check_msg = Parse.karma_change_sanity_check(initiator_id,
                                                    user_id,
                                                    bot_id,
                                                    self._config.SELF_KARMA,
                                                    points,
                                                    self._config.MAX_SHOT)
        if check_msg:
            self._transport.send_error(check_msg, channel, ts=ts)
            return False

        instance = self._session.query(Voting).filter_by(uuid=(ts, channel)).first()
        if instance:
            logging.fatal(f'Voting already exists: ts={ts}, channel={channel}')
            return False

        karma = Voting(initial_msg_ts=ts,
                       bot_msg_ts=ts,
                       channel=channel,
                       user_id=user_id,
                       initiator_id=initiator_id,
                       karma=points,
                       text=text)

        result = self._transport.create_voting(karma)
        karma.bot_msg_ts = float(result['ts'])

        self._session.add(karma)
        self._session.commit()
        return True

    def _cmd_close_expired_votes(self):
        result = True
        now = time.time()
        expired = self._session.query(Voting)\
                               .filter(Voting.bot_msg_ts + self._config.VOTE_TIMEOUT < now).all()
        for e in expired:
            logging.debug(f'Expired voting: {e}')

            r = self._count_reactions(e.channel, e.initial_msg_ts, e.bot_msg_ts)
            if not r:
                result = False
                logging.error(f'Failed to get messages for: {e}')
                self._session.delete(e)
                continue

            success = self._determine_success(r)
            if success:
                karma = self._session.query(Karma).filter_by(user_id=e.user_id).first()
                if karma:
                    karma.karma += e.karma
                else:
                    self._session.add(Karma(user_id=e.user_id, karma=self._config.INITIAL_USER_KARMA + e.karma))

            self._transport.close_voting(e, success)
            self._session.delete(e)

        self._session.commit()
        return result

    def _cmd_get_user_karma(self, text, channel):
        user_id, error = Parse.cmd_get(text)
        if error:
            self._transport.send_error(error, channel)
            return False

        karma = self._session.query(Karma).filter_by(user_id=user_id).first()
        if karma:
            value = karma.karma
        else:
            value = self._config.INITIAL_USER_KARMA

        self._transport.report_karma(user_id, value, channel)
        return True

    def _cmd_set_user_karma(self, text, channel):
        (user_id, karma), error = Parse.cmd_set(text)
        if error:
            self._transport.send_error(error, channel)
            return False

        karma_change = self._session.query(Karma).filter_by(user_id=user_id).first()
        if karma_change:
            karma_change.karma = karma
        else:
            self._session.add(Karma(user_id=user_id, karma=karma))

        self._session.commit()
        return True

    def _cmd_help(self, channel):
        self._transport.send_help(channel)

    def _cmd_config(self):
        pass

    def _count_reactions(self, channel, initial_msg_ts, bot_msg_ts):
        initial_msg, bot_msg = self._transport.get_reactions(channel,
                                                             initial_msg_ts,
                                                             bot_msg_ts)

        if not (initial_msg and bot_msg):
            logging.fatal(f'Failed to get original messages for: channel={channel}, initial_msg_ts={initial_msg_ts}, '
                          f'bot_msg_ts={bot_msg_ts}')
            return None

        r = Counter()
        if 'reactions' in initial_msg:
            r += Parse.reactions(initial_msg['reactions'])
        if 'reactions' in bot_msg:
            r += Parse.reactions(bot_msg['reactions'])
        return r

    def _determine_success(self, reactions):
        logging.debug(f'Reactions: {reactions}')
        upvotes = [reactions[r] for r in self._config.UPVOTE_EMOJI if r in reactions]
        downvotes = [reactions[r] for r in self._config.DOWNVOTE_EMOJI if r in reactions]
        logging.debug(f'Upvotes: {upvotes}')
        logging.debug(f'Downvotes: {downvotes}')
        return sum(upvotes) - sum(downvotes) > 0

    def _check_admin_permissions(self, initiator_id):
        return self._transport.lookup_username(initiator_id) in self._config.ADMINS


if __name__ == '__main__':
    logging.basicConfig(format='[%(name)s] - [%(levelname)s] %(asctime)s --- %(message)s', level=logging.DEBUG)

    config = Config()
    words.init(config.BOT_LANG)
    logging.debug(vars(config))
    bot = Bot(config)
    bot.listen()
