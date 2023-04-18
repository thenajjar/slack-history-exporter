import logging
from typing import Optional

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class SlackClient:
    def __init__(self, token):
        self.client = WebClient(token=token)

    def get_chats_list(self, chat_type: str, limit: Optional[int] = 9999,
                       exclude_archived: Optional[bool] = True):
        chat_type = chat_type.lower()
        if not self.is_valid_chat_type(chat_type):
            return []
        conversations = {}
        public_conversations = {}
        private_conversations = {}
        channels = []
        type_check = ""
        if chat_type == "channel":
            public_conversations = (self.fetch_chats_list(
                chat_type="public_channel",
                limit=limit,
                exclude_archived=exclude_archived
            ))
            private_conversations = (self.fetch_chats_list(
                chat_type="private_channel",
                limit=limit,
                exclude_archived=exclude_archived
            ))
            type_check = "is_channel"
        elif chat_type == "group":
            conversations = (self.fetch_chats_list(
                chat_type="mpim",
                limit=limit,
                exclude_archived=exclude_archived
            ))
            type_check = "is_mpim"
        elif chat_type == "dm":
            conversations = (self.fetch_chats_list(
                chat_type="im",
                limit=limit,
                exclude_archived=exclude_archived
            ))
            type_check = "is_im"
        if conversations and chat_type != "channel":
            channels.extend(self.get_channels(conversations=conversations, type_check=type_check))
        else:
            if public_conversations:
                channels.extend(self.get_channels(conversations=public_conversations, type_check=type_check))
            if private_conversations:
                channels.extend(self.get_channels(conversations=private_conversations, type_check=type_check))
        if channels:
            logger.info(f"Found {len(channels)} {chat_type}s messages.")
        else:
            logger.info(f"No {chat_type}s messages found.")
        return channels

    def fetch_chats_list(self, chat_type: str, limit: Optional[int] = 9999, exclude_archived: Optional[bool] = True):
        conversations = []
        try:
            logger.info(f"Fetching {chat_type} messages...")
            conversations = self.client.conversations_list(
                types=chat_type,
                limit=limit,
                exclude_archived=exclude_archived
            )
        except SlackApiError as e:
            logger.error({
                "class": "SlackClient",
                "method": "fetch_conversations_list",
                "error_message": "Error fetching messages.",
                "type": chat_type,
                "limit": limit,
                "exclude_archived": exclude_archived,
                "error": str(e)
            })
        if conversations:
            logger.info(f"Found {len(conversations['channels'])} {chat_type} messages.")
        else:
            logger.info(f"No {chat_type} messages found.")
        return conversations

    def get_user_name(self, user_id: str):
        try:
            user_info = self.client.users_info(user=user_id)["user"]
            try:
                user_data = {"name": user_info["name"], "real_name": user_info["real_name"]}
            except KeyError:
                user_data = {"name": user_info["name"], "real_name": user_info["name"]}
        except SlackApiError as e:
            logger.error({
                "class": "SlackClient",
                "method": "get_user_name",
                "error_message": "Error fetching user info.",
                "user_id": user_id,
                "error": str(e)
            })
            user_data = {"name": user_id, "real_name": user_id}
        return user_data

    def get_chat_messages(self, chat_id: str, chat_name: str):
        messages = []
        try:
            logger.info(f"Fetching messages from {chat_id}...")
            response = self.client.conversations_history(channel=chat_id)
            messages += response["messages"]
            while response["has_more"]:
                response = self.client.conversations_history(
                    channel=chat_id,
                    cursor=response["response_metadata"]["next_cursor"]
                )
                messages += response["messages"]
        except SlackApiError as e:
            logger.error({
                "class": "SlackClient",
                "method": "get_chat_history",
                "error_message": "Error fetching messages.",
                "chat_id": chat_id,
                "error": str(e)
            })
        if messages:
            logger.info(f"Found {len(messages)} messages in {chat_name} chat.")
        else:
            logger.info(f"No messages found in {chat_name} chat.")
        return messages

    def get_message_replies(self, chat_id: str, message_ts: str):
        try:
            response = self.client.conversations_replies(
                channel=chat_id,
                ts=message_ts
            )
            replies = [reply for reply in response.get("messages") if reply.get("ts") != message_ts]
        except SlackApiError as e:
            logger.error({
                "class": self.__class__.__name__,
                "method": "get_message_replies",
                "error_message": "Error fetching replies.",
                "chat_id": chat_id,
                "error": str(e)
            })
            replies = []
        return replies

    @staticmethod
    def is_valid_chat_type(chat_type: str):
        if chat_type not in ["channel", "group", "dm"]:
            logger.error({
                "class": "SlackClient",
                "method": "get_conversations_list",
                "error_message": "Invalid type.",
                "valid_types": ["channel", "group", "dm"],
                "type": chat_type
            })
            return False
        return True

    @staticmethod
    def get_channels(conversations: dict, type_check: str):
        channels = []
        for conversation in conversations["channels"]:
            if conversation[type_check]:
                channels.append(conversation)
        return channels
