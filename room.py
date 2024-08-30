import sys
import threading
import logging

# initialize logger for debugging
logger = logging.getLogger(__name__)
#logger.addHandler(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.DEBUG) # DEBUG or ERROR

class Room:
    
    # room name
    name = None

    def __init__(self, name, participants=[]):
        self.name = name
        self.participants = participants
        self.messages = []

    def toJSON(self):
        return {
            "name": self.name,
            "participants": [part.toJSON() for part in self.participants],
        }
    