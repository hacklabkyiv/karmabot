from collections import Counter
from words import Format
import re


REGEX = {
    'user': '<@([A-Za-z]+[A-Za-z0-9-_]+)>',
    'karma': '([\+]{1,}|[\-]{1,})',
}


class Parse:
    @staticmethod
    def user_mention(text):
        user_mention_match = re.match(REGEX['user'] + '+', text)
        if user_mention_match:
            return user_mention_match[0]
        return None

    @staticmethod
    def karma_change(text):
        full_match = re.match(REGEX['user'] + ' ' + REGEX['user'] + ' ' + REGEX['karma'] + '+', text)
        if not full_match:
            return None, Format.parsing_error()

        bot_id, user_id, vote = full_match.groups()
        plus = vote.count('+')
        minus = vote.count('-')
        return (bot_id, user_id, plus or -minus), None

    @staticmethod
    def karma_change_sanity_check(initiator_id,
                                  user_id,
                                  bot_id,
                                  self_karma,
                                  karma,
                                  max_shot):
        if not self_karma and initiator_id == user_id:
            return Format.strange_error()
        if user_id == bot_id:
            return Format.robo_error()
        if abs(karma) > max_shot:
            return Format.max_shot_error(max_shot)
        return None

    @staticmethod
    def reactions(reactions):
        c = Counter()
        for r in reactions:
            c[r['name']] += r['count']
        return c

    @staticmethod
    def cmd_get(text):
        r = re.match('get' + ' ' + REGEX['user'], text)
        if not r:
            return None, Format.cmd_error()
        return r[1], None

    @staticmethod
    def cmd_set(text):
        r = re.match('set' + ' ' + REGEX['user'] + ' ' + '(\d{1,6})', text)
        if not r:
            return None, Format.cmd_error()
        user_id, karma = r.groups()
        return (user_id, int(karma)), None
