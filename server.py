import sys
import socket
import struct
import threading
import logging
import traceback
from user import User
from room import Room
from message import Message
import json
import pickle

class Server:

    def __init__(self, host='0.0.0.0', port=5555):
        # initialize logger for debugging
        self.logger = logging.getLogger(__name__)
        #self.logger.addHandler(logging.StreamHandler(sys.stdout))
        logging.basicConfig(level=logging.DEBUG) # DEBUG or ERROR

        self.lock = threading.Lock()

        self.allocate_resources()

        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(10)
        print(f"Server started on {self.host}:{self.port}")

        self.run_server()


    def allocate_resources(self):
        self.rooms = {}
        self.broadcast_room = Room("Broadcast") # for broadcasting to all logged in users
        self.rooms[self.broadcast_room.name] = self.broadcast_room

        self.clients = []  # list to keep track of connected clients
        # registered users username: User
        self.registered_users = {
            "andrej": User("andrej", "123", None),
            "ivona": User("ivona", "123", None),
            "demijan": User("demijan", "123", None),
        }

        self.logged_in_users = {}  # dictionary to keep track of logged-in users, username: User


    def run_server(self):
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Client connected: {addr}")
            self.clients.append(client_socket)
            client_thread = threading.Thread(target=self.handle_auth, args=(client_socket, addr))
            client_thread.start()


    def handle_auth(self, client_socket, addr):
        while True:
            self.logger.debug(f"In while in handle_auth()...")
            try:
                msg = self.receive(client_socket)
                action = msg.split("|")[0]
                self.logger.debug(f"Client chose action: {action}")
                
                if action == "REGISTER":
                    self.register(client_socket, msg, addr)
                    continue

                elif action == "LOGIN":
                    username = self.login(client_socket, msg, addr)
                    if username:
                        self.on_login_success(username, client_socket)
                        break
                    elif username == None:
                        continue
                    else:#if username == False
                        self.cleanup_client(client_socket)
                        break

                elif action == "LISTEN":
                    username = msg.split("|")[1]
                    self.logged_in_users[username].listening_socket = client_socket


            except Exception as e:
                self.logger.error("Exception in handle_auth():")
                self.logger.exception(e)
                self.logout(username, client_socket)
                break


    def on_login_success(self, username, client_socket):
        while True:
            try:
                msg = self.receive(client_socket).split("|")
                self.logger.debug(f"Received msg from client: {msg}")
                action = msg[0]
                if action == "SEND_ROOMS":
                    self.send_rooms(username, client_socket)

                elif action == "SELECT_ROOM":
                    self.select_room(client_socket, username, msg)

                elif action == "SEND_MESSAGE":
                    self.send_message(client_socket, username, msg)

                elif action == "LOGOUT":
                    self.logout(username, client_socket)
                    break
                
                elif action == "CREATE_ROOM":
                    self.create_room(username, client_socket, msg)

                elif action == "ADD_PARTICIPANTS":
                    self.add_participants(username, client_socket, msg)
                    
            except Exception as e:
                self.logger.error("Exception in on_login_success():")
                traceback.print_exception(e)
                self.logout(username, client_socket)
                break


    def select_room(self, client_socket, username, msg):
        room_name = msg[1]
        if (username not in self.rooms[room_name].participants) and room_name != "Broadcast":
            self.send_all(client_socket, "Access Denied!")
            return

        self.logger.debug("Sending SUCCESSFULLY JOINED ROOM to client...\n")
        self.send_all(client_socket, "SUCCESSFULLY JOINED ROOM!")
        self.send_room_messages(client_socket, username, room_name)


    def send_message(self, client_socket, username, msg):
        try:
            room_name = msg[1]
            message = msg[2]
            self.logger.debug(f"Room name is '{room_name}', and message is '{message}'")
            
            if self.send_message_to_room(username, room_name, message):
                self.logger.debug("Sending SUCCESSFULLY SENT MESSAGE to client...")
                self.send_all(client_socket, "SUCCESSFULLY SENT MESSAGE!")

                
        except Exception as e:
            self.logger.error(f"Exception in send_message(): {e}")


    def create_room(self, username, client_socket, msg):
        room_name = msg[1]
        self.logger.debug(f"Received room_name: {room_name} from client and now creating room...")
        if room_name not in self.rooms:
            self.rooms[room_name] = Room(room_name, [username])
            self.logger.debug("Room created successfully.\n")


    def add_participants(self, username, client_socket, msg):
        try:
            room_name = msg[1]

            registered_users = self.registered_users
            for participant in self.rooms[room_name].participants:
                registered_users.pop(participant)

            registered_users_str = "|".join(registered_users)
            self.send_all(client_socket, registered_users_str)

            new_participants = self.receive(client_socket).split("|")
            self.logger.debug(f"Received new participants from user: {new_participants}")

            for participant in new_participants:
                self.rooms[room_name].participants.append(participant)

        except Exception as e:
            self.logger.error(f"Exception in add_participants(): {e}")
        
        
            
    def send_message_to_room(self, author_username, room_name, message):
        if not self.rooms[room_name]:
            return None
        
        if (author_username not in self.rooms[room_name].participants) and (room_name != "Broadcast"):
            return None
        
        messageObj = Message(room_name, author_username, message)
        self.rooms[room_name].messages.append(messageObj)

        for username in self.rooms[room_name].participants:
            if username in self.logged_in_users:
                pass
                # self.send_all(self.logged_in_users[username].listening_socket, f"UPDATE|{room_name}|{author_username}|{message}")
                # serialized_message = pickle.dumps(messageObj)
                # self.logged_in_users[username].socket.sendall(serialized_message)

        return True
        

    def send_room_messages(self, client_socket, username, room_name):
        serialized_messages = pickle.dumps(self.rooms[room_name].messages)
        client_socket.sendall(serialized_messages)
        return
    

    def login(self, client_socket, msg, addr):
        try:
            msg = msg.split("|")
            username = msg[1]
            password = msg[2]
            self.logger.debug(f"Client entered username: {username}, and password: {password}")

            if ((not username) or (not password)):
                self.send_all(client_socket, "Login failed. Username and Password are required fields!\n")
                self.logger.debug("Login failed. Username and Password are required fields!\n")
                return None
            
            elif username not in self.registered_users:
                self.send_all(client_socket, "Login failed. User not found!\n")
                self.logger.debug("Login failed. User not found!\n")
                return None

            if self.registered_users[username].password == password:
                if username not in self.logged_in_users:
                    self.logged_in_users[username] = User(username, password, socket=client_socket, address=addr)
                    self.send_all(client_socket, "Login successful!\n")
                    self.logger.debug("Login successful!\n")
                    return username
                
                else:
                    self.send_all(client_socket, "Login failed. User is already logged in.\n")
                    self.logger.debug("Login failed. User already logged in.\n")
                    return None
                
            else:
                self.send_all(client_socket, "Login failed. Username and Password don't match.\n")
                self.logger.debug("Login failed. Username and Password don't match.\n")
                return None

        except Exception as e:
            self.send_all(client_socket, "Login failed. Ran into exception server-side!")
            self.logger.error(f"Ran into Exception during login(): {e}")
            return False


    def register(self, client_socket, msg, addr):
        try:
            msg = msg.split("|")
            username = msg[1]
            password = msg[2]
            self.logger.debug(f"Client entered new username: {username}, and new password: {password}")

            if ((not username) or (not password)):
                self.send_all(client_socket, "Login failed. Username and Password are required fields!\n")
                self.logger.debug("Login failed. Username and Password are required fields!\n")
                return None

            if username not in self.registered_users:
                self.registered_users[username] = User(username, password, socket=client_socket, address=addr)
                self.send_all(client_socket, "Registration successful!\n")
                self.logger.debug("Registration successful!\n")
                return username

        except Exception as e:
            self.send_all(client_socket, "Registration failed. Ran into exception server-side!")
            self.logger.error(f"Ran into Exception during register(): {e}")
            return False


    def broadcast(self, message):
        print(f"Broadcasting message: {message}")
        for username, user in self.logged_in_users.items():
            try:
                user.socket.send(message.encode())
                return True
            except Exception as e:
                self.logger.error(f"Error sending message to client: {e}")
                with self.lock:
                    self.logged_in_users.pop(username)
                    if socket in self.clients:
                        self.clients.remove(socket)
                    socket.close()
                return False


    def logout(self, username, client_socket):
        print(f"{username} has disconnected.")
        client_socket.send(f"Logout successful!".encode())
        self.broadcast(f"{username} has left the chat.")

        if username:
            with self.lock:
                self.logged_in_users.pop(username)

        self.cleanup_client(client_socket)


    def send_rooms(self, username, client_socket):
        try:
            rooms = ''
            for room_name, room in self.rooms.items():
                if (username in room.participants) or (room_name == "Broadcast"):
                    rooms += f"|{room_name}"
            
            rooms = rooms.strip("|")
            self.logger.debug(f"Sending rooms ({rooms}) to user...")
            self.send_all(client_socket, rooms)

        except Exception as e:
            self.logger.error(f"Exception in send_rooms(): {e}")


    def cleanup_client(self, client_socket):
        if client_socket in self.clients:
            self.clients.remove(client_socket)
        client_socket.close()


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
    server = Server()
    server.run_server()
