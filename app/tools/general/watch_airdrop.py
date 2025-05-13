import json
import time
import uuid
import asyncio
from typing import List, Dict, Optional, Any
from bson import ObjectId
import logging
from functools import partial

from app.utils.call_api import call_api 
from app.cache.cache_redis import get_redis_client
from app.cache.rule_storage import RuleStorage
from app.constants import NodeName
from app.configs import app_configs
from app.core.tool_registry import register_tool

from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB objects"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def generate_rule_id() -> str:
    """Generate unique rule ID"""
    return f"r_{uuid.uuid4().hex[:8]}"

def get_notify_id(user_id: str, app: str, conversation_id: str = None, chat_type: str = None) -> str:
    """Get notification ID based on user and app"""
    # For Telegram
    if app == "telegram":
        # If it's a group chat, always use conversation_id (group chat ID)
        if chat_type in ["group", "supergroup"]:
            return conversation_id
        # For private chat, use user_id
        return user_id
    # For other apps, use user_id
    return user_id

@register_tool(NodeName.GENERAL_NODE, "watch_airdrop")
@tool
async def watch_airdrop(tokens: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Tool để đăng ký theo dõi thông tin về airdrop của một hoặc nhiều token/dự án.
    Hệ thống sẽ thông báo khi có thông tin mới về airdrop từ các dự án được theo dõi.

    Args:
        tokens: Danh sách các token symbol hoặc tên dự án muốn theo dõi (ví dụ: ["ETH", "BTC", "LayerZero", ...]).
               Nếu không truyền sẽ theo dõi tất cả các dự án có tiềm năng airdrop.
    Returns:
        Dict với trạng thái và thông báo kết quả đăng ký theo dõi.
    """
    try:
        return await _watch_airdrop_async(tokens, runable_config)
    except Exception as e:
        logger.error(f"[WatchAirdrop] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi xử lý yêu cầu: {str(e)}"
        }

async def _watch_airdrop_async(tokens: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Async implementation of watch_airdrop tool (không xác thực token trên CoinGecko)
    """
    user_id = runable_config["configurable"].get("user_id", "")
    user_name = runable_config["configurable"].get("user_name", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)

    # Nếu không truyền tokens thì mặc định theo dõi tất cả
    if not tokens:
        tokens = ["*"]

    rule = {
        "rule_id": generate_rule_id(),
        "user_id": str(user_id),
        "user_name": user_name,
        "watch_type": "airdrop",
        "target": tokens,
        "target_data": {},
        "notify_channel": app,
        "notify_id": get_notify_id(user_id, app, conversation_id, runable_config["configurable"].get("chat_type")),
        "metadata": {
            "conversation_id": conversation_id,
            "chat_type": runable_config["configurable"].get("chat_type"),
            "created_at": time.time(),
            "watch_airdrop": True
        },
        "active": True
    }

    try:
        storage = await RuleStorage.get_instance()
        logger.info(f"[WatchAirdrop] Saving rule to MongoDB: {json.dumps(rule, cls=MongoJSONEncoder)}")
        if not await storage.save_rule(rule):
            logger.error("[WatchAirdrop] Failed to save rule to MongoDB")
            return {
                "success": False,
                "message": "Lỗi khi lưu rule vào database"
            }
        logger.info(f"[WatchAirdrop] Successfully saved rule {rule['rule_id']} to MongoDB")
    except Exception as e:
        logger.error(f"[WatchAirdrop] Error connecting to MongoDB: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi kết nối database: {str(e)}"
        }

    try:
        redis = get_redis_client()
        channel = "airdrop_watch:register_rule"
        logger.info(f"[WatchAirdrop] Publishing rule to Redis channel {channel}")
        if not redis.publish(channel, json.dumps(rule, cls=MongoJSONEncoder)):
            await storage.deactivate_rule(rule["rule_id"])
            return {
                "success": False,
                "message": "Lỗi khi đăng ký rule vào Redis"
            }
        logger.info(f"[WatchAirdrop] Successfully published rule {rule['rule_id']} to Redis")
    except Exception as e:
        await storage.deactivate_rule(rule["rule_id"])
        logger.error(f"[WatchAirdrop] Error connecting to Redis: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi kết nối Redis: {str(e)}"
        }

    if tokens == ["*"]:
        msg = "Đã đăng ký theo dõi tất cả các dự án có tiềm năng airdrop"
    else:
        msg = f"Đã đăng ký theo dõi airdrop cho: {', '.join(tokens)}"

    return {
        "success": True,
        "message": msg,
        "rule": rule
    } 