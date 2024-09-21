import sys
import socket
import struct
import threading
import logging
import tkinter as tk
from tkinter import simpledialog, scrolledtext, messagebox

logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.ERROR)

class MyGUI:
    def __init__(self):
        self.client_socket = self.create_socket()

        self.root = tk.Tk()

        self.DIMENSIONS = "1200x900"
        self.root.geometry(self.DIMENSIONS)

        self.root.title("Chat Room")

        self.label_welcome = tk.Label(self.root, text="Welcome to the chat room!", font=('Bahnschrift', 18))
        self.label_welcome.pack(padx=10, pady=10)
        self.label_rules = tk.Label(self.root, text="(Rules: Be nice, don't spam, and have fun (^^) )", font=('Bahnschrift', 16))
        self.label_rules.pack(padx=10, pady=10)
        
        self.message_display = scrolledtext.ScrolledText(self.root, state=tk.DISABLED, wrap=tk.WORD, font=('Bahnschrift', 14))
        self.message_display.pack(padx=10, pady=10, fill=tk.BOTH)
        
        self.message_entry = tk.Entry(self.root, font=('Bahnschrift', 14))
        self.message_entry.pack(padx=10, pady=10, ipadx=150)

        self.send_button = tk.Button(self.root, text="Send", font=('Bahnschrift', 18), state=tk.DISABLED, command=lambda: self.send_message(self.client_socket, self.message_entry))
        self.send_button.pack(padx=10, pady=10)

        self.login_button = tk.Button(self.root, text="Login", font=('Bahnschrift', 18), command=lambda: self.login(self.client_socket, self.root, self.message_display, self.send_button))
        self.login_button.pack(padx=10, pady=5, side=tk.RIGHT)
        
        self.register_button = tk.Button(self.root, text="Register", font=('Bahnschrift', 18), command=lambda: self.register())
        self.register_button.pack(padx=10, pady=5, side=tk.RIGHT)

        self.logout_button = tk.Button(self.root, text="Logout", font=('Bahnschrift', 18), state=tk.DISABLED, command=lambda: self.logout())
        self.logout_button.pack(padx=10, pady=5, side=tk.RIGHT)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.root.mainloop()

    def recv_all(self, sock, length):
        data=""

        while len(data) < length:
            more = sock.recv(length - len(data)).decode('utf-8')

            if not more:
                raise EOFError("Socket closed %d bytes into a %d-byte message" %(len(data), length))
            data += more
        
        return data.encode('utf-8')
    
    def create_socket(self):
        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_socket.connect(('127.0.0.1', 5555))
            return client_socket
        except ConnectionRefusedError:
            logger.error("Server is not available. Please start the server and try again.")
            exit()

    def on_close(self):
        if messagebox.askyesno(title="Quit?", message="Do you really want to quit?"):
            self.root.destroy()

    def receive_messages(self, client_socket, message_display):
        while True:
            try:
                message = client_socket.recv(1024).decode('utf-8')
                if message:
                    if "logout" in message.lower().strip():
                        message_display.delete(0, tk.END)
                        logger.debug("Breaking from receive_messages() loop and exiting method...")
                        break
                    else:
                        message_display.config(state=tk.NORMAL)
                        message_display.insert(tk.END, message + "\n")
                        message_display.config(state=tk.DISABLED)
                        message_display.yview(tk.END)

            except Exception as e:
                logger.error(f"Error receiving message: {e}")
                logger.error("Closing connection to server...")
                client_socket.close()
                break

    def send_message(self, client_socket, message_entry):
        message = message_entry.get()
        if message:
            client_socket.send(message.encode('utf-8'))
            message_entry.delete(0, tk.END)

    def register(self):
        username = simpledialog.askstring("Register", "Enter your new username:", )
        logger.debug(f"Entered username {username}")
        password = simpledialog.askstring("Register", "Enter your new password:", show='*')
        logger.debug(f"Entered password {password}")

        if (not username) or (not password):
            messagebox.showinfo(title="Error", message="Username and Password are required fields!")
            return

        logger.debug("Sending 'register' to server...\n")
        msg = "register"
        fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
        self.client_socket.sendall(fullmsg)

        logger.debug("Sending new username and new password to server...\n")
        fullmsg = struct.pack("!i", len(username)) + username.encode('utf-8')
        self.client_socket.sendall(fullmsg)
        fullmsg = struct.pack("!i", len(password)) + password.encode('utf-8')
        self.client_socket.sendall(fullmsg)

        try:
            logger.debug("Getting response from server...")
            logger.debug(f"client_socket: {self.client_socket}\n")
            length = struct.unpack("!i", self.recv_all(self.client_socket, 4))[0]
            response = self.recv_all(self.client_socket, length).decode('utf-8')
            logger.debug(f"Server response: {response}")
        except Exception as e:
            logger.error(f"Exception: {e}")
            self.client_socket.close()
            return
        
        if "successful" in response:
            messagebox.showinfo(title="Success", message="User created successfully!")
            return True
        elif "failed" in response:
            messagebox.showinfo(title="Failure", message="Registration failed!")
            return False
        
        return None

    def login(self, client_socket, root, message_display, send_button):
        username = simpledialog.askstring("Login", "Enter your username:", )
        logger.debug(f"Entered username {username}")
        password = simpledialog.askstring("Login", "Enter your password:", show='*')
        logger.debug(f"Entered password {password}")
        
        if (not username) or (not password):
            messagebox.showinfo(title="Error", message="Username and Password are required fields!")
            return

        logger.debug("Sending 'login' to server...\n")
        msg = "login"
        fullmsg = struct.pack("!i", len(msg)) + msg.encode('utf-8')
        client_socket.sendall(fullmsg)

        logger.debug("Sending username and password to server...\n")
        fullmsg = struct.pack("!i", len(username)) + username.encode('utf-8')
        client_socket.sendall(fullmsg)
        fullmsg = struct.pack("!i", len(password)) + password.encode('utf-8')
        client_socket.sendall(fullmsg)

        try:
            logger.debug("Getting response from server...")
            logger.debug(f"client_socket: {client_socket}\n")
            length = struct.unpack("!i", self.recv_all(client_socket, 4))[0]
            response = self.recv_all(client_socket, length).decode('utf-8')
            logger.debug(f"Server response: {response}")
            messagebox.showinfo(title="Server Response", message=response)
        except Exception as e:
            logger.error(f"Exception: {e}")
            self.client_socket.close()
            return

        if "successful" in response:
            self.send_button.config(state=tk.NORMAL)
            self.login_button.config(state=tk.DISABLED)
            self.register_button.config(state=tk.DISABLED)
            self.logout_button.config(state=tk.NORMAL)

            self.receive_thread = threading.Thread(target=self.receive_messages, args=(self.client_socket, self.message_display))
            self.receive_thread.start()

            return True
        
        elif "failed" in response:
            return False
        else:
            return None
            
    def logout(self):
        self.client_socket.send("logout".encode('utf-8'))
        try:    
            response = self.client_socket.recv(1024).decode('utf-8')
            logger.debug(f"Server response: {response}")
        except Exception as e:
            logger.error(f"Exeption occured: {e}\n")
        
        # close old socket and create a new one
        self.client_socket.close()
        self.client_socket = self.create_socket()

        # clear the message_display
        self.message_display.config(state=tk.NORMAL)
        self.message_display.delete(1.0, tk.END)
        self.message_display.config(state=tk.DISABLED)
        self.root.deiconify()

        # change button visibility
        logger.debug("Changing button states...")
        self.send_button.config(state=tk.DISABLED)
        self.login_button.config(state=tk.NORMAL)
        self.register_button.config(state=tk.NORMAL)
        self.logout_button.config(state=tk.DISABLED)



if __name__ == "__main__":
    MyGUI()
