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

# Global event loop for database operations
_db_loop = None

def get_db_loop():
    """Get or create database event loop"""
    global _db_loop
    if _db_loop is None or _db_loop.is_closed():
        _db_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_db_loop)
    return _db_loop

def run_async(coro):
    """Run coroutine in database event loop"""
    loop = get_db_loop()
    return loop.run_until_complete(coro)

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

@register_tool(NodeName.GENERAL_NODE, "watch_market")
@tool
def watch_market(tokens: Optional[List[str]] = None, conditions: Optional[Dict] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Tool để đăng ký theo dõi biến động của một hoặc nhiều token (ví dụ: giá, volume, tin tức, sự kiện). 
    Khi có thay đổi liên quan đến các token này, hệ thống sẽ chủ động thông báo cho bạn qua kênh đã kết nối (Telegram, Web, Discord).

    Args:
        tokens: Danh sách các token symbol muốn theo dõi (ví dụ: ["ETH", "BTC"]). 
               Nếu không truyền sẽ mặc định theo dõi các token phổ biến.
        conditions: Điều kiện theo dõi (ví dụ: {"gt": 3000} để theo dõi khi giá > 3000).
                   Nếu không có điều kiện -> theo dõi mọi thay đổi.
    Returns:
        Dict với trạng thái và thông báo kết quả đăng ký theo dõi.
    """
    try:
        return run_async(_watch_market_async(tokens, conditions, runable_config))
    except Exception as e:
        logger.error(f"[WatchMarket] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi xử lý yêu cầu: {str(e)}"
        }

async def _watch_market_async(tokens: Optional[List[str]] = None, conditions: Optional[Dict] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Async implementation of watch_market tool
    """
    # Get context values
    user_id = runable_config["configurable"].get("user_id", "")
    user_name = runable_config["configurable"].get("user_name", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)

    if not tokens:
        tokens = ["BTC", "ETH", "BNB", "SOL", "XRP"]
        return {
            "success": True,
            "message": f"Mặc định tôi sẽ theo dõi các token này: {', '.join(tokens)}"
        }

    # Verify tokens on CoinGecko
    valid_tokens = []
    invalid_tokens = []
    
    coingecko_url = app_configs.API_CONF["coingecko"]["url"]
    coingecko_api_key = app_configs.API_CONF["coingecko"]["api_key"]
    headers = {"x-cg-demo-api-key": coingecko_api_key} if coingecko_api_key else {}
    
    for token in tokens:
        # Search for the token
        search_url = f"/search?query={token}"
        search_result = await call_api(
            f"{coingecko_url}{search_url}", 
            method="GET",
            headers=headers
        )
        
        if search_result["success"] and "coins" in search_result["data"] and search_result["data"]["coins"]:
            coin_data = search_result["data"]["coins"][0]
            # Check if the found token exactly matches user input
            exact_match = (
                coin_data["symbol"].upper() == token.upper() or 
                coin_data["name"].lower() == token.lower()
            )
            
            if not exact_match:
                return {
                    "success": True,
                    "message": f"Tôi tìm thấy token '{coin_data['name']} ({coin_data['symbol']})' cho từ khóa '{token}'. Bạn có muốn theo dõi token này không?",
                    "confirm": {
                        "token": token,
                        "found_token": {
                            "symbol": coin_data["symbol"].upper(),
                            "id": coin_data["id"],
                            "name": coin_data["name"]
                        }
                    }
                }
            
            valid_tokens.append({
                "symbol": coin_data["symbol"].upper(),
                "id": coin_data["id"],
                "name": coin_data["name"]
            })
        else:
            invalid_tokens.append(token)

    if not valid_tokens:
        return {
            "success": False,
            "message": f"Không tìm thấy tokens: {', '.join(tokens)}"
        }

    # Create watch rule
    rule = {
        "rule_id": generate_rule_id(),
        "user_id": str(user_id),  # Convert to string to avoid ObjectId
        "user_name": user_name,
        "watch_type": "token",
        "target": [t["symbol"] for t in valid_tokens],
        "target_data": {
            t["symbol"]: {
                "symbol": t["symbol"],
                "name": t["name"],
                "coin_gc_id": t["id"]  # Add CoinGecko ID
            } for t in valid_tokens
        },  # Store additional token data with CoinGecko IDs
        "condition": conditions or {"type": "any"},
        "notify_channel": app,
        "notify_id": get_notify_id(user_id, app, conversation_id, runable_config["configurable"].get("chat_type")),
        "metadata": {
            "conversation_id": conversation_id,
            "chat_type": runable_config["configurable"].get("chat_type"),
            "created_at": time.time()
        },
        "active": True
    }

    # Save rule to MongoDB
    try:
        storage = await RuleStorage.get_instance()
        logger.info(f"[WatchMarket] Saving rule to MongoDB: {json.dumps(rule, cls=MongoJSONEncoder)}")
        if not await storage.save_rule(rule):
            logger.error("[WatchMarket] Failed to save rule to MongoDB")
            return {
                "success": False,
                "message": "Lỗi khi lưu rule vào database"
            }
        logger.info(f"[WatchMarket] Successfully saved rule {rule['rule_id']} to MongoDB")
    except Exception as e:
        logger.error(f"[WatchMarket] Error connecting to MongoDB: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi kết nối database: {str(e)}"
        }

    # Publish rule to register_rule channel
    try:
        redis = get_redis_client()
        channel = "market_watch:register_rule"
        logger.info(f"[WatchMarket] Publishing rule to Redis channel {channel}")
        if not redis.publish(channel, json.dumps(rule, cls=MongoJSONEncoder)):
            # Deactivate rule if publish fails
            logger.error("[WatchMarket] Failed to publish rule to Redis")
            await storage.deactivate_rule(rule["rule_id"])
            return {
                "success": False,
                "message": "Lỗi khi đăng ký rule vào Redis"
            }
        logger.info(f"[WatchMarket] Successfully published rule {rule['rule_id']} to Redis")
    except Exception as e:
        # Deactivate rule if Redis operation fails
        logger.error(f"[WatchMarket] Error connecting to Redis: {e}", exc_info=True)
        await storage.deactivate_rule(rule["rule_id"])
        return {
            "success": False,
            "message": f"Lỗi kết nối Redis: {str(e)}"
        }

    msg = f"Đã đăng ký theo dõi: {', '.join(f'{t['symbol']} ({t['name']})' for t in valid_tokens)} qua {app}."
    if conditions:
        msg += f"\nĐiều kiện: {json.dumps(conditions, ensure_ascii=False)}"
    if invalid_tokens:
        msg += f"\nKhông tìm thấy: {', '.join(invalid_tokens)}"

    return {
        "success": True,
        "message": msg,
        "rule": rule
    }
