import sys
import socket
import struct
import threading
import logging
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLineEdit, QTextEdit, QLabel, QComboBox, QListWidget, QInputDialog
from PyQt5.QtCore import Qt, QTimer
from user import User
from room import Room
from message import Message
import pickle

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ChatClient(QWidget):
    def __init__(self):
        super().__init__()
        self.user = None
        self.client_socket = None
        self.listening_socket = None
        self.server_host = '127.0.0.1'
        self.server_port = 5555
        self.rooms = ["Broadcast"]
        self.current_room = "Broadcast"
        self.messages = []

        self.init_ui()
        self.manage_socket()

    def init_ui(self):
        self.setWindowTitle("Chat Application")
        self.setGeometry(100, 100, 800, 600)

        layout = QVBoxLayout()

        # Auth widgets
        self.auth_widget = QWidget()
        auth_layout = QVBoxLayout()
        self.username_input = QLineEdit()
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.login_button = QPushButton("Login")
        self.register_button = QPushButton("Register")

        auth_layout.addWidget(QLabel("Username:"))
        auth_layout.addWidget(self.username_input)
        auth_layout.addWidget(QLabel("Password:"))
        auth_layout.addWidget(self.password_input)
        auth_layout.addWidget(self.login_button)
        auth_layout.addWidget(self.register_button)
        self.auth_widget.setLayout(auth_layout)

        # Chat widgets
        self.chat_widget = QWidget()
        chat_layout = QVBoxLayout()
        
        toolbar_layout = QHBoxLayout()
        self.room_selector = QComboBox()
        self.refresh_rooms_button = QPushButton("Refresh") # refresh rooms and messages
        self.create_room_button = QPushButton("Create Room")
        self.add_participants_button = QPushButton("Add Participants")
        self.logout_button = QPushButton("Logout")

        toolbar_layout.addWidget(self.room_selector)
        toolbar_layout.addWidget(self.refresh_rooms_button)
        toolbar_layout.addWidget(self.create_room_button)
        toolbar_layout.addWidget(self.add_participants_button)
        toolbar_layout.addWidget(self.logout_button)

        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.message_input = QLineEdit()
        self.send_button = QPushButton("Send")

        chat_layout.addLayout(toolbar_layout)
        chat_layout.addWidget(self.chat_display)
        chat_layout.addWidget(self.message_input)
        chat_layout.addWidget(self.send_button)
        self.chat_widget.setLayout(chat_layout)

        layout.addWidget(self.auth_widget)
        layout.addWidget(self.chat_widget)
        self.setLayout(layout)

        # Initially hide chat widget
        self.chat_widget.hide()

        # Connect signals
        self.login_button.clicked.connect(self.login)
        self.register_button.clicked.connect(self.register)
        self.logout_button.clicked.connect(self.logout)
        self.refresh_rooms_button.clicked.connect(lambda: self.get_rooms(force=True))
        self.create_room_button.clicked.connect(self.create_room)
        self.add_participants_button.clicked.connect(self.add_participants)
        self.room_selector.currentTextChanged.connect(self.select_render_room)
        self.send_button.clicked.connect(self.send_message)
        self.message_input.returnPressed.connect(self.send_message)

    def manage_socket(self):
        self.client_socket = self.create_socket()

    def create_socket(self):
        logger.debug("Creating socket...")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect((self.server_host, self.server_port))
            return client_socket
        except ConnectionRefusedError:
            logger.error("Server is not available. Please start the server and try again.")
            self.show_error("Server is not available. Please start the server and try again.")
            sys.exit()

    def login(self):
        username = self.username_input.text()
        password = self.password_input.text()
        if not username or not password:
            self.show_error("Please enter a username and password.")
            return

        try:
            logger.debug(f"Sending 'LOGIN', username and password to server...")
            self.send_all(self.client_socket, f"LOGIN|{username}|{password}")
            response = self.receive(self.client_socket)
        except Exception as e:
            logger.error(f"Exception in login(): {e}")
            self.cleanup_client_socket()
            return

        if "successful" in response:
            logger.debug(f"Server responded with successful: {response}")
            self.user = User(username, password, self.client_socket)
            self.show_chat_view()
            self.get_rooms()
        else:
            logger.debug(f"Server responded with failed: {response}")
            self.show_error("Login failed. Please check your credentials.")

    def register(self):
        username = self.username_input.text()
        password = self.password_input.text()
        if not username or not password:
            self.show_error("Please enter a username and password.")
            return

        try:
            logger.debug(f"Sending 'REGISTER', username and password to server...")
            self.send_all(self.client_socket, f"REGISTER|{username}|{password}")
            response = self.receive(self.client_socket)
        except Exception as e:
            logger.error(f"Exception: {e}")
            self.cleanup_client_socket()
            return

        if "successful" in response:
            logger.debug(f"Server responded with successful: {response}")
            self.show_info("Registration successful. You can now login.")
        else:
            logger.debug(f"Server responded with failed: {response}")
            self.show_error("Registration failed. Please try a different username.")

    def logout(self):
        self.send_all(self.client_socket, "LOGOUT")
        try:    
            response = self.client_socket.recv(1024).decode('utf-8')
            logger.debug(f"Server response: {response}")
        except Exception as e:
            logger.error(f"Exception occurred: {e}\n")
        
        self.client_socket.close()
        self.manage_socket()
        self.user = None
        self.show_auth_view()

    def show_auth_view(self):
        self.chat_widget.hide()
        self.auth_widget.show()

    def show_chat_view(self):
        self.auth_widget.hide()
        self.chat_widget.show()

    def get_rooms(self, force=False):
        try:
            logger.debug(f"IN GET ROOMS ROOM NAME IS {self.current_room}\n")
            self.send_all(self.client_socket, "SEND_ROOMS")
            logger.debug("Receiving rooms from server...")
            self.rooms = self.receive(self.client_socket).split("|")
            logger.debug(f"Received rooms from server: {self.rooms}")
            self.update_room_selector()
        except Exception as e:
            logger.debug(f"Exception in get_rooms(): {e}")
            self.cleanup_client_socket()
            self.show_auth_view()

    def update_room_selector(self):
        current_room = self.current_room
        self.room_selector.clear()
        self.room_selector.addItems(self.rooms) # prebrishuva self.current_room
        if current_room in self.rooms:
            self.room_selector.setCurrentText(current_room)

    def select_render_room(self, room_name):
        if not room_name:
            return

        self.send_all(self.client_socket, f"SELECT_ROOM|{room_name}")
        logger.debug(f"Sent action: SELECT_ROOM|{room_name}")

        response = self.receive(self.client_socket)
        if "SUCCESSFULLY" not in response:
            self.show_error("Access Denied!")
        else:
            self.current_room = room_name
            self.show_info("Successfully joined room!")
            room_messages = self.get_room_messages(room_name)
            self.update_chat_display(room_messages)

    def get_room_messages(self, room_name):
        serialized_messages = self.client_socket.recv(2048)
        messages = pickle.loads(serialized_messages)
        return messages

    def update_chat_display(self, messages):
        self.chat_display.clear()
        for message in messages:
            self.chat_display.append(f"<b>{message.author_name}</b> ({message.timestamp.strftime('%c')}): {message.text}")

    def send_message(self):
        message = self.message_input.text()
        if not message:
            return

        msg = f"SEND_MESSAGE|{self.current_room}|{message}"
        self.send_all(self.client_socket, msg)
        logger.debug(f"Message sent: {msg}")

        response = self.receive(self.client_socket)
        logger.debug(f"Received response after sending Message: {response}")
        
        self.message_input.clear()
        self.select_render_room(self.current_room)  # Refresh messages

    def create_room(self):
        room_name, ok = QInputDialog.getText(self, "Create Room", "Enter room name:")
        if ok and room_name:
            logger.debug(f"Sending 'CREATE_ROOM' and room_name to server...")
            self.send_all(self.client_socket, f"CREATE_ROOM|{room_name}")
            logger.debug(f"CREATE_ROOM and room_name sent.")
            self.get_rooms(force=True)

    def add_participants(self):
        if self.current_room == "Broadcast":
            self.show_error("Cannot add participants to Broadcast room.")
            return

        self.send_all(self.client_socket, f"ADD_PARTICIPANTS|{self.current_room}")
        registered_users = self.receive(self.client_socket).split("|")
        logger.debug(f"Received registered_users from server: {registered_users}")

        participants, ok = QInputDialog.getItem(self, "Add Participants", 
                                                "Select users to add:", 
                                                registered_users, 0, True)
        if ok and participants:
            self.send_all(self.client_socket, participants)
            logger.debug(f"Sent participants to server: {participants}")
        else:
            self.send_all(self.client_socket, "")
        

    def cleanup_client_socket(self):
        self.client_socket.close()
        self.client_socket = self.create_socket()

    def send_all(self, sock, msg):
        fullmsg = struct.pack("!i", len(msg)) + msg.encode()
        sock.sendall(fullmsg)

    def receive(self, sock):
        length = struct.unpack("!i", self.recv_all(sock, 4))[0]
        message = self.recv_all(sock, length).decode()
        return message

    def recv_all(self, sock, length):
        data = b""
        while len(data) < length:
            more = sock.recv(length - len(data))
            if not more:
                raise EOFError("Socket closed %d bytes into a %d-byte message" % (len(data), length))
            data += more
        return data

    def show_error(self, message):
        # In a real application, you'd use QMessageBox for errors
        print(f"Error: {message}")

    def show_info(self, message):
        # In a real application, you'd use QMessageBox for info messages
        print(f"Info: {message}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    client = ChatClient()
    client.show()
    sys.exit(app.exec_())