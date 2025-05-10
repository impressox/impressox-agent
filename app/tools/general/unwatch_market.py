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

async def verify_token_with_coingecko(token: str) -> Optional[Dict]:
    """Verify token with CoinGecko API"""
    try:
        # Try to get token data from CoinGecko
        response = await call_api(
            "GET",
            f"{app_configs.COINGECKO_API_URL}/coins/{token.lower()}",
            params={
                "localization": "false",
                "tickers": "false",
                "market_data": "true",
                "community_data": "false",
                "developer_data": "false"
            }
        )
        
        if response.get("success"):
            data = response.get("data", {})
            return {
                "symbol": data.get("symbol", "").upper(),
                "name": data.get("name", ""),
                "id": data.get("id", "")
            }
        return None
    except Exception as e:
        logger.error(f"[UnwatchMarket] Error verifying token {token} with CoinGecko: {e}")
        return None

@register_tool(NodeName.GENERAL_NODE, "unwatch_market")
@tool
async def unwatch_market(tokens: Optional[List[str]] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
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
        return await _unwatch_market_async(tokens, runable_config)
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
    chat_type = runable_config["configurable"].get("chat_type", "private")

    try:
        # Get all active rules for this user
        storage = await RuleStorage.get_instance()
        active_rules = await storage.get_active_rules(user_id, "token", conversation_id, chat_type)
        logger.info(f"[UnwatchMarket] User {user_id} has {len(active_rules)} active rules")
        if not active_rules:
            return {
                "success": True,
                "message": "Bạn chưa theo dõi token nào"
            }

        # If tokens provided, verify they exist in user's active rules
        if tokens:
            # Convert tokens to uppercase for case-insensitive comparison
            tokens = [t.upper() for t in tokens]
            
            # Get all unique tokens from user's active rules
            user_tokens = set()
            for rule in active_rules:
                user_tokens.update(t.upper() for t in rule["target"])
            
            # Check which tokens are not being watched
            invalid_tokens = [t for t in tokens if t not in user_tokens]
            
            if invalid_tokens:
                # Try to verify invalid tokens with CoinGecko
                verified_tokens = []
                for token in invalid_tokens:
                    token_data = await verify_token_with_coingecko(token)
                    if token_data:
                        verified_tokens.append(f"{token_data['symbol']} ({token_data['name']})")
                
                if verified_tokens:
                    return {
                        "success": True,
                        "message": f"Không tìm thấy token nào trong danh sách theo dõi. Có thể bạn đang tìm: {', '.join(verified_tokens)}"
                    }
                else:
                    return {
                        "success": True,
                        "message": f"Không tìm thấy token nào trong danh sách theo dõi: {', '.join(invalid_tokens)}"
                    }

        # Filter rules based on tokens
        rules_to_deactivate = []
        if tokens:
            for rule in active_rules:
                # Check if any of the rule's target tokens match the requested tokens
                if any(t.upper() in tokens for t in rule["target"]):
                    rules_to_deactivate.append(rule)
        else:
            # If no tokens specified, find rules that watch all alerts (using "*" token)
            for rule in active_rules:
                if "*" in rule.get("target", []):
                    rules_to_deactivate.append(rule)

        if not rules_to_deactivate:
            return {
                "success": True,
                "message": f"Không tìm thấy token nào trong danh sách theo dõi: {', '.join(tokens) if tokens else 'alert'}"
            }

        # Get Redis client
        redis = get_redis_client()

        # Deactivate rules
        deactivated_tokens = set()
        for rule in rules_to_deactivate:
            try:
                # Verify rule belongs to user
                if rule["user_id"] != user_id:
                    logger.warning(f"[UnwatchMarket] Skipping rule {rule['rule_id']} - belongs to different user")
                    continue

                # Get tokens to remove from this rule
                tokens_to_remove = [t for t in rule["target"] if t.upper() in tokens] if tokens else rule["target"]
                remaining_tokens = [t for t in rule["target"] if t.upper() not in tokens] if tokens else []

                if remaining_tokens:
                    # Update rule with remaining tokens
                    update_data = {
                        "target": remaining_tokens,
                        "updated_at": datetime.utcnow(),
                        "metadata": {
                            **rule.get("metadata", {}),
                            "watch_price": bool(remaining_tokens)  # Update watch_price based on remaining tokens
                        }
                    }
                    if await storage.update_rule(rule["rule_id"], update_data):
                        # Publish deactivation event for specific tokens
                        redis.publish(
                            "market_watch:deactivate_rule",
                            json.dumps({
                                "rule_id": rule["rule_id"],
                                "user_id": user_id,
                                "watch_type": "token",
                                "target": tokens_to_remove
                            })
                        )
                        # Remove tokens from Redis
                        for token in tokens_to_remove:
                            redis.hdel(f"watch:active:token:{token}", rule["rule_id"])
                            deactivated_tokens.add(token)
                else:
                    # No tokens remaining, deactivate entire rule
                    if await storage.deactivate_rule(rule["rule_id"]):
                        # Publish deactivation event for all tokens
                        redis.publish(
                            "market_watch:deactivate_rule",
                            json.dumps({
                                "rule_id": rule["rule_id"],
                                "user_id": user_id,
                                "watch_type": "token",
                                "target": rule["target"]
                            })
                        )
                        # Remove all tokens from Redis
                        for token in rule["target"]:
                            redis.hdel(f"watch:active:token:{token}", rule["rule_id"])
                            deactivated_tokens.add(token)
            except Exception as e:
                logger.error(f"[UnwatchMarket] Error deactivating rule {rule['rule_id']}: {e}")

        if deactivated_tokens:
            msg = "Đã hủy theo dõi"
            if tokens:
                msg += f": {', '.join(sorted(deactivated_tokens))}"
            else:
                msg += " tất cả thông báo"
            return {
                "success": True,
                "message": msg
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