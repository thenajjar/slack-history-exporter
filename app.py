import json
import logging
import os
import sys
from datetime import datetime

import requests
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QCheckBox, QComboBox, QFileDialog, QGridLayout, QLabel, QLineEdit, \
    QListWidget, QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QWidget

from libraries.slack import SlackClient

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

version = "V1.0.1"

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
        self.checked_chat_names = {}
        self.slack_user_token = ""
        # fetch users from users.json if it exists, otherwise create it
        try:
            if os.path.exists(os.path.join(application_path, "users.json")):
                with open(os.path.join(application_path, "users.json"), "r") as f:
                    self.users = json.load(f)
            else:
                with open(os.path.join(application_path, "users.json"), "w") as f:
                    json.dump(self.users, f)
        except Exception as e:
            logger.exception(e)
            logger.error({
                "class": self.__class__.__name__,
                "method": "__init__",
                "error_message": "Error loading users.json.",
                "error": str(e)
            })
        # fetch slack user token from token.json if it exists, otherwise create it
        try:
            if os.path.exists(os.path.join(application_path, "tokens.json")):
                with open(os.path.join(application_path, "tokens.json"), "r") as f:
                    token = json.load(f)
                    if "slack_user_token" in token:
                        self.slack_user_token = token["slack_user_token"]
            else:
                with open(os.path.join(application_path, "tokens.json"), "w") as f:
                    json.dump("", f)
                    self.slack_user_token = ""
        except Exception as e:
            logger.exception(e)
            logger.error({
                "class": self.__class__.__name__,
                "method": "__init__",
                "error_message": "Error loading tokens.json.",
                "error": str(e)
            })
        self.init_ui()

    def init_ui(self):
        # add an input field for the slack token
        self.token_label = QLabel("Enter your Slack token:")
        self.token_input = QLineEdit()
        self.token_input.setPlaceholderText("Slack token")
        if self.slack_user_token:
            self.token_input.setText(self.slack_user_token)

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

        # add label "created by"
        self.created_by_label = QLabel(f"{version} - Created by: Abdulwahab Alnajjar")

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
        grid.addWidget(self.created_by_label, 10, 0, 1, 2)

        self.setLayout(grid)

        self.setWindowTitle("Slack Chat History Exporter")
        self.show()

    def closeEvent(self, event):
        try:
            self.slack_user_token = self.token_input.text()
            with open(os.path.join(application_path, "tokens.json"), "w") as f:
                json.dump({"slack_user_token": self.slack_user_token}, f)
            with open(os.path.join(application_path, "users.json"), "w") as f:
                json.dump(self.users, f)
            QApplication.processEvents()
        except Exception as e:
            logger.exception(e)
            logger.error({
                "class": self.__class__.__name__,
                "method": "closeEvent",
                "error_message": "Error saving users.json or tokens.json.",
                "error": str(e)
            })
        reply = QMessageBox.question(
            self,
            "Message", "Are you sure you want to exist?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        # save users.json and tokens.json
        if reply == QMessageBox.Yes:
            event.accept()
        else:
            event.ignore()

    def update_description(self, text):
        self.description_label.setText(self.chat_types[text])

    def select_folder_path(self):
        self.folder_path = QFileDialog.getExistingDirectory(self, "Select Directory")
        self.folder_path_button.setText(self.folder_path)

    def search_chat_names(self, text):
        # save check state of all items in dict with id as key
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            if item.checkState() == Qt.Checked:
                self.checked_chat_names[self.visible_chat_data[i]["chat"]["id"]] = Qt.Checked
            else:
                self.checked_chat_names[self.visible_chat_data[i]["chat"]["id"]] = Qt.Unchecked
        self.chat_list.clear()
        self.visible_chat_data = []
        for chat in self.chat_data:
            if text.lower().strip() in chat["data"][0].lower() or text.lower() in chat["data"][1].lower():
                item = QListWidgetItem(f"{chat['number']}: {chat['data'][1]}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                if chat["chat"]["id"] in self.checked_chat_names:
                    item.setCheckState(self.checked_chat_names[chat["chat"]["id"]])
                else:
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
        self.checked_chat_names = {}
        self.search_bar.clear()
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
        self.search_bar.setEnabled(False)
        self.save_button.setEnabled(False)
        self.chat_type_combo.setEnabled(False)
        self.token_input.setEnabled(False)
        QApplication.processEvents()
        self.chat_data = []
        self.visible_chat_data = []
        chat_type = self.chat_type_combo.currentText()
        if chat_type == "Channel":
            channels = self.slack_client.get_chats_list(chat_type="channel")
            self.chat_data = [{"number": i + 1, "type": chat_type, "data": [c["name"], c["name"]], "chat": c} for i, c
                              in
                              enumerate(channels)]
            self.loading_bar.setValue(100)
        elif chat_type == "Group Chat":
            groups = self.slack_client.get_chats_list(chat_type="group")
            self.chat_data = [{"number": i + 1, "type": chat_type, "data": [g["name"], g["name"]], "chat": g} for i, g
                              in
                              enumerate(groups)]
            self.loading_bar.setValue(100)
        elif chat_type == "Direct Message":
            direct_messages = self.slack_client.get_chats_list(chat_type="dm")
            for i, d in enumerate(direct_messages):
                user_id = d["user"]
                user_data = self.get_user_data(user_id=user_id)
                chat_number = i + 1
                chat_data = [user_data["name"], user_data["real_name"]]
                self.chat_data.append({
                    "number": i + 1,
                    "type": chat_type,
                    "data": chat_data,
                    "chat": d
                })
                value_percentage = int((i + 1) / len(direct_messages) * 100)
                self.loading_bar.setValue(value_percentage)
                item = QListWidgetItem(f"{chat_number}: {chat_data[1]}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, d["id"])
                self.checked_chat_names[d["id"]] = Qt.Unchecked
                self.chat_list.addItem(item)
                self.chat_list.scrollToBottom()
                QApplication.processEvents()
        if chat_type != "Direct Message":
            for chat in self.chat_data:
                item = QListWidgetItem(f"{chat['number']}: {chat['data'][0]}")
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                item.setData(Qt.UserRole, chat["chat"]["id"])
                self.checked_chat_names[chat["chat"]["id"]] = Qt.Unchecked
                self.chat_list.addItem(item)
        try:
            with open(os.path.join(application_path, "tokens.json"), "w") as f:
                json.dump({"slack_user_token": self.slack_user_token}, f)
            with open(os.path.join(application_path, "users.json"), "w") as f:
                json.dump(self.users, f)
        except Exception as e:
            logger.exception(e)
            logger.error({
                "class": self.__class__.__name__,
                "method": "fetch_chat_names",
                "error_message": "Error saving user data",
                "error": str(e)
            })
        self.visible_chat_data = self.chat_data
        self.save_media_checkbox.setEnabled(True)
        self.save_button.setEnabled(True)
        self.search_bar.setEnabled(True)
        self.save_button.setEnabled(True)
        self.chat_type_combo.setEnabled(True)
        self.token_input.setEnabled(True)
        QApplication.processEvents()

    def save_chat_history(self):
        self.search_bar.clear()
        self.search_chat_names("")
        self.save_button.setEnabled(False)
        self.save_media_checkbox.setEnabled(False)
        self.loading_bar.setValue(0)
        self.search_bar.setEnabled(False)
        self.save_button.setEnabled(False)
        self.chat_type_combo.setEnabled(False)
        self.token_input.setEnabled(False)
        QApplication.processEvents()
        selected_chats = []
        save_media = self.save_media_checkbox.isChecked()
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            if item.checkState() == Qt.Checked:
                selected_chats.append(self.visible_chat_data[i])
        total_chats = len(selected_chats)
        chat_progress_unit = 100 / total_chats
        current_chat_progress = 0
        for chat in selected_chats:
            self.loading_bar.setValue(int(current_chat_progress))
            QApplication.processEvents()
            chat_id = chat["chat"]["id"]
            chat_type = chat["type"]
            if chat_type != "Direct Message":
                chat_name = chat["chat"]["name"]
            else:
                user_id = chat["chat"]["user"]
                user_data = self.get_user_data(user_id=user_id)
                chat_name = f"{user_data['name']} ({user_data['real_name']})"
            self.media_file_names = []
            folder_name = f"Nana Slack - {chat_type} - {chat_name}".replace("<", "").replace(">", "").replace(":",
                                                                                                              "").replace(
                "?", "").replace("/", "").replace("\\", "").replace("*", "").replace("|", "").replace('"', "")
            project_path = application_path
            if self.folder_path_button.text() != "Default":
                project_path = self.folder_path_button.text()
            folder_path = f"{project_path}/{folder_name}"
            if not os.path.exists(folder_path):
                os.makedirs(folder_path)
            media_folder_path = f"{folder_path}/media"
            if not os.path.exists(media_folder_path):
                os.makedirs(media_folder_path)
            # get all the file names in the media folder
            for file in os.listdir(media_folder_path):
                self.media_file_names.append(file)
            chat_messages = self.slack_client.get_chat_messages(
                chat_id=chat_id,
                chat_name=chat_name,
            )
            html_result = self.convert_chat_to_html(
                chat_id=chat_id,
                chat_name=chat_name,
                chat_type=chat_type,
                chat_messages=chat_messages,
                chat_progress_unit=chat_progress_unit,
                current_chat_progress=current_chat_progress,
            )
            current_message_progress = html_result.get("current_message_progress")
            QApplication.processEvents()
            self.save_chat_to_file(
                chat_name=chat_name,
                chat_type=chat["type"],
                html_content=html_result.get("html"),
                folder_path=folder_path
            )
            save_html_unit = chat_progress_unit * 0.1
            current_html_progress = save_html_unit + current_chat_progress
            self.loading_bar.setValue(int(current_html_progress))
            QApplication.processEvents()
            if save_media:
                self.save_chat_media(
                    chat_name=chat_name,
                    chat_type=chat["type"],
                    media=html_result.get("media"),
                    chat_progress_unit=chat_progress_unit,
                    current_html_progress=current_html_progress,
                    media_folder_path=media_folder_path
                )
            current_chat_progress += chat_progress_unit
        self.loading_bar.setValue(100)
        self.save_button.setEnabled(True)
        self.save_media_checkbox.setEnabled(True)
        self.search_bar.setEnabled(True)
        self.save_button.setEnabled(True)
        self.chat_type_combo.setEnabled(True)
        self.token_input.setEnabled(True)
        QApplication.processEvents()

    def convert_chat_to_html(self, chat_id: str, chat_name: str, chat_type: str, chat_messages: list,
                             chat_progress_unit: float, current_chat_progress: float):
        try:
            html_content = html_template
            page_title = f"Nana Slack | {chat_type} | {chat_name}"
            html_content = html_content.replace("PLACE_PAGE_TITLE_HERE", page_title)
            chat_messages_result = self.convert_chat_messages_to_html(
                chat_id=chat_id,
                chat_messages=chat_messages,
                chat_progress_unit=chat_progress_unit,
                current_chat_progress=current_chat_progress
            )
            html_content = html_content.replace("PLACE_MESSAGES_HERE", chat_messages_result.get("html"))
            html_content = html_content.replace(
                "PLACE_REPLIES_HERE",
                json.dumps(chat_messages_result.get("replies"), ensure_ascii=True)
            )
            return {
                "html": html_content,
                "media": chat_messages_result.get("media"),
                "current_message_progress": chat_messages_result.get("current_message_progress"),
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
                "media": [],
                "current_message_progress": current_chat_progress,
            }

    def convert_chat_messages_to_html(self, chat_id, chat_messages: list, chat_progress_unit: float,
                                      current_chat_progress: float):
        media_list = []
        replies_dict = {}
        html = ""
        last_date = ""
        total_messages = len(chat_messages)
        current_message_progress = current_chat_progress
        for message_index, message in enumerate(reversed(chat_messages)):
            try:
                replies = []
                user_id = message["user"] if message.get("user") else message["bot_id"]
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
                if message.get("text"):
                    html += self.convert_message_to_html(message=message, user_name=user_name)
                    if message.get("files"):
                        for file in message["files"]:
                            try:
                                if file_url := file.get("url_private"):
                                    file_dict = {}
                                    file_name = file["name"]
                                    file_name_fixed = self.fix_file_name(file_name=file_name)
                                    self.media_file_names.append(file_name_fixed)
                                    html += f"""
                                                <p><a href="./media/{file_name_fixed}">{file_name_fixed}</a></p>
                                            """
                                    if file.get("filetype") in ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"]:
                                        html += f"""
                                                    <video class="video" controls>
                                                        <source src="./media/{file_name_fixed}" type="video/mp4">
                                                        <source src="./media/{file_name_fixed}" type="video/quicktime">
                                                        Your browser does not support the video tag.
                                                    </video>
                                                """
                                    elif file.get("filetype") in ["jpg", "png", "gif", "jpeg", "bmp", "svg", "tiff",
                                                                  "tif",
                                                                  "webp"]:
                                        html += f"""
                                            <div class="container">
                                                <img class="img" src="./media/{file_name_fixed}">
                                            </div>
                                        """
                                    elif file.get("filetype") in ["mp3", "wav", "ogg", "flac", "aac", "wma", "m4a",
                                                                  "m4b", "m4p", "m4r", "m4v", "m4b"]:
                                        html += f"""
                                                    <audio class="audio" controls>
                                                        <source src="./media/{file_name_fixed}" type="audio/mpeg">
                                                        Your browser does not support the audio tag.
                                                    </audio>
                                                """
                                    file_dict["file_name"] = file_name_fixed
                                    file_dict["file_url"] = file_url
                                    media_list.append(file_dict)
                                elif file.get("name"):
                                    html += f"""
                                                        <p><strong>{file['name']}</strong></p>
                                                    """
                            except Exception as e:
                                logger.exception(e)
                                logger.error({
                                    "class": self.__class__.__name__,
                                    "method": "convert_chat_messages_to_html",
                                    "error_message": "Error converting file to html",
                                    "chat_id": chat_id,
                                    "error": str(e)
                                })
                else:
                    html += f"""
                            <div class="message other">
                                <p><strong><bdi>{user_name}</bdi></strong></p>
                            """
                    if message.get("files"):
                        for file in message["files"]:
                            try:
                                if file_url := file.get("url_private"):
                                    file_dict = {}
                                    file_name = file["name"]
                                    file_name_fixed = self.fix_file_name(file_name=file_name)
                                    self.media_file_names.append(file_name_fixed)
                                    html += f"""
                                                <p><a href="./media/{file_name_fixed}">{file_name_fixed}</a></p>
                                            """
                                    if file.get("filetype") in ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"]:
                                        html += f"""
                                                    <video class="video" controls>
                                                        <source src="./media/{file_name_fixed}" type="video/mp4">
                                                        <source src="./media/{file_name_fixed}" type="video/quicktime">
                                                        Your browser does not support the video tag.
                                                    </video>
                                                """
                                    elif file.get("filetype") in ["jpg", "png", "gif", "jpeg", "bmp", "svg", "tiff",
                                                                  "tif",
                                                                  "webp"]:
                                        html += f"""
                                            <div class="container">
                                                <img class="img" src="./media/{file_name_fixed}">
                                            </div>
                                        """
                                    elif file.get("filetype") in ["mp3", "wav", "ogg", "flac", "aac", "wma", "m4a",
                                                                  "m4b", "m4p", "m4r", "m4v", "m4b"]:
                                        html += f"""
                                                    <audio class="audio" controls>
                                                        <source src="./media/{file_name_fixed}" type="audio/mpeg">
                                                        Your browser does not support the audio tag.
                                                    </audio>
                                                """
                                    file_dict["file_name"] = file_name_fixed
                                    file_dict["file_url"] = file_url
                                    media_list.append(file_dict)
                                elif file.get("name"):
                                    html += f"""
                                                        <p><strong>{file['name']}</strong></p>
                                                    """
                            except Exception as e:
                                logger.exception(e)
                                logger.error({
                                    "class": self.__class__.__name__,
                                    "method": "convert_chat_messages_to_html",
                                    "error_message": "Error converting file to html",
                                    "chat_id": chat_id,
                                    "error": str(e)
                                })
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
                        try:
                            reply_user_id = reply["user"] if reply.get("user") else reply["bot_id"]
                            reply_user_data = self.get_user_data(user_id=reply_user_id)
                            reply["user"] = reply_user_data["real_name"]
                            reply_result = self.convert_reply_to_html(reply=reply)
                            reply["html"] = reply_result.get("html")
                            if reply_result.get("media"):
                                media_list.extend(reply_result.get("media"))
                            replies.append(reply)
                        except Exception as e:
                            logger.exception(e)
                            logger.error({
                                "class": self.__class__.__name__,
                                "method": "convert_chat_messages_to_html",
                                "error_message": "Error converting chat messages to html",
                                "chat_id": chat_id,
                                "chat_message": message,
                                "error": str(e)
                            })
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
                chat_progress_unit = chat_progress_unit * 0.4 / total_messages * (message_index + 1)
                current_message_progress = current_chat_progress + chat_progress_unit
                self.loading_bar.setValue(int(current_message_progress))
                QApplication.processEvents()
            except Exception as e:
                logger.exception(e)
                logger.error({
                    "class": self.__class__.__name__,
                    "method": "convert_chat_messages_to_html",
                    "error_message": "Error converting chat messages to html",
                    "chat_id": chat_id,
                    "chat_message": message,
                    "error": str(e)
                })
        self.media_file_names = []
        return {
            "html": html,
            "replies": replies_dict,
            "media": media_list,
            "current_message_progress": current_message_progress
        }

    def convert_reply_to_html(self, reply):
        reply_timestamp = datetime.fromtimestamp(float(reply["ts"])).strftime("%Y-%m-%d %H:%M:%S")
        media_list = []
        html = '<div class="message reply">'
        if reply.get("text"):
            html += self.convert_message_to_html(message=reply, user_name=reply["user"])
            if reply.get("files"):
                for file in reply["files"]:
                    try:
                        if file_url := file.get("url_private"):
                            file_dict = {}
                            file_name = file["name"]
                            file_name_fixed = self.fix_file_name(file_name=file_name)
                            self.media_file_names.append(file_name_fixed)
                            html += f"""
                                                        <p><a href="./media/{file_name_fixed}">{file_name_fixed}</a></p>
                                                    """
                            if file.get("filetype") in ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"]:
                                html += f"""
                                                            <video class="video" controls>
                                                                <source src="./media/{file_name_fixed}" type="video/mp4">
                                                                <source src="./media/{file_name_fixed}" type="video/quicktime">
                                                                Your browser does not support the video tag.
                                                            </video>
                                                        """
                            elif file.get("filetype") in ["jpg", "png", "gif", "jpeg", "bmp", "svg", "tiff", "tif",
                                                          "webp"]:
                                html += f"""
                                                    <div class="container">
                                                        <img class="img" src="./media/{file_name_fixed}">
                                                    </div>
                                                """
                            elif file.get("filetype") in ["mp3", "wav", "ogg", "flac", "aac", "wma", "m4a",
                                                          "m4b", "m4p", "m4r", "m4v", "m4b"]:
                                html += f"""
                                            <audio class="audio" controls>
                                                <source src="./media/{file_name_fixed}" type="audio/mpeg">
                                                Your browser does not support the audio tag.
                                            </audio>
                                        """
                            file_dict["file_name"] = file_name_fixed
                            file_dict["file_url"] = file_url
                            media_list.append(file_dict)
                        elif file.get("name"):
                            html += f"""
                                                                <p><strong>{file['name']}</strong></p>
                                                            """
                    except Exception as e:
                        logger.exception(e)
                        logger.error({
                            "class": self.__class__.__name__,
                            "method": "convert_reply_to_html",
                            "error_message": "Error converting reply to html",
                            "reply": reply,
                            "error": str(e)
                        })
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
                    try:
                        if file_url := file.get("url_private"):
                            file_dict = {}
                            file_name = file["name"]
                            file_name_fixed = self.fix_file_name(file_name=file_name)
                            self.media_file_names.append(file_name_fixed)
                            html += f"""
                                                        <p><a href="./media/{file_name_fixed}">{file_name_fixed}</a></p>
                                                    """
                            if file.get("filetype") in ["mp4", "mov", "avi", "wmv", "flv", "webm", "mkv"]:
                                html += f"""
                                                            <video class="video" controls>
                                                                <source src="./media/{file_name_fixed}" type="video/mp4">
                                                                <source src="./media/{file_name_fixed}" type="video/quicktime">
                                                                Your browser does not support the video tag.
                                                            </video>
                                                        """
                            elif file.get("filetype") in ["jpg", "png", "gif", "jpeg", "bmp", "svg", "tiff", "tif",
                                                          "webp"]:
                                html += f"""
                                                    <div class="container">
                                                        <img class="img" src="./media/{file_name_fixed}">
                                                    </div>
                                                """
                            elif file.get("filetype") in ["mp3", "wav", "ogg", "flac", "aac", "wma", "m4a",
                                                          "m4b", "m4p", "m4r", "m4v", "m4b"]:
                                html += f"""
                                            <audio class="audio" controls>
                                                <source src="./media/{file_name_fixed}" type="audio/mpeg">
                                                Your browser does not support the audio tag.
                                            </audio>
                                        """
                            file_dict["file_name"] = file_name_fixed
                            file_dict["file_url"] = file_url
                            media_list.append(file_dict)
                        elif file.get("name"):
                            html += f"""
                                                                <p><strong>{file['name']}</strong></p>
                                                            """
                    except Exception as e:
                        logger.exception(e)
                        logger.error({
                            "class": self.__class__.__name__,
                            "method": "convert_reply_to_html",
                            "error_message": "Error converting reply to html",
                            "reply": reply,
                            "error": str(e)
                        })
            else:
                html += """
                                            <p><em>Unknown message type</em></p>
                                        """
            html += f"""
                                        <div class="timestamp">{reply_timestamp}</div>
                                    </div></div>
                                    """
        return {"html": html, "media": media_list.copy()}

    def fix_file_name(self, file_name):
        file_name_fixed = file_name.replace("<", "").replace(">", "").replace(":", "").replace("?",
                                                                                               "").replace(
            "/", "").replace("\\", "").replace("*", "").replace("|", "").replace('"', "")
        parts = file_name_fixed.rsplit(".", 1)
        if len(parts) == 1:
            return file_name_fixed
        new_file_name = parts[0].replace(".", "_")
        count = 1
        while f"{new_file_name}{count}.{parts[1]}" in self.media_file_names:
            count += 1
        file_name_fixed = f"{new_file_name}{count}.{parts[1]}"
        return file_name_fixed

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

    def save_chat_to_file(self, chat_name: str, chat_type: str, html_content: str, folder_path: str):
        try:
            html_filename = f"Nana Slack - {chat_type} - {chat_name}.html".replace("<", "").replace(">", "").replace(
                ":", "").replace("?", "").replace("/", "").replace("\\", "").replace("*", "").replace("|", "").replace(
                '"', "")
            with open(f"{folder_path}/{html_filename}", "w", encoding="utf-8") as f:
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

    def save_chat_media(self, chat_name: str, chat_type: str, media: list, media_folder_path: str,
                        chat_progress_unit: float, current_html_progress: float):
        try:
            if media:
                for file_index, file in enumerate(media):
                    try:
                        files_percentage = (media.index(file) + 1) / len(media) * 100
                        file_name = file["file_name"].replace("<", "").replace(">", "").replace(":", "").replace("?",
                                                                                                                 "").replace(
                            "/", "").replace("\\", "").replace("*", "").replace("|", "").replace('"', "")
                        file_url = file["file_url"]
                        media_file_path = f"{media_folder_path}/{file_name}"
                        # check if file does not exists already in the directory
                        media_progress_unit = chat_progress_unit * 0.5 / len(media) * (file_index + 1)
                        current_media_progress = current_html_progress + media_progress_unit
                        if os.path.exists(media_file_path):
                            self.loading_bar.setValue(int(current_media_progress))
                            QApplication.processEvents()
                            continue
                        logger.info(f"Downloading {file_name}...")
                        headers = {
                            "Authorization": f"Bearer {self.slack_user_token}"
                        }
                        response = requests.get(file_url, headers=headers)
                        with open(media_file_path, 'wb') as f:
                            f.write(response.content)
                        self.loading_bar.setValue(int(current_media_progress))
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
            max-height: 400px;
            height: auto;
            }
            .video {
            max-width: 100%;
            max-height: 400px;
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
