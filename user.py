import sys
import threading
import logging

logger = logging.getLogger(__name__)
#logger.addHandler(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.DEBUG) # DEBUG or ERROR

class User:

    username = None # Unique (PK)
    password = None
    socket = None
    listening_socket = None
    address = None

    def __init__(self, username, password, socket=None, listening_socket=None, address=None):
        self.username = username
        self.password = password
        self.socket = socket
        self.listening_socket = listening_socket
        self.address = address

    def toJSON(self):
        return {
            "uid": self.uid,
            "username": self.username,
            "password": self.password
        }