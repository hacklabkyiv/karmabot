from words import Format
import re


class Parse:
    REGEX = {
        'user': '<@([A-Za-z]+[A-Za-z0-9-_]+)>',
        'karma': '([\+]{1,}|[\-]{1,})',
    }

    @staticmethod
    def user_mention(text):
        user_mention_match = re.match(Parse.REGEX['user'] + '+', text)
        if user_mention_match:
            return user_mention_match[0]
        return None

    @staticmethod
    def karma_change(text):
        full_match = re.match(Parse.REGEX['user'] + ' ' + Parse.REGEX['user'] + ' ' + Parse.REGEX['karma'] + '+', text)
        if not full_match:
            return None, Format.parsing_error()

        bot_id, user_id, vote = full_match.groups()
        plus = vote.count('+')
        minus = vote.count('-')
        return (bot_id, user_id, plus or -minus), None

    @staticmethod
    def cmd_get(text):
        r = re.match('get' + ' ' + Parse.REGEX['user'], text)
        if not r:
            return None, Format.cmd_error()
        return r[1], None

    @staticmethod
    def cmd_set(text):
        r = re.match('set' + ' ' + Parse.REGEX['user'] + ' ' + '([-+]?[0-9]+)$', text)
        if not r:
            return None, Format.cmd_error()
        user_id, karma = r.groups()
        return (user_id, int(karma)), None