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

@register_tool(NodeName.GENERAL_NODE, "unwatch_wallet")
@tool
async def unwatch_wallet(wallets: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Tool để hủy theo dõi hoạt động của một hoặc nhiều ví đang được theo dõi.
    Có thể hủy theo dõi một ví cụ thể, một số ví, hoặc tất cả các ví đang theo dõi.

    Args:
        wallets: Danh sách các địa chỉ ví muốn hủy theo dõi.
               Nếu không truyền sẽ hủy theo dõi tất cả các ví.
    Returns:
        Dict với trạng thái và thông báo kết quả hủy theo dõi.
    """
    try:
        return await _unwatch_wallet_async(wallets, runable_config)
    except Exception as e:
        logger.error(f"[UnwatchWallet] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi xử lý yêu cầu: {str(e)}"
        }

async def _unwatch_wallet_async(wallets: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Async implementation of unwatch_wallet tool
    """
    # Get context values
    user_id = runable_config["configurable"].get("user_id", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)
    chat_type = runable_config["configurable"].get("chat_type", "private")

    try:
        # Get all active rules for this user
        storage = await RuleStorage.get_instance()
        active_rules = await storage.get_active_rules(user_id, "wallet", conversation_id, chat_type)
        logger.info(f"[UnwatchWallet] User {user_id} has {len(active_rules)} active rules")
        if not active_rules:
            return {
                "success": True,
                "message": "Bạn chưa theo dõi ví nào"
            }

        # If wallets provided, verify they exist in user's active rules
        if wallets:
            # Get all unique wallets from user's active rules
            user_wallets = set()
            for rule in active_rules:
                user_wallets.update(rule["target"])
            
            # Check which wallets are not being watched
            invalid_wallets = [w for w in wallets if w not in user_wallets]
            
            if invalid_wallets:
                return {
                    "success": True,
                    "message": f"Không tìm thấy ví nào trong danh sách theo dõi: {', '.join(invalid_wallets)}"
                }

        # Filter rules based on wallets
        rules_to_deactivate = []
        if wallets:
            for rule in active_rules:
                # Check if any of the rule's target wallets match the requested wallets
                if any(w in wallets for w in rule["target"]):
                    rules_to_deactivate.append(rule)
        else:
            # If no wallets specified, deactivate all wallet rules
            rules_to_deactivate = active_rules

        if not rules_to_deactivate:
            return {
                "success": True,
                "message": f"Không tìm thấy ví nào trong danh sách theo dõi: {', '.join(wallets) if wallets else 'wallet'}"
            }

        # Get Redis client
        redis = get_redis_client()

        # Deactivate rules
        deactivated_wallets = set()
        for rule in rules_to_deactivate:
            try:
                # Verify rule belongs to user
                if rule["user_id"] != user_id:
                    logger.warning(f"[UnwatchWallet] Skipping rule {rule['rule_id']} - belongs to different user")
                    continue

                # Get wallets to remove from this rule
                wallets_to_remove = [w for w in rule["target"] if w in wallets] if wallets else rule["target"]
                remaining_wallets = [w for w in rule["target"] if w not in wallets] if wallets else []

                if remaining_wallets:
                    # Update rule with remaining wallets
                    update_data = {
                        "target": remaining_wallets,
                        "updated_at": datetime.utcnow(),
                        "metadata": {
                            **rule.get("metadata", {})
                        }
                    }
                    if await storage.update_rule(rule["rule_id"], update_data):
                        # Publish deactivation event for specific wallets
                        redis.publish(
                            "wallet_watch:deactivate_rule",
                            json.dumps({
                                "rule_id": rule["rule_id"],
                                "user_id": user_id,
                                "watch_type": "wallet",
                                "target": wallets_to_remove
                            })
                        )
                        # Remove wallets from Redis
                        for wallet in wallets_to_remove:
                            redis.hdel(f"watch:active:wallet:{wallet}", rule["rule_id"])
                            deactivated_wallets.add(wallet)
                else:
                    # No wallets remaining, deactivate entire rule
                    if await storage.deactivate_rule(rule["rule_id"]):
                        # Publish deactivation event for all wallets
                        redis.publish(
                            "wallet_watch:deactivate_rule",
                            json.dumps({
                                "rule_id": rule["rule_id"],
                                "user_id": user_id,
                                "watch_type": "wallet",
                                "target": rule["target"]
                            })
                        )
                        # Remove all wallets from Redis
                        for wallet in rule["target"]:
                            redis.hdel(f"watch:active:wallet:{wallet}", rule["rule_id"])
                            deactivated_wallets.add(wallet)
            except Exception as e:
                logger.error(f"[UnwatchWallet] Error deactivating rule {rule['rule_id']}: {e}")

        if deactivated_wallets:
            msg = "Đã hủy theo dõi"
            if wallets:
                msg += f": {', '.join(sorted(deactivated_wallets))}"
            else:
                msg += " tất cả các ví"
            return {
                "success": True,
                "message": msg
            }
        else:
            return {
                "success": False,
                "message": "Không thể hủy theo dõi các ví"
            }

    except Exception as e:
        logger.error(f"[UnwatchWallet] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi hủy theo dõi: {str(e)}"
        } 