import datetime
import gettext
import importlib
import pathlib


class Status:
    OPEN = ":hourglass_flowing_sand:"
    CLOSED = ":white_check_mark:"


class Color:
    ERROR = "#FF0000"
    INFO = "#3AA3E3"


class Format:
    _INTERVALS = (
        604800,  # 60 * 60 * 24 * 7
        86400,  # 60 * 60 * 24
        3600,  # 60 * 60
        60,
        1,
    )

    def __init__(
        self,
        lang: str,
        votes_up_emoji: list[str],
        votes_down_emoji: list[str],
        timeout: datetime.timedelta,
    ) -> None:
        lang_resource = importlib.resources.files("lang")
        with importlib.resources.as_file(lang_resource) as dir_path:
            self._install_lang_pack(dir_path, lang)
        self._votes_up_emoji = votes_up_emoji
        self._votes_down_emoji = votes_down_emoji
        self._display_time = self.display_time(timeout.seconds)

    @staticmethod
    def message(color, text: str, image: str | None = None) -> dict:
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

    def display_time(self, seconds, granularity=4) -> str:
        result = []

        for i, count in enumerate(Format._INTERVALS):
            value = seconds // count
            if value:
                seconds -= value * count
                name = gettext.gettext("time").split()[i]
                result.append(f"{value}{name}")
        return ", ".join(result[:granularity])

    def hello(self) -> dict:
        return Format.message(Color.INFO, gettext.gettext("hello"))

    def new_voting(self, username: str, karma: int) -> dict:
        text = gettext.gettext("new_voting").format(
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
            text = gettext.gettext("voting_result_success").format(
                Status.CLOSED, username, karma, emoji
            )
        else:
            emoji = ":fidget_spinner:"
            text = gettext.gettext("voting_result_nothing").format(Status.CLOSED, username, emoji)

        return Format.message(Color.INFO, text)

    def report_karma(self, username: str, karma: int) -> dict:
        return Format.message(Color.INFO, gettext.gettext("report_karma").format(username, karma))

    def parsing_error(self) -> dict:
        return Format.message(Color.ERROR, gettext.gettext("parsing_error").format(":robot_face:"))

    def max_diff_error(self, max_diff: int) -> dict:
        return Format.message(Color.ERROR, gettext.gettext("max_diff_error").format(max_diff))

    def strange_error(self) -> dict:
        return Format.message(Color.ERROR, gettext.gettext("strange_error").format(":grimacing:"))

    def robo_error(self) -> dict:
        return Format.message(Color.ERROR, gettext.gettext("robo_error").format(":robot_face:"))

    def cmd_error(self) -> dict:
        return Format.message(
            Color.ERROR, gettext.gettext("cmd_error"), image="https://i.imgflip.com/2cuafm.jpg"
        )

    def _install_lang_pack(self, lang_dir_path: pathlib.Path, lang: str) -> None:
        """Compile and install a language pack."""
        gettext.install(
            domain="messages",
            localedir=str(lang_dir_path),
            names=(lang,),
        )
        gettext.bindtextdomain(
            domain="messages",
            localedir=str(lang_dir_path),
        )
        gettext.textdomain("messages")
