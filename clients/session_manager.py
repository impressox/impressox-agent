import uuid
import os
import logging
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# Ưu tiên lấy từ clients/config.py, nếu không có thì lấy từ biến môi trường hoặc mặc định
try:
    from clients.config import MONGO_URI, MONGO_DB
except ImportError:
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "impressox")

MONGO_COLLECTION = "user_sessions"

client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
sessions = db[MONGO_COLLECTION]

def get_session_id(platform: str, session_key: str) -> str:
    """
    Lấy session_id từ MongoDB theo platform và session_key.
    Nếu chưa có thì sinh mới, lưu vào Mongo và trả về.
    
    Args:
        platform: Platform identifier (e.g., "telegram", "discord", "x")
        session_key: Unique identifier for the session (e.g., user_id, chat_id, channel_id)
    """
    doc = sessions.find_one({"platform": platform, "session_key": session_key})
    if doc and "session_id" in doc:
        return doc["session_id"]
    session_id = str(uuid.uuid4())
    try:
        sessions.update_one(
            {"platform": platform, "session_key": session_key},
            {"$set": {"session_id": session_id}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error updating session_id for {platform}: {e}", exc_info=True)
    return session_id

def reset_session_id(platform: str, session_key: str) -> str:
    """
    Sinh session_id mới cho platform và session_key, lưu vào MongoDB.
    
    Args:
        platform: Platform identifier (e.g., "telegram", "discord", "x")
        session_key: Unique identifier for the session (e.g., user_id, chat_id, channel_id)
    """
    session_id = str(uuid.uuid4())
    try:
        sessions.update_one(
            {"platform": platform, "session_key": session_key},
            {"$set": {"session_id": session_id}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error updating session_id for {platform}: {e}", exc_info=True)
    return session_id
