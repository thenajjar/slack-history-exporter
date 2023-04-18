import sys
import os
import logging
import requests

from PyQt5.QtCore import Qt
from datetime import datetime
import json
from dotenv import load_dotenv
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QComboBox, QPushButton, QGridLayout, \
    QListWidget, QListWidgetItem, QCheckBox, QProgressBar, QLineEdit

from libraries.slack import SlackClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

load_dotenv()


class SlackChatExporter(QWidget):
    def __init__(self):
        super().__init__()

        self.chat_types = {"Channel": "This type of chat is used for broadcasting messages to a large group of people.",
                           "Group Chat": "This type of chat is used for communication with a specific group of people.",
                           "Direct Message": "This type of chat is used for one-on-one communication."}
        self.slack_user_token = os.environ.get("SLACK_USER_TOKEN")
        self.slack_bot_token = os.environ.get("SLACK_BOT_TOKEN")
        self.slack_client = SlackClient(self.slack_user_token)
        self.chat_data = []
        self.visible_chat_data = []
        self.users = {}

        self.init_ui()

    def init_ui(self):
        self.chat_type_label = QLabel("Choose the type of chat to export:")
        self.chat_type_combo = QComboBox()
        self.chat_type_combo.addItems(self.chat_types.keys())
        self.chat_type_combo.currentTextChanged.connect(self.update_description)

        self.description_label = QLabel(self.chat_types["Channel"])

        self.fetch_button = QPushButton("Fetch Chat Names")
        self.fetch_button.clicked.connect(self.fetch_chat_names)

        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 100)

        # add search bar
        self.search_bar = QLineEdit()
        self.search_bar.textChanged.connect(self.search_chat_names)
        self.chat_list_label = QLabel("Select chat(s) to export:")
        self.chat_list = QListWidget()
        self.chat_list.setSelectionMode(QListWidget.NoSelection)

        self.save_media_checkbox = QCheckBox("Save media")
        self.save_media_checkbox.setChecked(True)
        self.save_media_checkbox.setEnabled(False)

        self.save_button = QPushButton("Save Chat History")
        self.save_button.clicked.connect(self.save_chat_history)
        self.save_button.setEnabled(False)

        grid = QGridLayout()
        grid.addWidget(self.chat_type_label, 0, 0)
        grid.addWidget(self.chat_type_combo, 0, 1)
        grid.addWidget(self.description_label, 1, 0, 1, 2)
        grid.addWidget(self.fetch_button, 2, 0, 1, 2)
        grid.addWidget(self.loading_bar, 3, 0, 1, 2)
        grid.addWidget(self.search_bar, 4, 0)
        grid.addWidget(self.chat_list_label, 5, 0)
        grid.addWidget(self.chat_list, 6, 0, 1, 2)
        grid.addWidget(self.save_media_checkbox, 7, 0)
        grid.addWidget(self.save_button, 7, 1)

        self.setLayout(grid)

        self.setWindowTitle("Chat Exporter")
        self.show()

    def update_description(self, text):
        self.description_label.setText(self.chat_types[text])

    def search_chat_names(self, text):
        self.chat_list.clear()
        self.visible_chat_data = []
        for chat in self.chat_data:
            if text.lower() in chat["data"][0].lower():
                item = QListWidgetItem(f"{chat['number']}: {', '.join(chat['data'])}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.chat_list.addItem(item)
                self.visible_chat_data.append(chat)

    def get_user_data(self, user_id: str):
        try:
            user_data = self.users[user_id]
        except KeyError:
            user_data = self.slack_client.get_user_name(user_id=user_id)
            self.users[user_id] = user_data
        return user_data

    def fetch_chat_names(self):
        self.save_button.setEnabled(False)
        self.save_media_checkbox.setEnabled(False)
        self.chat_list.clear()
        self.loading_bar.setValue(0)
        QApplication.processEvents()
        self.chat_data = []
        self.visible_chat_data = []
        chat_type = self.chat_type_combo.currentText()
        if chat_type == "Channel":
            channels = self.slack_client.get_chats_list(chat_type="channel")
            self.chat_data = [{"number": i + 1, "type": chat_type, "data": [c["name"]], "chat": c} for i, c in
                              enumerate(channels)]
            self.loading_bar.setValue(100)
        elif chat_type == "Group Chat":
            groups = self.slack_client.get_chats_list(chat_type="group")
            self.chat_data = [{"number": i + 1, "type": chat_type, "data": [g["name"]], "chat": g} for i, g in
                              enumerate(groups)]
            self.loading_bar.setValue(100)
        elif chat_type == "Direct Message":
            direct_messages = self.slack_client.get_chats_list(chat_type="dm")
            for i, d in enumerate(direct_messages):
                user_id = d["user"]
                user_name_data = self.slack_client.get_user_name(user_id=user_id)
                self.users[user_id] = self.slack_client.get_user_name(user_id=user_id)
                chat_number = i + 1
                chat_data = [user_name_data["name"], user_name_data["real_name"]]
                self.chat_data.append({
                    "number": i + 1,
                    "type": chat_type,
                    "data": chat_data,
                    "chat": d
                })
                value_percentage = int((i + 1) / len(direct_messages) * 100)
                self.loading_bar.setValue(value_percentage)
                item = QListWidgetItem(f"{chat_number}: {', '.join(chat_data)}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.chat_list.addItem(item)
                QApplication.processEvents()
        if chat_type != "Direct Message":
            for chat in self.chat_data:
                item = QListWidgetItem(f"{chat['number']}: {', '.join(chat['data'])}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.chat_list.addItem(item)
        self.visible_chat_data = self.chat_data
        self.save_media_checkbox.setEnabled(True)
        self.save_button.setEnabled(True)

    def save_chat_history(self):
        self.save_button.setEnabled(False)
        self.save_media_checkbox.setEnabled(False)
        self.loading_bar.setValue(0)
        QApplication.processEvents()
        selected_chats = []
        save_media = self.save_media_checkbox.isChecked()
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_chats.append(self.visible_chat_data[i])
        for chat in selected_chats:
            chat_percentage = int((selected_chats.index(chat) + 1) / len(selected_chats) * 100)
            chat_id = chat["chat"]["id"]
            if chat["type"] != "Direct Message":
                chat_name = chat["chat"]["name"]
            else:
                user_id = chat["chat"]["user"]
                user_data = self.get_user_data(user_id=user_id)
                chat_name = f"{user_data['name']} ({user_data['real_name']})"
            chat_messages = self.slack_client.get_chat_messages(
                chat_id=chat_id,
                chat_name=chat_name,
            )
            html_result = self.convert_chat_to_html(
                chat_id=chat_id,
                chat_name=chat_name,
                chat_type=chat["type"],
                chat_messages=chat_messages,
            )
            self.loading_bar.setValue(int(chat_percentage * 0.25))
            QApplication.processEvents()
            self.save_chat_to_file(chat_name=chat_name, chat_type=chat["type"], html_content=html_result.get("html"))
            self.loading_bar.setValue(int(chat_percentage * 0.5))
            QApplication.processEvents()
            if save_media:
                self.save_chat_media(chat_name=chat_name, chat_type=chat["type"], media=html_result.get("media"), chat_percentage=chat_percentage)
        self.loading_bar.setValue(100)
        self.save_button.setEnabled(True)
        self.save_media_checkbox.setEnabled(True)
        QApplication.processEvents()

    def convert_chat_to_html(self, chat_id: str, chat_name: str, chat_type: str, chat_messages: list):
        try:
            with open("./templates/chat_page_template.html", "r", encoding="utf-8") as file:
                html_content = file.read()
            page_title = f"Nana Slack | {chat_type} | {chat_name}"
            html_content = html_content.replace("PLACE_PAGE_TITLE_HERE", page_title)
            chat_messages_result = self.convert_chat_messages_to_html(
                chat_id=chat_id,
                chat_messages=chat_messages,
            )
            html_content = html_content.replace("PLACE_MESSAGES_HERE", chat_messages_result.get("html"))
            html_content = html_content.replace(
                "PLACE_REPLIES_HERE",
                json.dumps(chat_messages_result.get("replies"), ensure_ascii=True)
            )
            return {
                "html": html_content,
                "media": chat_messages_result.get("media")
            }
        except Exception as e:
            logger.exception(e)
            logger.error({
                "class": self.__class__.__name__,
                "method": "convert_chat_to_html",
                "error_message": "Error converting chat to html",
                "chat_name": chat_name,
                "error": str(e)
            })
            return {
                "html": "",
                "media": []
            }

    def convert_chat_messages_to_html(self, chat_id, chat_messages: list):
        media_dict = []
        replies_dict = {}
        html = ""
        for message in reversed(chat_messages):
            replies = []
            user_id = message["user"]
            user_data = self.get_user_data(user_id=user_id)
            user_name = user_data["real_name"]
            message_ts = message["ts"]
            timestamp = datetime.fromtimestamp(float(message_ts)).strftime("%Y-%m-%d %H:%M:%S")
            if message_text := message.get("text"):
                text = message_text.replace("<", "&lt;").replace(">", "&gt;")
                if "```" in text:
                    # Split message text into code blocks and regular text
                    blocks = text.split("```")
                    text_html = ""
                    for i, block in enumerate(blocks):
                        if i % 2 == 0:
                            # Regular text block
                            text_html += f"<p><bdi>{block}</bdi></p>"
                        else:
                            # Code block
                            text_html += f'<div class="code-block"><pre>{block}</pre></div>'
                    html += f"""
                        <div class="message other">
                            <p><strong><bdi>{user_name}</bdi></strong></p>
                                {text_html}
                        """
                else:
                    html += f"""
                            <div class="message other">
                                <p><strong><bdi>{user_name}</bdi></strong></p>
                                <p><bdi>{text}</bdi></p>
                            """
                if attachments := message.get("attachments"):
                    for attachment in attachments:
                        html += f"  <p><em><bdi>{attachment.get('pretext', '')}</bdi></em></p>"
                        if attachment.get("title"):
                            html += f"  <p><strong><bdi>{attachment['title']}</bdi></strong></p>"
                        if attachment.get("text"):
                            text = attachment["text"].replace("<", "&lt;").replace(">", "&gt;")
                            html += f"  <p><bdi>{text}</bdi></p>"
                        if image_url := attachment.get("image_url"):
                            image_url = image_url.replace("<", "").replace(">", "")
                            html += f"""
                                        <p><img class="img" src="{image_url}"></p>
                                    """
                if message.get("reply_count") and message.get("reply_count") > 0:
                    temp_replies = self.slack_client.get_message_replies(
                        chat_id=chat_id,
                        message_ts=message_ts
                    )
                    # fix name of users in replies
                    for reply in temp_replies:
                        reply_user_id = reply["user"]
                        reply_user_data = self.get_user_data(user_id=reply_user_id)
                        reply["user"] = reply_user_data["real_name"]
                        replies.append(reply)
                if replies:
                    html += f"""
                        <div class="timestamp"><button onclick="showReplies('{message_ts}')"
                                data-timestamp="{message_ts}"
                                class="replies-btn">{message["reply_count"]} replies</button>{timestamp}</div>
                        </div>
                    """
                else:
                    html += f"""
                                <div class="timestamp">{timestamp}</div>
                            </div>
                            """
            else:
                html += f"""
                        <div class="message other">
                            <p><strong><bdi>{user_name}</bdi></strong></p>
                        """
                if message.get("files"):
                    for file in message["files"]:
                        if file_url := file.get("url_private"):
                            file_dict = {}
                            file_name = file["name"]
                            html += f"""
                                        <p><a href="{file_url}">{file_name}</a></p>
                                    """
                            if file.get("filetype") in ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"]:
                                html += f"""
                                            <video class="video" crossorigin="https://files.slack.com/" controls>
                                                <source src="{file_name}" type="video/mp4">
                                                <source src="{file_name}" type="video/quicktime">
                                                Your browser does not support the video tag.
                                            </video>
                                        """
                            elif file.get("filetype") in ["jpg", "png", "gif", "jpeg", "bmp", "svg", "tiff", "tif",
                                                          "webp"]:
                                html += f"""
                                    <div class="container">
                                        <img class="img" src="{file_name}">
                                    </div>
                                """
                            file_dict["file_id"] = file.get("id")
                            file_dict["file_type"] = file.get("filetype")
                            file_dict["file_name"] = file_name
                            file_dict["file_url"] = file_url
                            media_dict.append(file_dict)
                        elif file.get("name"):
                            html += f"""
                                                <p><strong>{file['name']}</strong></p>
                                            """
                else:
                    html += """
                                <p><em>Unknown message type</em></p>
                            """
                html += f"""
                            <div class="timestamp">{timestamp}</div>
                        </div>
                        """
            replies_dict[message_ts] = replies
        return {
            "html": html,
            "replies": replies_dict,
            "media": media_dict
        }

    def save_chat_to_file(self, chat_name: str, chat_type: str, html_content: str):
        try:
            filename = f"Nana Slack - {chat_type} - {chat_name}.html"
            path = f"Nana Slack - {chat_type} - {chat_name}"
            if not os.path.exists(path):
                os.makedirs(path)
            with open(f"{path}/{filename}", "w") as f:
                f.write(html_content)
        except Exception as e:
            logger.error({
                "class": self.__class__.__name__,
                "method": "save_chat_to_file",
                "error_message": "Error saving chat to file",
                "chat_name": chat_name,
                "chat_type": chat_type,
                "error": str(e)
            })


    def save_chat_media(self, chat_name: str, chat_type: str, media: list, chat_percentage: int):
        try:
            if media:
                path = f"Nana Slack - {chat_type} - {chat_name}"
                if not os.path.exists(path):
                    os.makedirs(path)
                for file in media:
                    files_percentage = int((media.index(file) + 1) / len(media) * 100)
                    file_name = file["file_name"]
                    file_id = file["file_id"]
                    file_url = file["file_url"]
                    file_path = f"{path}/{file_name}"
                    logger.info(f"Downloading {file_name}...")
                    headers = {
                        "Authorization": f"Bearer {self.slack_user_token}"
                    }
                    response = requests.get(file_url, headers=headers)
                    with open(file_path, 'wb') as f:
                        f.write(response.content)
                    total_percentage = int(chat_percentage * (0.5 + (files_percentage / 100) * 0.5))
                    self.loading_bar.setValue(total_percentage)
                    QApplication.processEvents()
                logger.info("Download all media is complete!")
        except Exception as e:
            logger.exception(e)
            logger.error({
                "class": self.__class__.__name__,
                "method": "save_chat_media",
                "error_message": "Error saving chat media",
                "chat_name": chat_name,
                "chat_type": chat_type,
                "error": str(e)
            })


if __name__ == '__main__':
    app = QApplication(sys.argv)
    chat_exporter = SlackChatExporter()
    sys.exit(app.exec_())
