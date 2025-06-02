from collections import Counter

from slack_sdk.web import SlackResponse, WebClient

from .logging import logger


def lookup_username(client: WebClient, user_id: str) -> str:
    user = user_id.strip("<>@")
    userinfo = client.users_info(user=user)
    return userinfo["user"]["profile"]["display_name"]


def lookup_channel_name(client: WebClient, channel_id: str) -> str:
    channel_id = channel_id.strip("<>@")
    channel_info = client.conversations_info(channel=channel_id)
    return channel_info["channel"]["name"]


def reactions_get(
    client: WebClient, channel: str, initial_msg_ts: str, bot_msg_ts: str
) -> Counter[str] | None:
    r: Counter[str] = Counter()
    for ts in (initial_msg_ts, bot_msg_ts):
        result = client.reactions_get(channel=channel, timestamp=ts)
        logger.info(f"Getting reactions: {result}")
        message = result.get("message")
        if message is None:
            return None
        reactions = message.get("reactions") or []
        for c in reactions:
            r[c["name"]] += c["count"]
    return r


def message_post(
    client: WebClient, channel: str, msg: dict, ts: str | None = None
) -> SlackResponse:
    logger.info(f"Sending message to {channel}: {msg}")
    return client.chat_postMessage(
        channel=channel, link_names=True, as_user=True, thread_ts=ts, **msg
    )


def message_update(client: WebClient, channel: str, msg: dict, ts: str) -> SlackResponse:
    logger.info(f"Sending update to {channel}: {msg}")
    return client.chat_update(channel=channel, link_names=True, as_user=True, ts=ts, **msg)


def channel_exists(client: WebClient, channel: str) -> bool:
    result = client.conversations_list(exclude_archived=True)
    channels = result.get("channels") or []
    return any(c["name"] == channel for c in channels)


def post_im(client: WebClient, user_id: str, msg: dict) -> SlackResponse:
    new_dm = client.im_open(user=user_id)
    return message_post(client, new_dm["channel"]["id"], msg)
