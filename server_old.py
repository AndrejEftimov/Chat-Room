import sys
import socket
import struct
import threading
import logging

# initialize logger for debugging
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.DEBUG) # DEBUG or ERROR

# registered users (username: password)
users = {
    'andrej': '123',
    'ivona': '123',
    'demijan': '123',
}

# logged in users
logged_in_users = {}

lock = threading.Lock()

def recv_all(sock, length):
    data=""

    while len(data) < length:
        more = sock.recv(length - len(data)).decode('utf-8')

        if not more:
            raise EOFError("Socket closed %d bytes into a %d-byte message" %(len(data), length))
        data += more
    
    return data.encode('utf-8')

def handle_client(client_socket, clients, addr, logged_in_users):
    i = -1
    while True:
        i+=1
        logger.debug(f"Iteration {i}")
        try:
            length = struct.unpack("!i", recv_all(client_socket, 4))[0]
            choice = recv_all(client_socket, length).decode('utf-8').lower().strip()
            logger.debug(f"Client chose: {choice}")
            username = None
            if choice == 'register':
                register(client_socket)
                continue

            elif choice == 'login':
                username = login(client_socket)
                if username == None:
                    logger.debug("login() returned 'None'\n")
                    continue

                elif username == False:
                    logger.debug("login() returned 'False'\n")
                    if client_socket in clients:
                        clients.remove(client_socket)
                    client_socket.close()

                elif username:
                    logger.debug(f"login() returned username: {username}")
                    broadcast(f"{username} has joined the chat.", client_socket, clients, logged_in_users)
                    logger.debug(f"{username} has joined the chat.")

                    while True:
                        try:
                            message = client_socket.recv(1024).decode('utf-8')
                            if message == "logout":
                                logout(username, client_socket, clients, logged_in_users)
                                return
                            else:
                                logger.debug(f"Received message from {username}: {message}")
                                broadcast(f"{username}: {message}", client_socket, clients, logged_in_users)
                        except Exception as e:
                            logger.error(f"Error receiving message: {e}")
                            logout(username, client_socket, clients, logged_in_users)
                            return

            else:
                client_socket.send("Invalid choice.\n".encode('utf-8'))
                continue


        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
            if client_socket in clients:
                clients.remove(client_socket)
            client_socket.close()

            if username:
                broadcast(f"{username} has left the chat.", None, clients, logged_in_users)
            break

def register(client_socket):
    try:
        length = struct.unpack("!i", recv_all(client_socket, 4))[0]
        username = recv_all(client_socket, length).decode('utf-8')
        logger.debug(f"Client entered new username: {username}")

        length = struct.unpack("!i", recv_all(client_socket, 4))[0]
        password = recv_all(client_socket, length).decode('utf-8')
        logger.debug(f"Client entered new password: {password}")
        
        if username in users:
            msg = "Registration failed! Username already exists!\n"
            fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
            client_socket.sendall(fullmsg)
            return False
            
        users[username] = password
        msg = f"Registration successful! You can now login with username '{username}'.\n"
        fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
        client_socket.sendall(fullmsg)
        print(f"New user registered: {username}")

        return True
    
    except Exception as e:
        # msg = f"Registration failed! Exception: {e}\n"
        # fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
        # client_socket.sendall(fullmsg)
        logger.error(f"Exception: {e}")
        return False

def login(client_socket):
    try:
        length = struct.unpack("!i", recv_all(client_socket, 4))[0]
        username = recv_all(client_socket, length).decode('utf-8')
        logger.debug(f"Client entered username: {username}")

        length = struct.unpack("!i", recv_all(client_socket, 4))[0]
        password = recv_all(client_socket, length).decode('utf-8')
        logger.debug(f"Client entered password: {password}")
        
        if ((not username) or (not password)) or (username not in users):
            msg = "Login failed.\n"
            fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
            client_socket.sendall(fullmsg)
            logger.debug("Login failed.")
            return None

        if users[username] == password:
            if username not in logged_in_users:
                logged_in_users.update({username: client_socket})
                msg = "Login successful!\n"
                fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
                client_socket.sendall(fullmsg)
                print("Login successful!")

                return username
            
            else:
                msg = "Login failed. User is already logged in.\n"
                fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
                client_socket.sendall(fullmsg)
                logger.debug("Login failed. User already logged in.")

                return None
        
        else:
            msg = "Login failed. Username and Password don't match.\n"
            fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
            client_socket.sendall(fullmsg)
            logger.debug("Login failed. Username and Password don't match.")
            return None
        
    except Exception as e:
        client_socket.send("Ran into exception server-side!".encode('utf-8'))
        logger.error(f"Ran into Exception: {e}")
        return False

def broadcast(message, sender_socket, clients, logged_in_users):
    print(f"Broadcasting message: {message}")
    for username, socket in logged_in_users.items():
        try:
            socket.send(message.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error sending message to client: {e}")
            with lock:
                logged_in_users.pop(username)
                if socket in clients:
                    clients.remove(socket)
                socket.close()

def logout(username, client_socket, clients, logged_in_users):
    print(f"{username} has disconnected.")
    client_socket.send(f"Logout successful!".encode('utf-8'))
    broadcast(f"{username} has left the chat.", client_socket, clients, logged_in_users)

    with lock:
        logged_in_users.pop(username)

    if client_socket in clients:
        clients.remove(client_socket)
    client_socket.close()

def main():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 5555))
    server_socket.listen(5)
    print("Server started on port 5555")
    
    # list of connected clients/sockets
    clients = []
    while True:
        client_socket, addr = server_socket.accept()
        print(f"Client connected: {addr}")
        clients.append(client_socket)
        client_thread = threading.Thread(target=handle_client, args=(client_socket, clients, addr, logged_in_users))
        client_thread.start()

if __name__ == "__main__":
    main()
