import json
import asyncio
from typing import List, Dict, Optional, Any
import logging
from functools import partial
from bson import ObjectId
from datetime import datetime

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

@register_tool(NodeName.GENERAL_NODE, "unwatch_airdrop")
@tool
async def unwatch_airdrop(tokens: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Tool để hủy theo dõi thông tin airdrop của một hoặc nhiều token/dự án đang được theo dõi.
    Có thể hủy theo dõi một token cụ thể, một số token, hoặc tất cả các dự án đang theo dõi airdrop.

    Args:
        tokens: Danh sách các token symbol hoặc tên dự án muốn hủy theo dõi (ví dụ: ["ETH", "BTC", "LayerZero", ...]).
               Nếu không truyền sẽ hủy theo dõi tất cả các dự án airdrop.
    Returns:
        Dict với trạng thái và thông báo kết quả hủy theo dõi.
    """
    try:
        return await _unwatch_airdrop_async(tokens, runable_config)
    except Exception as e:
        logger.error(f"[UnwatchAirdrop] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi xử lý yêu cầu: {str(e)}"
        }

async def _unwatch_airdrop_async(tokens: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Async implementation of unwatch_airdrop tool
    """
    user_id = runable_config["configurable"].get("user_id", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)
    chat_type = runable_config["configurable"].get("chat_type", "private")

    try:
        storage = await RuleStorage.get_instance()
        active_rules = await storage.get_active_rules(user_id, "airdrop", conversation_id, chat_type)
        logger.info(f"[UnwatchAirdrop] User {user_id} has {len(active_rules)} active airdrop rules")
        if not active_rules:
            return {
                "success": True,
                "message": "Bạn chưa theo dõi airdrop nào"
            }

        if tokens:
            tokens = [t.upper() for t in tokens]
            user_tokens = set()
            for rule in active_rules:
                user_tokens.update(t.upper() for t in rule["target"])
            invalid_tokens = [t for t in tokens if t not in user_tokens]
            if invalid_tokens:
                return {
                    "success": True,
                    "message": f"Không tìm thấy token nào trong danh sách theo dõi airdrop: {', '.join(invalid_tokens)}"
                }

        rules_to_deactivate = []
        if tokens:
            for rule in active_rules:
                if any(t.upper() in tokens for t in rule["target"]):
                    rules_to_deactivate.append(rule)
        else:
            for rule in active_rules:
                if "*" in rule.get("target", []):
                    rules_to_deactivate.append(rule)

        if not rules_to_deactivate:
            return {
                "success": True,
                "message": f"Không tìm thấy token nào trong danh sách theo dõi airdrop: {', '.join(tokens) if tokens else 'alert'}"
            }

        redis = get_redis_client()
        deactivated_tokens = set()
        for rule in rules_to_deactivate:
            try:
                if rule["user_id"] != user_id:
                    logger.warning(f"[UnwatchAirdrop] Skipping rule {rule['rule_id']} - belongs to different user")
                    continue
                tokens_to_remove = [t for t in rule["target"] if t.upper() in tokens] if tokens else rule["target"]
                remaining_tokens = [t for t in rule["target"] if t.upper() not in tokens] if tokens else []
                if remaining_tokens:
                    update_data = {
                        "target": remaining_tokens,
                        "updated_at": datetime.utcnow(),
                        "metadata": {
                            **rule.get("metadata", {}),
                            "watch_airdrop": bool(remaining_tokens)
                        }
                    }
                    if await storage.update_rule(rule["rule_id"], update_data):
                        redis.publish(
                            "airdrop_watch:deactivate_rule",
                            json.dumps({
                                "rule_id": rule["rule_id"],
                                "user_id": user_id,
                                "watch_type": "airdrop",
                                "target": tokens_to_remove
                            })
                        )
                        for token in tokens_to_remove:
                            redis.hdel(f"watch:active:airdrop:{token}", rule["rule_id"])
                            deactivated_tokens.add(token)
                else:
                    if await storage.deactivate_rule(rule["rule_id"]):
                        redis.publish(
                            "airdrop_watch:deactivate_rule",
                            json.dumps({
                                "rule_id": rule["rule_id"],
                                "user_id": user_id,
                                "watch_type": "airdrop",
                                "target": rule["target"]
                            })
                        )
                        for token in rule["target"]:
                            redis.hdel(f"watch:active:airdrop:{token}", rule["rule_id"])
                            deactivated_tokens.add(token)
            except Exception as e:
                logger.error(f"[UnwatchAirdrop] Error deactivating rule {rule['rule_id']}: {e}")

        if deactivated_tokens:
            msg = "Đã hủy theo dõi airdrop"
            if tokens:
                msg += f": {', '.join(sorted(deactivated_tokens))}"
            else:
                msg += " tất cả thông báo airdrop"
            return {
                "success": True,
                "message": msg
            }
        else:
            return {
                "success": False,
                "message": "Không thể hủy theo dõi các airdrop"
            }

    except Exception as e:
        logger.error(f"[UnwatchAirdrop] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi hủy theo dõi airdrop: {str(e)}"
        } 