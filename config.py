import logging


LOGGER_SETTINGS = {
    "format": "%(asctime)s  - %(levelname)s - %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
    "level": logging.INFO
}

BUFFER_SIZE = 30

FILEPATH = 'client.json'

MSG_LIMIT = 20

LIMIT_UPDATE_PERIOD = 60 * 60  # seconds

SIZE_LIMIT = 5000 * 1000  # bytes

TITLE = 'Server Chat API'
