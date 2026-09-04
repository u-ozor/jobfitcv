
# app/logging/logging_config.py

import logging

from logging.handlers import (
    RotatingFileHandler
)

import os


LOG_DIR = "logs"

os.makedirs(
    LOG_DIR,
    exist_ok=True
)

LOG_PATH = os.path.join(
    LOG_DIR,
    "app.log"
)


def setup_logging():

    logger = logging.getLogger()

    logger.setLevel(logging.INFO)

    if logger.handlers:
        return logger

    handler = RotatingFileHandler(
        LOG_PATH,
        maxBytes=1_000_000,
        backupCount=5,
        encoding="utf-8"
    )

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s - %(message)s"
    )

    handler.setFormatter(
        formatter
    )

    logger.addHandler(
        handler
    )

    return logger