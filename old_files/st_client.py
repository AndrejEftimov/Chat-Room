import sys
import socket
import struct
import threading
import logging
import streamlit as st
from user import User
from room import Room
from message import Message
import json
import pickle
import traceback
from datetime import datetime
import time

logger = logging.getLogger(__name__)
#logger.addHandler(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.DEBUG) # DEBUG OR ERROR

class Client:
    
    user = None # User if logged in
    client_socket = None
    listening_socket = None
    server_host = '127.0.0.1'
    server_port = 5555
    view = 'auth' #default is auth

    def __init__(self):
        logger.debug("Running __init__()...")

        st.title("Socket-based Chat Application")

        self.manage_socket()
        self.manage_view()
        self.manage_messages()
        self.manage_rooms()
        self.activate_view()


    def manage_socket(self):
        if 'client_socket' not in st.session_state:
            st.session_state['client_socket'] = self.create_socket()
        self.client_socket = st.session_state['client_socket']


    def manage_view(self):
        if 'view' not in st.session_state:
            self.set_view('auth')
        self.view = self.get_view()


    def is_logged_in(self):
        if 'logged_in' not in st.session_state:
            st.session_state['logged_in'] = False
            st.session_state['username'] = ""
        
        if 'user' not in st.session_state:
            st.session_state['user'] = None
        else:
            self.user = st.session_state['user']

        if not st.session_state['logged_in']:
            return None
        
        return st.session_state['username']
    

    def manage_messages(self):
        if 'messages' not in st.session_state:
            st.session_state['messages'] = []

        if 'new_messages' not in st.session_state:
            st.session_state['new_messages'] = False


    def manage_rooms(self):
        if 'rooms' not in st.session_state:
            st.session_state['rooms'] = ["Broadcast"]
        self.rooms = st.session_state['rooms']

        if 'current_room' not in st.session_state:
            st.session_state['current_room'] = 'Broadcast'

        if 'got_rooms' not in st.session_state:
            st.session_state['got_rooms'] = False

        if 'received_registered_users' not in st.session_state:
            st.session_state['received_registered_users'] = False
    

    def activate_view(self):
        if 'view' not in st.session_state:
            self.set_view('auth')

        self.view = self.get_view()

        match self.view:
            case 'auth':
                self.auth_view()
            case 'chat':
                self.chat_view()
            case 'create_room':
                self.create_room_view()
            case 'add_participants':
                self.add_participants_view()
    

    def auth_view(self):
        st.sidebar.title("Login/Registration")
        action = st.sidebar.selectbox("Choose Action", ["Login", "Register"])

        if action == "Login":
            self.login()

        elif action == "Register":
            self.register()


    def chat_view(self):
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.session_state['current_room'] != "Broadcast":
                add_participants_btn = st.button("Add Participants", key="add_participants_btn")
                if add_participants_btn:
                    self.set_view('add_participants')
                    st.rerun()

        with col2:
            create_room_btn = st.button("Create Room", key="create_room_btn")
        if create_room_btn:
            self.set_view('create_room')
            st.rerun()
        
        with col3:
            logout_btn = st.button("Logout", key="logout_btn")
        if logout_btn:
            self.logout()

        st.sidebar.title("Chat Rooms")

        refresh_rooms_btn = st.sidebar.button("Refresh Rooms", key="refresh_rooms_btn")
        if refresh_rooms_btn:
            self.get_rooms(force=True)

        room_choice = st.sidebar.selectbox("Choose a room", self.rooms, index=self.rooms.index(st.session_state['current_room']))
        if room_choice:
            self.select_render_room(room_choice)

        input = st.chat_input("Type your message:", key='new_message')

        if input:
            self.send_message(room_choice, input)
            st.rerun()

        time.sleep(0.9)
        st.rerun()


    def create_room_view(self):
        room_name = st.text_input("Room Name")
        submitted = st.button("Create", key="create_room_submit_btn")
        if submitted:
            logger.debug(f"Sending 'CREATE_ROOM' and room_name to server...")
            self.send_all(self.client_socket, f"CREATE_ROOM|{room_name}")
            logger.debug(f"CREATE_ROOM and room_name sent.")
            self.set_view('chat')
            st.rerun()


    def add_participants_view(self):
        if st.session_state['received_registered_users'] == False:
            self.send_all(self.client_socket, f"ADD_PARTICIPANTS|{st.session_state['current_room']}")
            registered_users = self.receive(self.client_socket).split("|")
            st.session_state['received_registered_users'] = True
            logger.debug(f"Received registered_users from server: {registered_users}")

        st.subheader(f"Add Participants to Room: {st.session_state['current_room']}")

        participants = st.multiselect("Add Users", registered_users)

        submitted = st.button("Add Participants")
        if submitted:
            participants = '|'.join(participants)
            self.send_all(self.client_socket, participants)
            logger.debug(f"Sent participants to server: {participants}")



            st.session_state['received_registered_users'] = False


        # self.send_all(self.client_socket, f"CREATE_ROOM")
        # logger.debug("Sent CREATE_ROOM command to server.")
        # registered_users = self.receive(self.client_socket).split("|")
        # logger.debug(f"Received registered_users from server: {registered_users}")

        # with st.form("Create Room", clear_on_submit=False, border=False):
        #     st.subheader("Create Room")
        #     room_name = st.text_input("Room Name")
        #     users = st.multiselect("Add Users", registered_users)
        #     users = '|'.join(users)
        #     submitted = st.form_submit_button("Create")

        #     if submitted:
        #         if (not room_name) or (not users):
        #             st.error("Please enter a username and password.")
        #         else:
        #             try:
        #                 logger.debug(f"Sending room_name and users to server...")
        #                 self.send_all(self.client_socket, f"{room_name}|{users}")
        #                 logger.debug(f"Getting response from server...")
        #                 response = self.receive(self.client_socket)
        #             except Exception as e:
        #                 logger.error(f"Exception: {e}")
        #                 self.client_socket.close()
        #                 st.rerun()

        #             if "successful" in response:
        #                 logger.debug(f"Server responded with successful: {response}")

        #             else:
        #                 logger.debug(f"Server responded with failed: {response}")

        #             st.rerun()
        #     else:
        #         st.stop()


    def listen_for_updates(self):
        try:
            listening_socket = self.create_socket()
            logger.debug("Created socket for listening and now listening...")
            logger.debug(f"self.user.listening_socket: {self.user.listening_socket}, listening_socket: {listening_socket}")
            self.user.listening_socket = listening_socket
            self.send_all(listening_socket, f"LISTEN|{self.user.username}")
            while True:
                msg = self.receive(listening_socket).split("|")
                action = msg[0]
                logger.debug(f"Received message with action: {action}")
                if action == "UPDATE":
                    logger.debug(f"Updating messages...")
                    room_name = msg[1]
                    author_username = msg[2]
                    message = msg[3]

                    if room_name == st.session_state['current_room']:
                        st.session_state['messages'].append(Message(room_name, author_username, message))
                        logger.debug(f"Setting st.session_state['new_messages'] = True...")
                        st.session_state['new_messages'] = True

                    # logger.debug(f"Rerunning...")
                    # st.rerun()
        
        except Exception as e:
            logger.debug(f"Exception: {e}")
            
    
    def send_message(self, room_name, input):
        msg = f"SEND_MESSAGE|{room_name}|{input}"
        self.send_all(self.client_socket, msg)
        logger.debug(f"Message sent: {msg}")

        response = self.receive(self.client_socket)
        logger.debug(f"Received response after sending Message: {response}")
        return
    

    def get_room_messages(self, room_name):
        serialized_messages = self.client_socket.recv(2048)
        messages = pickle.loads(serialized_messages)
        return messages


    def login(self):
        with st.form("login", clear_on_submit=False, border=False):
            st.subheader("Login")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")

        if submitted:
            if (not username) or (not password):
                st.error("Please enter a username and password.")
            else:
                try:
                    logger.debug(f"Sending 'LOGIN', username and password to server...")
                    self.send_all(self.client_socket, f"LOGIN|{username}|{password}")
                    logger.debug(f"Getting response from server...")
                    response = self.receive(self.client_socket)
                except Exception as e:
                    logger.error(f"Exception in login(): {e}")
                    self.cleanup_client_socket()
                    st.rerun()

                if "successful" in response:
                    logger.debug(f"Server responded with successful: {response}")
                    self.user = User(username, password, self.client_socket)
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['user'] = self.user
                    self.set_view('chat')

                else:
                    logger.debug(f"Server responded with failed: {response}")

                st.rerun()


    def register(self):
        with st.form("Register", clear_on_submit=False, border=False):
            st.subheader("Register")
            username = st.text_input("New Username")
            password = st.text_input("New Password", type="password")
            submitted = st.form_submit_button("Register")

        if submitted:
            if (not username) or (not password):
                st.error("Please enter a username and password.")
            else:
                try:
                    logger.debug(f"Sending 'REGISTER', username and password to server...")
                    self.send_all(self.client_socket, f"REGISTER|{username}|{password}")
                    logger.debug(f"Getting response from server...")
                    response = self.receive(self.client_socket)
                except Exception as e:
                    logger.error(f"Exception: {e}")
                    self.cleanup_client_socket()
                    st.rerun()

                if "successful" in response:
                    logger.debug(f"Server responded with successful: {response}")

                elif "failed" in response:
                    logger.debug(f"Server responded with failed: {response}")

                st.rerun()

            
    def logout(self):
        self.send_all(self.client_socket, "LOGOUT")
        try:    
            response = self.client_socket.recv(1024).decode('utf-8')
            logger.debug(f"Server response: {response}")
        except Exception as e:
            logger.error(f"Exeption occured: {e}\n")
        
        # close old socket and create a new one
        self.client_socket.close()

        self.manage_socket()

        st.session_state['logged_in'] = False
        st.session_state['username'] = ""
        st.session_state['user'] = None

        self.set_view('auth')

        st.rerun()


    def set_view(self, view):
        st.session_state['view'] = view


    def get_view(self):
        return st.session_state['view']


    def select_render_room(self, room_name):
        st.subheader(f"Room: {room_name}")

        self.send_all(self.client_socket, f"SELECT_ROOM|{room_name}")
        logger.debug(f"Sent action: SELECT_ROOM|{room_name}")

        response = self.receive(self.client_socket)
        if "SUCCESSFULLY" not in response:
            st.error("Access Denied!")

        else:
            st.session_state['current_room'] = room_name
            st.success("Successfully joined room!")
            room_messages = self.get_room_messages(room_name)
            room = Room(room_name)
            room.messages = room_messages

            st.session_state['new_messages'] = False

            with st.chat_message("user"):
                for message in room_messages:
                    st.markdown(f"**{message.author_name}** ({message.timestamp.strftime("%c")}): {message.text}")

        logger.debug(f"Received response after selecting Room: {response}")


    def get_rooms(self, force=False):
        if (st.session_state['got_rooms'] == False) or (force == True):
            try:
                self.send_all(self.client_socket, "SEND_ROOMS")
                logger.debug("Receiving rooms from server...")
                self.rooms = self.receive(self.client_socket).split("|")
                st.session_state['rooms'] = self.rooms
                st.session_state['got_rooms'] = True
                logger.debug(f"Received rooms from server: {self.rooms}")
            except Exception as e:
                logger.debug(f"Exception in chat _view(): {e}")
                self.cleanup_client_socket()
                self.set_view('auth')
                st.rerun()

    # CREATE AND RETURN A SOCKET
    def create_socket(self):
        logger.debug("Creating socket...")
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect((self.server_host, self.server_port))
            return client_socket
        except ConnectionRefusedError:
            st.error("Server is not available. Please start the server and try again.")
            logger.error("Server is not available. Please start the server and try again.")
            exit()


    def cleanup_client_socket(self):
        self.client_socket.close()
        self.client_socket = self.create_socket()


    # FOR SENDING MESSAGES
    def send_all(self, sock, msg):
        fullmsg = struct.pack("!i", len(msg)) + msg.encode()
        sock.sendall(fullmsg)


    # FOR RECEIVING MESSAGES
    def receive(self, sock):
        length = struct.unpack("!i", self.recv_all(sock, 4))[0]
        message = self.recv_all(sock, length).decode()
        return message
    

    # HELPER METHOD
    def recv_all(self, sock, length):
        data=""

        while len(data) < length:
            more = sock.recv(length - len(data)).decode()

            if not more:
                raise EOFError("Socket closed %d bytes into a %d-byte message" %(len(data), length))
            data += more
        
        return data.encode()


if __name__ == "__main__":
    Client()
