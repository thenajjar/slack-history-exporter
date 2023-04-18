import sys
import os
import logging
import requests

from PyQt5.QtCore import Qt
from datetime import datetime
import json
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QComboBox, QPushButton, QGridLayout, \
    QListWidget, QListWidgetItem, QCheckBox, QProgressBar, QLineEdit, QFileDialog

from libraries.slack import SlackClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

try:
    this_file = __file__
except NameError:
    this_file = sys.argv[0]
this_file = os.path.abspath(this_file)
if getattr(sys, 'frozen', False):
    application_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
else:
    application_path = os.path.dirname(this_file)


class SlackChatExporter(QWidget):
    def __init__(self):
        super().__init__()

        self.chat_types = {"Channel": "This type of chat is used for broadcasting messages to a large group of people.",
                           "Group Chat": "This type of chat is used for communication with a specific group of people.",
                           "Direct Message": "This type of chat is used for one-on-one communication."}
        self.chat_data = []
        self.visible_chat_data = []
        self.users = {}

        self.init_ui()

    def init_ui(self):
        # add an input field for the slack token
        self.token_label = QLabel("Enter your Slack token:")
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Slack token")

        # select folder path to save the chat history in
        self.folder_path_label = QLabel("Select a folder to save the chat history in:")
        self.folder_path_button = QPushButton("Select Folder")
        self.folder_path_button.clicked.connect(self.select_folder_path)


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
        self.search_bar.setPlaceholderText("Search chat names")
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
        grid.addWidget(self.token_label, 0, 0)
        grid.addWidget(self.token_input, 0, 1)
        grid.addWidget(self.folder_path_label, 1, 0)
        grid.addWidget(self.folder_path_button, 1, 1)
        grid.addWidget(self.chat_type_label, 2, 0)
        grid.addWidget(self.chat_type_combo, 2, 1)
        grid.addWidget(self.description_label, 3, 0, 1, 2)
        grid.addWidget(self.fetch_button, 4, 0, 1, 2)
        grid.addWidget(self.loading_bar, 5, 0, 1, 2)
        grid.addWidget(self.search_bar, 6, 0)
        grid.addWidget(self.chat_list_label, 7, 0)
        grid.addWidget(self.chat_list, 8, 0, 1, 2)
        grid.addWidget(self.save_media_checkbox, 9, 0)
        grid.addWidget(self.save_button, 9, 1)

        self.setLayout(grid)

        self.setWindowTitle("Chat Exporter")
        self.show()

    def update_description(self, text):
        self.description_label.setText(self.chat_types[text])

    def select_folder_path(self):
        self.folder_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        self.folder_path_button.setText(self.folder_path)


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
        self.slack_user_token = self.token_input.text().strip()
        if not self.slack_user_token:
            logger.error("No Slack token provided")
            self.token_input.setFocus()
            self.token_input.setStyleSheet("border: 1px solid red;")
            return
        self.token_input.setStyleSheet("border: 1px solid black;")
        self.slack_client = SlackClient(self.slack_user_token)
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
            html_content = html_template
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
        last_date = ""
        for message in reversed(chat_messages):
            replies = []
            user_id = message["user"]
            user_data = self.get_user_data(user_id=user_id)
            user_name = user_data["real_name"]
            message_ts = message["ts"]
            timestamp = datetime.fromtimestamp(float(message_ts)).strftime("%Y-%m-%d %H:%M:%S")
            current_date = timestamp.split(" ")[0]
            # add line break if date changed
            if current_date != last_date:
                html += f"""
                    <div class="date">
                        <p><bdi>{current_date}</bdi></p>
                    </div>
                    """
                last_date = current_date
            if message_text := message.get("text"):
                html += self.convert_message_to_html(message=message, user_name=user_name)
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
                                        <p><a href="{file_name}">{file_name}</a></p>
                                    """
                            if file.get("filetype") in ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"]:
                                html += f"""
                                            <video class="video" controls>
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
                    reply_result = self.convert_reply_to_html(reply=reply)
                    reply["html"] = reply_result.get("html")
                    if reply_result.get("media"):
                        media_dict.extend(reply_result.get("media"))
                    replies.append(reply)
            if replies:
                html += f"""
                            <div class="timestamp"><button onclick="showReplies('{message_ts}')"
                                    data-timestamp="{message_ts}"
                                    class="replies-btn">{message["reply_count"]} replies</button>{timestamp}
                            </div>
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

    def convert_reply_to_html(self, reply):
        reply_timestamp = datetime.fromtimestamp(float(reply["ts"])).strftime("%Y-%m-%d %H:%M:%S")
        media_dict = []
        html = '<div class="message reply">'
        if reply.get("text"):
            html += self.convert_message_to_html(message=reply, user_name=reply["user"])
            html += f"""
                        <div class="timestamp">{reply_timestamp}</div>
                    </div> </div>
                    """
        else:
            html += f"""
                                    <div class="message other">
                                        <p><strong><bdi>{reply["user"]}</bdi></strong></p>
                                    """
            if reply.get("files"):
                for file in reply["files"]:
                    if file_url := file.get("url_private"):
                        file_dict = {}
                        file_name = file["name"]
                        html += f"""
                                                    <p><a href="{file_name}">{file_name}</a></p>
                                                """
                        if file.get("filetype") in ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"]:
                            html += f"""
                                                        <video class="video" controls>
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
                                        <div class="timestamp">{reply_timestamp}</div>
                                    </div></div>
                                    """
        return {"html": html, "media": media_dict}

    def convert_message_to_html(self, message, user_name):
        html = ""
        text = message.get("text").replace("<", "&lt;").replace(">", "&gt;")
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
        return html
    def save_chat_to_file(self, chat_name: str, chat_type: str, html_content: str):
        try:
            filename = f"Nana Slack - {chat_type} - {chat_name}.html"
            folder_path = f"Nana Slack - {chat_type} - {chat_name}"
            project_path = application_path
            if self.folder_path_button.text() != "Default":
                project_path = self.folder_path_button.text()
            full_path = f"{project_path}/{folder_path}"
            if not os.path.exists(full_path):
                os.makedirs(full_path)
            with open(f"{full_path}/{filename}", "w", encoding="utf-8") as f:
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
                folder_name = f"Nana Slack - {chat_type} - {chat_name}"
                project_path = application_path
                if self.folder_path_button.text() != "Default":
                    project_path = self.folder_path_button.text()
                path = f"{project_path}/{folder_name}"
                if not os.path.exists(path):
                    os.makedirs(path)
                for file in media:
                    try:
                        files_percentage = int((media.index(file) + 1) / len(media) * 100)
                        file_name = file["file_name"].replace("<", "").replace(">", "").replace(":", "").replace("?", "").replace("/", "").replace("\\", "").replace("*", "").replace("|", "").replace('"', "")
                        file_id = file["file_id"]
                        file_url = file["file_url"]
                        file_path = f"{path}/{file_name}"
                        # check if file does not exists already in the directory
                        if os.path.exists(file_path):
                            logger.info(f"File {file_name} already exists!")
                            total_percentage = int(chat_percentage * (0.5 + (files_percentage / 100) * 0.5))
                            self.loading_bar.setValue(total_percentage)
                            QApplication.processEvents()
                            continue
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

html_template = """
<!DOCTYPE html>
<html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PLACE_PAGE_TITLE_HERE</title>
        <style>
            body {
            background-color: #232931;
            color: #fff;
            font-family: Arial, sans-serif;
            font-size: 16px;
            }
            .container {
            margin-top: 30px;
            margin-bottom: 30px;
            max-width: 95%;
            margin-left: auto;
            margin-right: auto;
            background-color: #393E46;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 0 10px rgba(0, 0, 0, 0.3);
            height: auto;
            clear: both; /* added this line to clear any floats */
            overflow: auto; /* added this line to show a scrollbar if necessary */
            }
            .message {
            padding: 10px;
            max-width: 780px;
            margin-bottom: 10px;
            border-radius: 5px;
            clear: both;
            }
            .message.me {
            background-color: #1c1c1c;
            float: right;
            }
            .message.other {
            background-color: #1c1c1c;
            float: left;
            }
            .message.reply {
            background-color: #1c1c1c;
            float: left;
            border: 1px solid #ccc;
            margin-top: 10px;
            }
            .message.me p, .message.other p, .message.reply p {
            margin: 0;
            font-size: 14px;
            line-height: 1.5;
            word-wrap: break-word;
            }
            .timestamp {
            font-size: 12px;
            color: #999;
            margin-top: 5px;
            margin-left: 5px;
            }
            .code-block {
            background-color: #383838;
            border: 1px solid #9c9c9c;
            border-radius: 5px;
            margin: 10px 0;
            padding: 10px;
            clear: both; /* added this line to clear any floats */
            overflow: auto; /* added this line to show a scrollbar if necessary */
            }
            .code-block pre {
            margin: 0;
            float: left;
            }
            .img {
            max-width: 100%;
            height: auto;
            }
            .video {
            max-width: 100%;
            height: auto;
            }
            .replies-btn {
            background-color: transparent;
            color: #00a6ff;
            border: none;
            font-size: 12px;
            cursor: pointer;
            }
            .replies-btn:hover {
            text-decoration: underline;
            }
            .date {
                display: block;
                width: 100%;
                margin-top: 10px;
                overflow: hidden;
                text-align: center;
                color: #999;
            }

            .date::after {
                content: "";
                display: inline-block;
                width: 100%;
                height: 1px;
                margin-bottom: 10px;
                background-color: #999;
            }
            /* Media queries */
            @media (max-width: 800px) {
            .container {
            max-width: 90%;
            }
            }
            @media (max-width: 600px) {
            .message {
            max-width: 95%;
            }
            }
        </style>
    </head>
    <body>
        <div class="container">
            PLACE_MESSAGES_HERE
        </div>
        <script>
            function showReplies(timestamp) {
                var data = JSON.stringify(PLACE_REPLIES_HERE);
                var replies = JSON.parse(data);
                var repliesHtml = '';
                for (const element of replies[timestamp]) {
                    repliesHtml += element.html;
                }
                var parentContainer = document.querySelector(`button[data-timestamp="${timestamp}"]`).parentNode;
                var repliesContainer = document.createElement('div');
                repliesContainer.classList.add('replies-container');
                repliesContainer.innerHTML = repliesHtml;
                repliesContainer.setAttribute('data-timestamp', timestamp);
                parentContainer.parentNode.insertBefore(repliesContainer, parentContainer.nextSibling);
                parentContainer.removeChild(parentContainer.querySelector(`button[data-timestamp="${timestamp}"]`));
            }
        </script>
    </body>
</html>
"""


if __name__ == '__main__':
    app = QApplication(sys.argv)
    chat_exporter = SlackChatExporter()
    sys.exit(app.exec_())
