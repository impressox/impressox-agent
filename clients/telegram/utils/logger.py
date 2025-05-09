# utils/logger.py

import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime

# Get log level from environment variable, default to INFO
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.getenv("LOG_DIR", "logs")

# Create logs directory if it doesn't exist
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Configure logger
logger = logging.getLogger("telegram_bot")
logger.setLevel(getattr(logging, LOG_LEVEL))

# Create formatters
console_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
file_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
)

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(console_formatter)
logger.addHandler(console_handler)

# File handler with rotation
log_file = os.path.join(LOG_DIR, f"telegram_bot_{datetime.now().strftime('%Y%m%d')}.log")
file_handler = RotatingFileHandler(
    log_file,
    maxBytes=10*1024*1024,  # 10MB
    backupCount=5,
    encoding='utf-8'
)
file_handler.setFormatter(file_formatter)
logger.addHandler(file_handler)

# Prevent propagation to root logger
logger.propagate = False 