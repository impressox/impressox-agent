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

def get_session_id(user_id: int, platform: str = "telegram") -> str:
    """
    Lấy session_id từ MongoDB theo user_id và platform.
    Nếu chưa có thì sinh mới, lưu vào Mongo và trả về.
    """
    doc = sessions.find_one({"platform": platform, "user_id": user_id})
    if doc and "session_id" in doc:
        return doc["session_id"]
    session_id = str(uuid.uuid4())
    try:
        sessions.update_one(
            {"platform": platform, "user_id": user_id},
            {"$set": {"session_id": session_id}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error updating session_id: {e}", exc_info=True)
    return session_id

def reset_session_id(user_id: int, platform: str = "telegram") -> str:
    """
    Sinh session_id mới cho user_id và platform, lưu vào MongoDB.
    """
    session_id = str(uuid.uuid4())
    try:
        sessions.update_one(
            {"platform": platform, "user_id": user_id},
            {"$set": {"session_id": session_id}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error updating session_id: {e}", exc_info=True)
    return session_id
