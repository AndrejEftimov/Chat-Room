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

    def __init__(self):
        logger.debug("Running __init__()...")

        self.rooms = ["Broadcast"] # rooms joined (names of rooms)

        if 'client_socket' not in st.session_state:
            st.session_state['client_socket'] = self.create_socket()
        self.client_socket = st.session_state['client_socket']

        st.title("Socket-based Chat Application")

        if 'logged_in' not in st.session_state:
            st.session_state['logged_in'] = False
            st.session_state['username'] = ""

        if not st.session_state['logged_in']:
            logger.debug("Entering auth_view()...")
            self.auth_view()
        else:
            if 'messages' not in st.session_state:
                st.session_state['messages'] = []

            if 'current_room' not in st.session_state:
                st.session_state['current_room'] = 'Broadcast'

            self.user = st.session_state['user']

            logger.debug("Entering chat_view()...")
            self.chat_view()


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
    

    def auth_view(self):
        st.sidebar.title("Login/Registration")
        action = st.sidebar.selectbox("Choose Action", ["Login", "Register"])

        if action == "Login":
            self.login()

        elif action == "Register":
            self.register()


    def chat_view(self):
        st.sidebar.title("Chat Rooms")

        room_choice = st.sidebar.selectbox("Choose a room", self.rooms, index=self.rooms.index(st.session_state['current_room']))
        if room_choice:
            update_thread = threading.Thread(target=self.listen_for_updates)
            update_thread.start()

            st.subheader(f"{room_choice} Room:")

            self.send_all(self.client_socket, f"SELECT_ROOM|{room_choice}")
            logger.debug(f"Sent action: SELECT_ROOM|{room_choice}")

            response = self.receive(self.client_socket)
            if "SUCCESSFULLY" not in response:
                st.error("Access Denied!")

            else:
                st.session_state['current_room'] = room_choice
                st.success("Successfully joined room!")
                room_messages = self.get_room_messages(room_choice)
                room = Room(room_choice)
                room.messages = room_messages

                with st.chat_message("user"):
                    for message in room_messages:
                        st.markdown(f"**{message.author_name}** ({message.timestamp.strftime("%c")}): {message.text}")

            logger.debug(f"Received response after selecting Room: {response}")

        input = st.chat_input("Type your message:", key='new_message')

        if input:
            self.send_message(room_choice, input)
            st.rerun()

        # self.listen_for_updates()


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

                    logger.debug(f"Rerunning...")
                    st.rerun()
        
        except Exception as e:
            logger.debug(f"Exception: {e}")
            
    
    def send_message(self, room_name, input):
        msg = f"SEND_MESSAGE|{room_name}|{input}"
        self.send_all(self.client_socket, msg)
        logger.debug("Message sent.")

        response = self.receive(self.client_socket)
        logger.debug(f"Received response after sending Message: {response}")
        return
    

    def get_room_messages(self, room_name):
        serialized_messages = self.client_socket.recv(1024)
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
                    logger.debug(f"Sending 'login', username and password to server...")
                    self.send_all(self.client_socket, f"LOGIN|{username}|{password}")
                    logger.debug(f"Getting response from server...")
                    response = self.receive(self.client_socket)
                except Exception as e:
                    logger.error(f"Exception: {e}")
                    self.client_socket.close()
                    st.rerun()

                if "successful" in response:
                    logger.debug(f"Server responded with successful: {response}")
                    self.user = User(username, password, self.client_socket)
                    st.session_state['logged_in'] = True
                    st.session_state['username'] = username
                    st.session_state['user'] = self.user

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
                    self.send_all(self.client_socket, "register")
                    self.send_all(self.client_socket, username)
                    self.send_all(self.client_socket, password)
                    response = self.receive(self.client_socket)
                except Exception as e:
                    logger.error(f"Exception: {e}")
                    self.client_socket.close()
                    st.rerun()

                if "failed" in response:
                    self.client_socket.close()

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
        self.client_socket = self.create_socket()


if __name__ == "__main__":
    Client()
