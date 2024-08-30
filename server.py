import sys
import socket
import struct
import threading
import logging
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

          # all rooms room_name: Room
        self.rooms = {}
        self.broadcast_room = Room("Broadcast") # for broadcasting to all logged in users
        self.rooms[self.broadcast_room.name] = self.broadcast_room

        self.host = host
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.clients = []  # list to keep track of connected clients
        # registered users username: User
        self.registered_users = {
            "andrej": User("andrej", "123", None),
            "ivona": User("ivona", "123", None),
        }
        self.logged_in_users = {}  # dictionary to keep track of logged-in users, username: User
        self.lock = threading.Lock()

        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        print(f"Server started on {self.host}:{self.port}")

        self.run_server()

    def run_server(self):
        while True:
            client_socket, addr = self.server_socket.accept()
            print(f"Client connected: {addr}")
            self.clients.append(client_socket)
            client_thread = threading.Thread(target=self.handle_client, args=(client_socket, addr))
            client_thread.start()


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


    def handle_client(self, client_socket, addr):
        i = -1
        username = None
        while True:
            i += 1
            self.logger.debug(f"Iteration {i}")

            try:
                msg = self.receive(client_socket)
                action = msg.split("|")[0]
                self.logger.debug(f"Client chose action: {action}")
                
                if action == "REGISTER":
                    self.register(client_socket)
                    continue

                elif action == "LOGIN":
                    username = self.login(client_socket, msg)
                    if username:
                        self.on_login_success(username, client_socket)
                    elif username == None:
                        continue
                    else: # if username == False
                        if client_socket in self.clients:
                            self.clients.remove(client_socket)
                        client_socket.close()
                        break

            except Exception as e:
                self.logger.error(f"Exception in handle_client(): {e}")
                if client_socket in self.clients:
                    self.clients.remove(client_socket)
                client_socket.close()
                break



            # try:
            #     msg = self.receive(client_socket).strip()
            #     action = msg.split("|")[0]
            #     self.logger.debug(f"Client chose: {action}")
                
            #     if action == 'REGISTER':
            #         self.register(client_socket)
            #         continue

            #     elif action == 'LOGIN':
            #         username = self.login(client_socket, msg)

            #         if username == False:
            #             self.logger.debug("login() returned 'False'\n")
            #             if client_socket in self.clients:
            #                 self.clients.remove(client_socket)
            #             client_socket.close()
            #             break

            #         elif username:
            #             self.on_login_success(username, client_socket)
            #         else:
            #             continue

            # except Exception as e:
            #     self.logger.error(f"Error handling client {addr}: {e}")
            #     if client_socket in self.clients:
            #         self.clients.remove(client_socket)
            #     client_socket.close()
            #     break


    def on_login_success(self, username, client_socket):
        while True:
            msg = self.receive(client_socket)
            self.logger.debug(f"Received msg from client: {msg}")
            msg = msg.split("|")
            action = msg[0]
            if action == "SELECT_ROOM":
                self.logger.debug("Action chosen is SELECT_ROOM")
                room_name = msg[1]

                if (username not in self.rooms[room_name].participants) and room_name != "Broadcast":
                    self.send_all(client_socket, "Access Denied!")
                    continue

                self.logger.debug("Sending SUCCESSFULLY JOINED ROOM to client...")
                self.send_all(client_socket, "SUCCESSFULLY JOINED ROOM!")
                self.send_room_messages(client_socket, username, room_name)

            elif action == "SEND_MESSAGE":
                self.logger.debug("Action chosen is SEND_MESSAGE")
                room_name = msg[1]
                message = msg[2]
                self.logger.debug(f"Room name is '{room_name}', and message is '{message}'")
                
                if self.send_message_to_room(username, room_name, message):
                    self.logger.debug("Sending SUCCESSFULLY SENT MESSAGE to client...")
                    self.send_all(client_socket, "SUCCESSFULLY SENT MESSAGE!")

        # while True:
        #     self.logger.debug(f"Entered while loop...")
        #     try:
        #         message = self.receive(client_socket)
        #         if message == "LOGOUT":
        #             self.logout(username, client_socket)
        #             return
        #         elif "SELECT_ROOM" in message:
        #             room_name = message.split("|")[1]
        #             if room_name not in self.rooms:
        #                 self.send_all(client_socket, "FAILED. No such Room.")
        #                 continue

        #             if username not in self.rooms[room_name].participants:
        #                 self.send_all(client_socket, "FAILED. Access Denied.")
        #                 continue

        #             self.send_all(client_socket, "SUCCESS. You joined this Room!")

        #         else: # send a message
        #             self.send_message(client_socket, room_name, message)
                    
        #     except Exception as e:
        #         self.logger.error(f"Error receiving message: {e}")
        #         self.logout(username, client_socket)
        #         return
            
            
    def send_message_to_room(self, author_username, room_name, message):
        if not self.rooms[room_name]:
            return None
        
        if (author_username not in self.rooms[room_name].participants) and (room_name != "Broadcast"):
            return None
        
        messageObj = Message(room_name, author_username, message)
        self.rooms[room_name].messages.append(messageObj)

        for username in self.rooms[room_name].participants:
            if username in self.logged_in_users:
                self.send_all(self.logged_in_users[username].socket, "UPDATE")
                serialized_message = pickle.dumps(messageObj)
                self.logged_in_users[username].socket.sendall(serialized_message)

        return True
        

    def send_room_messages(self, client_socket, username, room_name):
        serialized_messages = pickle.dumps(self.rooms[room_name].messages)
        client_socket.sendall(serialized_messages)
        return


    def register(self, client_socket):
        try:
            length = struct.unpack("!i", self.recv_all(client_socket, 4))[0]
            username = self.recv_all(client_socket, length).decode()
            self.logger.debug(f"Client entered new username: {username}")

            length = struct.unpack("!i", self.recv_all(client_socket, 4))[0]
            password = self.recv_all(client_socket, length).decode()
            self.logger.debug(f"Client entered new password: {password}")

            if username in self.registered_users:
                msg = "Registration failed! Username already exists!\n"
                fullmsg = struct.pack("!i", len(msg)) + msg.encode()
                client_socket.sendall(fullmsg)
                return False

            self.registered_users[username] = password
            msg = f"Registration successful! You can now login with username '{username}'.\n"
            fullmsg = struct.pack("!i", len(msg)) + msg.encode()
            client_socket.sendall(fullmsg)
            print(f"New user registered: {username}")

            return True

        except Exception as e:
            # msg = f"Registration failed! Exception: {e}\n"
            # fullmsg = struct.pack("!i", len(msg)) + msg.encode()
            # client_socket.sendall(fullmsg)
            self.logger.error(f"Exception: {e}")
            return False


    def login(self, client_socket, msg):
        try:
            msg = msg.split("|")
            username = msg[1]
            password = msg[2]
            self.logger.debug(f"Client entered username: {username}, and password: {password}")

            if ((not username) or (not password)) or (username not in self.registered_users):
                self.logger.debug("Location 1")
                self.send_all(client_socket, "Login failed.\n")
                self.logger.debug("Login failed.")
                return None

            if self.registered_users[username].password == password:
                self.logger.debug("Location 2")
                if username not in self.logged_in_users:
                    self.logged_in_users[username] = User(username, password, client_socket)
                    self.send_all(client_socket, "Login successful!\n")
                    self.logger.debug("Login successful!")

                    return username
                
                else:
                    self.logger.debug("Location 3")
                    self.send_all(client_socket, "Login failed. User is already logged in.\n")
                    self.logger.debug("Login failed. User already logged in.")

                    return None
                
            else:
                self.logger.debug("Location 4")
                self.send_all(client_socket, "Login failed. Username and Password don't match.\n")
                self.logger.debug("Login failed. Username and Password don't match.")

                return None

        except Exception as e:
            self.send_all(client_socket, "Ran into exception server-side!")
            self.logger.error(f"Ran into Exception: {e}")
            self.logger.debug("Location 5")
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

        with self.lock:
            self.logged_in_users.pop(username)

        if client_socket in self.clients:
            self.clients.remove(client_socket)
        client_socket.close()


if __name__ == "__main__":
    server = Server()
    server.run_server()
