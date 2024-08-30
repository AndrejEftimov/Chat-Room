import sys
import logging
from datetime import datetime

# initialize logger for debugging
logger = logging.getLogger(__name__)
#logger.addHandler(logging.StreamHandler(sys.stdout))
logging.basicConfig(level=logging.DEBUG) # DEBUG or ERROR

class Message:

    def __init__(self, room_name, author_name, text):
        self.room_name = room_name
        self.timestamp = datetime.now()
        self.author_name = author_name
        self.text = text
        
    