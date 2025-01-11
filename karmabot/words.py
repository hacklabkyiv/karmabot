import datetime
import gettext
import importlib


class Status:
    OPEN = ":hourglass_flowing_sand:"
    CLOSED = ":white_check_mark:"


class Color:
    ERROR = "#FF0000"
    INFO = "#3AA3E3"


_INTERVALS = (
    604800,  # 60 * 60 * 24 * 7
    86400,  # 60 * 60 * 24
    3600,  # 60 * 60
    60,
    1,
)


class Format:
    def __init__(
        self,
        lang: str,
        votes_up_emoji: list[str],
        votes_down_emoji: list[str],
        timeout: datetime.timedelta,
    ) -> None:
        lang_resource = importlib.resources.files("lang")
        with importlib.resources.as_file(lang_resource) as dir_path:
            self._translation = gettext.translation(
                domain="messages",
                localedir=str(dir_path),
                languages=(lang,),
            )
        self._votes_up_emoji = votes_up_emoji
        self._votes_down_emoji = votes_down_emoji
        self._display_time = self.display_time(timeout.seconds)

    @staticmethod
    def message(color: str, text: str, image: str | None = None) -> dict:
        return {
            "attachments": [
                {
                    "mrkdwn_in": ["text"],
                    "color": color,
                    "attachment_type": "default",
                    "callback_id": "karma_voting",
                    "fallback": text,
                    "text": text,
                    "image_url": image,
                }
            ]
        }

    def display_time(self, seconds: int, granularity=4) -> str:
        result = []

        for i, count in enumerate(_INTERVALS):
            value = seconds // count
            if value:
                seconds -= value * count
                name = self._translation.gettext("time").split()[i]
                result.append(f"{value}{name}")
        return ", ".join(result[:granularity])

    def hello(self) -> dict:
        return Format.message(Color.INFO, self._translation.gettext("hello"))

    def new_voting(self, username: str, karma: int) -> dict:
        text = self._translation.gettext("new_voting").format(
            Status.OPEN,
            karma,
            username,
            ":" + ": :".join(self._votes_up_emoji) + ":",
            ":" + ": :".join(self._votes_down_emoji) + ":",
            self._display_time,
        )
        return Format.message(Color.INFO, text)

    def voting_result(self, username: str, karma: int, success: bool) -> dict:
        if success:
            emoji = ":tada:" if karma > 0 else ":face_palm:"
            text = self._translation.gettext("voting_result_success").format(
                Status.CLOSED, username, karma, emoji
            )
        else:
            emoji = ":fidget_spinner:"
            text = self._translation.gettext("voting_result_nothing").format(
                Status.CLOSED, username, emoji
            )

        return Format.message(Color.INFO, text)

    def report_karma(self, username: str, karma: int) -> dict:
        return Format.message(
            Color.INFO, self._translation.gettext("report_karma").format(username, karma)
        )

    def parsing_error(self) -> dict:
        return Format.message(
            Color.ERROR, self._translation.gettext("parsing_error").format(":robot_face:")
        )

    def max_diff_error(self, max_diff: int) -> dict:
        return Format.message(
            Color.ERROR, self._translation.gettext("max_diff_error").format(max_diff)
        )

    def strange_error(self) -> dict:
        return Format.message(
            Color.ERROR, self._translation.gettext("strange_error").format(":grimacing:")
        )

    def robo_error(self) -> dict:
        return Format.message(
            Color.ERROR, self._translation.gettext("robo_error").format(":robot_face:")
        )

    def cmd_error(self) -> dict:
        return Format.message(
            Color.ERROR,
            self._translation.gettext("cmd_error"),
            image="https://i.imgflip.com/2cuafm.jpg",
        )
