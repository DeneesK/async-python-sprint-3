import logging


LOGGER_SETTINGS = {
    "format": "%(asctime)s  - %(levelname)s - %(message)s",
    "datefmt": "%Y-%m-%d %H:%M:%S",
    "level": logging.INFO
}

logging.basicConfig(**LOGGER_SETTINGS)
