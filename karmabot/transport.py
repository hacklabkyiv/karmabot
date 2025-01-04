from collections import Counter

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk.web import SlackResponse

from .config import KarmabotConfig
from .logging import logger


class Transport:
    def __init__(self, config: KarmabotConfig) -> None:
        self.slack_app = App(token=config.slack_bot_token)
        self.slack_app_token = config.slack_app_token

    def start(self) -> None:
        SocketModeHandler(self.slack_app, self.slack_app_token).start()

    def lookup_username(self, user_id: str) -> str:
        user = user_id.strip("<>@")
        userinfo = self.slack_app.client.users_info(user=user)
        return userinfo["user"]["profile"]["display_name"]

    def lookup_channel_name(self, channel_id: str) -> str:
        channel_id = channel_id.strip("<>@")
        channel_info = self.slack_app.client.channels_info(channel=channel_id)
        return channel_info["channel"]["name"]

    def reactions_get(
        self, channel: str, initial_msg_ts: str, bot_msg_ts: str
    ) -> Counter[str] | None:
        r: Counter[str] = Counter()
        for ts in (initial_msg_ts, bot_msg_ts):
            result = self.slack_app.client.reactions_get(channel=channel, timestamp=ts)
            logger.info(f"Getting reactions: {result}")
            message = result.get("message")
            if message is None:
                return None
            reactions = message.get("reactions") or []
            for c in reactions:
                r[c["name"]] += c["count"]
        return r

    def post(self, channel: str, msg: dict, ts: str | None = None) -> SlackResponse:
        logger.info(f"Sending message to {channel}: {msg}")
        return self.slack_app.client.chat_postMessage(
            channel=channel, link_names=True, as_user=True, thread_ts=ts, **msg
        )

    def update(self, channel: str, msg: dict, ts: str) -> SlackResponse:
        logger.info(f"Sending update to {channel}: {msg}")
        return self.slack_app.client.chat_update(
            channel=channel, link_names=True, as_user=True, ts=ts, **msg
        )

    def channel_exists(self, channel: str) -> bool:
        result = self.slack_app.client.conversations_list(exclude_archived=True)
        channels = result.get("channels") or []
        return any(c["name"] == channel for c in channels)

    def post_im(self, user_id: str, msg: dict) -> SlackResponse:
        new_dm = self.slack_app.client.im_open(user=user_id)
        return self.post(new_dm["channel"]["id"], msg)
