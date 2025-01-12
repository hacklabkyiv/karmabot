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
    def cmd_get(text: str) -> str | None:
        r = re.match(rf"get\s+{REGEX_USER}", text)
        if not r:
            return None
        user_id, _ = r.groups()
        return user_id

    @staticmethod
    def cmd_set(text: str) -> tuple[str, int] | None:
        r = re.match(rf"set\s+{REGEX_USER}\s([-+]?[0-9]+)$", text)
        if not r:
            return None
        user_id, karma = r.groups()
        return user_id, int(karma)

    @staticmethod
    def cmd_digest(text: str) -> bool:
        return text.strip() == "digest"

    @staticmethod
    def cmd_pending(text: str) -> bool:
        return text.strip() == "pending"

    @staticmethod
    def cmd_help(text: str) -> bool:
        return text.strip() == "help"
