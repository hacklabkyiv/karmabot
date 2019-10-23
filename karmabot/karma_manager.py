import logging
import time
from datetime import datetime
from datetime import timedelta
from .orm import get_scoped_session, Voting, Karma, cast, Float
from .parse import Parse
from .words import Color


# FIXME: check every where for succeded POST
class KarmaManager:
    __slots__ = [
        '_initial_value', '_max_shot', '_self_karma', '_vote_timeout',
        '_upvote_emoji', '_downvote_emoji',
        '_transport', '_format', '_backup', '_session', '_logger'
    ]

    def __init__(self, karma_config, db_config, transport, fmt, backup_provider):
        self._initial_value = karma_config['initial_value']
        self._max_shot = karma_config['max_shot']
        self._self_karma = karma_config['self_karma']
        self._vote_timeout = karma_config['vote_timeout']
        self._upvote_emoji = karma_config['upvote_emoji']
        self._downvote_emoji = karma_config['downvote_emoji']

        self._transport = transport
        self._format = fmt
        self._backup = backup_provider
        self._session = get_scoped_session(db_config)
        self._logger = logging.getLogger('KarmaManager')

    def get(self, user_id, channel):
        karma = self._session.query(Karma).filter_by(user_id=user_id).first()
        if karma:
            value = karma.karma
        else:
            value = self._initial_value
            self._session.add(Karma(user_id=user_id, karma=value))
            self._session.commit()

        username = self._transport.lookup_username(user_id)
        self._transport.post(channel, self._format.report_karma(username, value))
        return True

    def set(self, user_id, karma, channel):
        karma_change = self._session.query(Karma).filter_by(user_id=user_id).first()
        if karma_change:
            karma_change.karma = karma
        else:
            self._session.add(Karma(user_id=user_id, karma=karma))

        self._session.commit()

        username = self._transport.lookup_username(user_id)
        self._transport.post(channel, self._format.report_karma(username, karma))
        return True

    def digest(self, channel):
        result = ['*username* => *karma*']
        for r in self._session.query(Karma).filter(Karma.karma != 0).order_by(Karma.karma.desc()).all():
            item = '_{}_ => *{}*'.format(self._transport.lookup_username(r.user_id), r.karma)
            result.append(item)

        # TODO: add translations
        if len(result) == 1:
            result = 'Seems like nothing to show. All the karma is zero'
        else:
            result.append('The rest are full ZERO')
            result = '\n'.join(result)

        self._transport.post(channel, self._format.message(Color.INFO, result))
        return True

    def pending(self, channel):
        result = ['*initiator* | *receiver* | *channel* | *karma* | *expired*']
        for r in self._session.query(Voting).all():
            dt = timedelta(seconds=self._vote_timeout)
            time_left = datetime.fromtimestamp(float(r.initial_msg_ts)) + dt
            item = '{} | {} | {} | {} | {}'.format(
                self._transport.lookup_username(r.initiator_id),
                self._transport.lookup_username(r.user_id),
                self._transport.lookup_channel_name(r.channel),
                r.karma,
                time_left.isoformat())
            result.append(item)

        if len(result) == 1:
            result = 'Seems like nothing to show'
        else:
            result = '\n'.join(result)

        self._transport.post(channel, self._format.message(Color.INFO, result))
        return True

    def create(self, initiator_id, channel, text, ts):
        # Check for an already existing voting
        instance = self._session.query(Voting).filter_by(uuid=(ts, channel)).first()
        if instance:
            self._logger.fatal('Voting already exists: ts=%s, channel=%s',
                               ts, channel)
            return False

        # Report an error if a request has not been parsed
        result = Parse.karma_change(text)
        if not result:
            self._transport.post(channel, self._format.parsing_error(), ts=ts)
            return None

        bot_id, user_id, points = result
        error = self._karma_change_sanity_check(initiator_id,
                                                user_id,
                                                bot_id,
                                                points)
        if error:
            self._transport.post(channel, error, ts=ts)
            return None

        username = self._transport.lookup_username(user_id)
        msg = self._format.new_voting(username, points)

        result = self._transport.post(channel, msg, ts=ts)
        karma = Voting(initial_msg_ts=ts,
                       bot_msg_ts=result['ts'],
                       channel=channel,
                       user_id=user_id,
                       initiator_id=initiator_id,
                       karma=points,
                       text=text)

        self._session.add(karma)
        self._session.commit()
        return True

    def close_expired_votes(self):
        result = True
        now = time.time()
        expired = self._session.query(Voting) \
            .filter(cast(Voting.bot_msg_ts, Float) + self._vote_timeout < now).all()

        # in order to avoid needlees backup
        if not expired:
            return result

        for e in expired:
            self._logger.debug('Expired voting: %s', e)

            reactions = self._transport.reactions_get(e.channel,
                                                      e.initial_msg_ts,
                                                      e.bot_msg_ts)
            if reactions is None:
                result = False
                self._logger.error('Failed to get messages for: %s', e)
                self._session.delete(e)
                continue

            success = self._determine_success(reactions)
            if success:
                karma = self._session.query(Karma).filter_by(user_id=e.user_id).first()
                if karma:
                    karma.karma += e.karma
                else:
                    self._session.add(Karma(user_id=e.user_id, karma=self._initial_value + e.karma))

            self._close(e, success)
            self._session.delete(e)

        self._session.commit()
        self._backup()
        return result

    def _close(self, karma_change, success):
        username = self._transport.lookup_username(karma_change.user_id)
        result = self._format.voting_result(username, karma_change.karma, success)
        return self._transport.update(karma_change.channel, result,
                                      karma_change.bot_msg_ts)

    def _determine_success(self, reactions):
        self._logger.debug('Reactions: %s', reactions)
        upvotes = [reactions[r] for r in self._upvote_emoji if r in reactions]
        downvotes = [reactions[r] for r in self._downvote_emoji if r in reactions]
        self._logger.debug('Upvotes: %s', upvotes)
        self._logger.debug('Downvotes: %s', downvotes)
        return sum(upvotes) - sum(downvotes) > 0

    def _karma_change_sanity_check(self,
                                   initiator_id,
                                   user_id,
                                   bot_id,
                                   karma):
        if not self._self_karma and initiator_id == user_id:
            return self._format.strange_error()
        if user_id == bot_id:
            return self._format.robo_error()
        if abs(karma) > self._max_shot:
            return self._format.max_shot_error(self._max_shot)
        return None
