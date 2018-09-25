import logging
import time
from .orm import get_scoped_session, Voting, Karma
from .parse import Parse
from .words import Color


# FIXME: check every where for succeded POST
class KarmaManager:
    def __init__(self, cfg, transport, fmt):
        self._config = cfg
        self._transport = transport
        self._format = fmt
        self._session = get_scoped_session(cfg.DB_URI)
        self._logger = logging.getLogger('KarmaManager')

    def get(self, user_id, channel):
        karma = self._session.query(Karma).filter_by(user_id=user_id).first()
        if karma:
            value = karma.karma
        else:
            value = self._config.INITIAL_USER_KARMA
            self._session.add(Karma(user_id=user_id, karma=self._config.INITIAL_USER_KARMA))
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

    def create(self, initiator_id, channel, text, ts):
        # Check for an already existing voting
        instance = self._session.query(Voting).filter_by(uuid=(ts, channel)).first()
        if instance:
            self._logger.fatal(f'Voting already exists: ts={ts}, channel={channel}')
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
            .filter(Voting.bot_msg_ts + self._config.VOTE_TIMEOUT < now).all()
        for e in expired:
            self._logger.debug(f'Expired voting: {e}')

            reactions = self._transport.reactions_get(e.channel, e.initial_msg_ts, e.bot_msg_ts)
            if reactions is None:
                result = False
                self._logger.error(f'Failed to get messages for: {e}')
                self._session.delete(e)
                continue

            success = self._determine_success(reactions)
            if success:
                karma = self._session.query(Karma).filter_by(user_id=e.user_id).first()
                if karma:
                    karma.karma += e.karma
                else:
                    self._session.add(Karma(user_id=e.user_id, karma=self._config.INITIAL_USER_KARMA + e.karma))

            self._close(e, success)
            self._session.delete(e)

        self._session.commit()
        return result

    def _close(self, karma_change, success):
        username = self._transport.lookup_username(karma_change.user_id)
        return self._transport.update(karma_change.channel,
                                             self._format.voting_result(username, karma_change.karma, success),
                                             karma_change.bot_msg_ts)

    def _determine_success(self, reactions):
        self._logger.debug(f'Reactions: {reactions}')
        upvotes = [reactions[r] for r in self._config.UPVOTE_EMOJI if r in reactions]
        downvotes = [reactions[r] for r in self._config.DOWNVOTE_EMOJI if r in reactions]
        self._logger.debug(f'Upvotes: {upvotes}')
        self._logger.debug(f'Downvotes: {downvotes}')
        return sum(upvotes) - sum(downvotes) > 0

    def _karma_change_sanity_check(self,
                                   initiator_id,
                                   user_id,
                                   bot_id,
                                   karma):
        if not self._config.SELF_KARMA and initiator_id == user_id:
            return self._format.strange_error()
        if user_id == bot_id:
            return self._format.robo_error()
        if abs(karma) > self._config.MAX_SHOT:
            return self._format.max_shot_error(self._config.MAX_SHOT)
        return None
