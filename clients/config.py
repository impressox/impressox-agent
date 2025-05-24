import os
from dotenv import load_dotenv
from typing import Dict

# Load environment variables
load_dotenv()

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Core API URL
CORE_API_URL = os.getenv("CORE_API_URL", "http://localhost:8564/threads/{session_id}/runs")

# DEX Aggregator URL
DEX_AGGREGATOR_URL = os.getenv("DEX_AGGREGATOR_URL", "http://localhost:42069/api")

# Supported chains configuration
# Format: "CHAIN_TYPE": chain_id
SUPPORTED_CHAINS: Dict[str, int] = {
    chain_type: int(chain_id)
    for chain_type, chain_id in [
        pair.split(':')
        for pair in os.getenv('SUPPORTED_CHAINS', 'EVM:1,SOLANA:1').split(',')
    ]
}

TIMEOUT = 120  # seconds
STREAM_TIMEOUT = 120  # seconds for streaming API
MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB=os.getenv("MONGO_DB", "cpx_dev")
REDIS_HOST=os.getenv("REDIS_HOST", "localhost")
REDIS_PORT=os.getenv("REDIS_PORT", 6379)
REDIS_PASSWORD=os.getenv("REDIS_PASSWORD", None)
REDIS_DB=os.getenv("REDIS_DB", 0)