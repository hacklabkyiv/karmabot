import re

REGEX_USER = r"<@(\w+)(\|\w+)?>"
REGEX_KARMA = r"([+]{1,}|[-]{1,})"
REGEX_KARMA_CHANGE = rf"<@(\w+)>\s+<@(\w+)>\s+{REGEX_KARMA}+(\s+\w+)?"


class Parse:
    @staticmethod
    def karma_change(text: str) -> tuple[str, str, int, str | None] | None:
        r = re.match(REGEX_KARMA_CHANGE, text)
        if not r:
            return None

        bot_id, user_id, vote, reason = r.groups()
        plus = vote.count("+")
        minus = vote.count("-")
        if reason:
            reason = reason.strip()
        return bot_id, user_id, plus or -minus, reason

    @staticmethod
    def cmd_get(text: str) -> tuple[str, str | None] | None:
        r = re.match(rf"get\s+{REGEX_USER}", text)
        if not r:
            return None
        user_id, user_name = r.groups()
        user_name = user_name.removeprefix("|") if user_name else None
        return user_id, user_name

    @staticmethod
    def cmd_set(text: str) -> tuple[str, str | None, int] | None:
        r = re.match(rf"set\s+{REGEX_USER}\s([-+]?[0-9]+)$", text)
        if not r:
            return None
        user_id, user_name, karma = r.groups()
        user_name = user_name.removeprefix("|") if user_name else None
        return user_id, user_name, int(karma)
