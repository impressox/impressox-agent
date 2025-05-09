import json
import asyncio
from typing import List, Dict, Optional, Any
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

@register_tool(NodeName.GENERAL_NODE, "unwatch_market")
@tool
def unwatch_market(tokens: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Tool để hủy theo dõi biến động của một hoặc nhiều token đang được theo dõi.
    Có thể hủy theo dõi một token cụ thể, một số token, hoặc tất cả các token đang theo dõi.

    Args:
        tokens: Danh sách các token symbol muốn hủy theo dõi (ví dụ: ["ETH", "BTC"]).
               Nếu không truyền sẽ hủy theo dõi tất cả các token.
    Returns:
        Dict với trạng thái và thông báo kết quả hủy theo dõi.
    """
    try:
        return run_async(_unwatch_market_async(tokens, runable_config))
    except Exception as e:
        logger.error(f"[UnwatchMarket] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi xử lý yêu cầu: {str(e)}"
        }

async def _unwatch_market_async(tokens: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Async implementation of unwatch_market tool
    """
    # Get context values
    user_id = runable_config["configurable"].get("user_id", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)

    try:
        # Get Redis client
        redis = get_redis_client()
        
        # Get all active rules for this user
        storage = await RuleStorage.get_instance()
        active_rules = await storage.get_active_rules(user_id, "token")
        
        if not active_rules:
            return {
                "success": True,
                "message": "Bạn chưa theo dõi token nào"
            }

        # Filter rules based on tokens
        rules_to_deactivate = []
        if tokens:
            # Convert tokens to uppercase for case-insensitive comparison
            tokens = [t.upper() for t in tokens]
            for rule in active_rules:
                # Check if any of the rule's target tokens match the requested tokens
                if any(t.upper() in tokens for t in rule["target"]):
                    rules_to_deactivate.append(rule)
        else:
            # If no tokens specified, deactivate all rules
            rules_to_deactivate = active_rules

        if not rules_to_deactivate:
            return {
                "success": True,
                "message": f"Không tìm thấy token nào trong danh sách theo dõi: {', '.join(tokens)}"
            }

        # Deactivate rules
        deactivated_tokens = set()
        for rule in rules_to_deactivate:
            try:
                # Deactivate rule in MongoDB
                if await storage.deactivate_rule(rule["rule_id"]):
                    # Remove rule from Redis
                    for token in rule["target"]:
                        await redis.hdel(f"watch:active:token:{token}", rule["rule_id"])
                        deactivated_tokens.add(token)
                    
                    # Publish deactivation event
                    await redis.publish(
                        "market_watch:deactivate_rule",
                        json.dumps({
                            "rule_id": rule["rule_id"],
                            "user_id": user_id,
                            "watch_type": "token",
                            "target": rule["target"]
                        })
                    )
            except Exception as e:
                logger.error(f"[UnwatchMarket] Error deactivating rule {rule['rule_id']}: {e}")

        if deactivated_tokens:
            return {
                "success": True,
                "message": f"Đã hủy theo dõi: {', '.join(sorted(deactivated_tokens))}"
            }
        else:
            return {
                "success": False,
                "message": "Không thể hủy theo dõi các token"
            }

    except Exception as e:
        logger.error(f"[UnwatchMarket] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi hủy theo dõi: {str(e)}"
        } 