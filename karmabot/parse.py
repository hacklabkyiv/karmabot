import re

REGEX_USER = r"<@(\w+)(\|\w+)?>"
REGEX_KARMA = r"([+]{1,}|[-]{1,})"


class Parse:
    @staticmethod
    def user_mention(text: str) -> str | None:
        user_mention_match = re.match(f"{REGEX_USER}+", text)
        if user_mention_match:
            return user_mention_match[0]
        return None

    @staticmethod
    def karma_change(text: str) -> tuple[str, str, int] | None:
        full_match = re.match(f"{REGEX_USER} {REGEX_USER} {REGEX_KARMA}+", text)
        if not full_match:
            return None

        bot_id, user_id, vote = full_match.groups()
        plus = vote.count("+")
        minus = vote.count("-")
        return bot_id, user_id, plus or -minus

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
