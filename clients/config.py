import os
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))


TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
CORE_API_URL = "http://localhost:8564/threads/{session_id}/runs"  # Sửa lại endpoint nếu cần
TIMEOUT = 120  # seconds
STREAM_TIMEOUT = 120  # seconds for streaming API
MONGO_URI=os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB=os.getenv("MONGO_DB", "impressox")