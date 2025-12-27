"""
Utkarsh Telegram Bot - Configuration
Supports both local config and Render environment variables
"""

import os

# Telegram API credentials
# For Render: Set these as environment variables
# For local: Edit values below
API_ID = int(os.getenv("API_ID", "22984163"))
API_HASH = os.getenv("API_HASH", "18c3760d602be96b599fa42f1c322956")
BOT_TOKEN = os.getenv("BOT_TOKEN", "8213629280:AAFdjRCTn2RlNr8JkIo-f8wA5anhav6AW_k")

# Admin user IDs (comma-separated in env var)
_admin_ids_str = os.getenv("ADMIN_IDS", "915101089")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_str.split(",")]

# Download settings
DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "./downloads")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "2000"))
PARALLEL_DOWNLOADS = int(os.getenv("PARALLEL_DOWNLOADS", "3"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "8"))

# Destination for uploads (channel ID or 0 for personal chat)
# For channel: use channel ID like -1001234567890
# For personal: use 0 (sends to whoever started the download)
DESTINATION_CHAT_ID = int(os.getenv("DESTINATION_CHAT_ID", "0"))

# Utkarsh credentials
UTKARSH_USERNAME = os.getenv("UTKARSH_USERNAME", "7973933527")
UTKARSH_PASSWORD = os.getenv("UTKARSH_PASSWORD", "A1234S12")
