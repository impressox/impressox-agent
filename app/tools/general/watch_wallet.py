import json
import time
import uuid
import asyncio
from typing import List, Dict, Optional, Any
from bson import ObjectId
import logging
from functools import partial
import base58
from eth_utils import is_address
from web3 import Web3

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

def get_config():
    """Get configuration for blockchain and notification settings."""
    from app.configs.config import app_configs
    
    config = app_configs.get_blockchain_config()
    return config

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

def validate_wallet_address(address: str) -> tuple[bool, str]:
    """Validate wallet address and determine its type"""
    try:
        # Check if it's a valid Solana address (base58 encoded, 32 bytes)
        decoded = base58.b58decode(address)
        if len(decoded) == 32:
            return True, "solana"
    except:
        pass

    # Check if it's a valid EVM address
    if is_address(address):
        return True, "evm"

    return False, None

@register_tool(NodeName.GENERAL_NODE, "watch_wallet")
@tool
async def watch_wallet(wallets: Optional[List[Dict[str, str]]] = None, conditions: Optional[Dict] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Tool để đăng ký theo dõi hoạt động của một hoặc nhiều ví (ví dụ: chuyển token, nhận token, giao dịch NFT).
    Khi có hoạt động liên quan đến các ví này, hệ thống sẽ chủ động thông báo cho bạn qua kênh đã kết nối (Telegram, Web, Discord).

    Args:
        wallets: Danh sách các ví muốn theo dõi. Mỗi ví là một dict với format:
                {
                    "address": "địa_chỉ_ví",
                    "name": "tên_ví" (optional)
                }
        conditions: Điều kiện theo dõi (ví dụ: {"min_amount": 1.0} để theo dõi khi số lượng token > 1.0).
                   Nếu không có điều kiện -> theo dõi mọi hoạt động.
    Returns:
        Dict với trạng thái và thông báo kết quả đăng ký theo dõi.
    """
    try:
        return await _watch_wallet_async(wallets, conditions, runable_config)
    except Exception as e:
        logger.error(f"[WatchWallet] Error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi khi xử lý yêu cầu: {str(e)}"
        }

async def _watch_wallet_async(wallets: Optional[List[Dict[str, str]]] = None, conditions: Optional[Dict] = None, runable_config: RunnableConfig = None) -> Dict[str, Any]:
    """
    Async implementation of watch_wallet tool
    """
    # Get context values
    user_id = runable_config["configurable"].get("user_id", "")
    user_name = runable_config["configurable"].get("user_name", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)

    if not wallets:
        return {
            "success": False,
            "message": "Vui lòng cung cấp ít nhất một địa chỉ ví để theo dõi"
        }

    # Validate wallets and resolve ENS names
    valid_wallets = []
    invalid_wallets = []
    
    for wallet_info in wallets:
        address = wallet_info.get("address")
        name = wallet_info.get("name")
        
        is_valid, wallet_type = validate_wallet_address(address)
        if is_valid:
            # If no name provided and it's an Ethereum address, try to resolve ENS
            if not name and wallet_type == "evm":
                try:
                    # Initialize Web3 with Ethereum RPC
                    w3 = Web3(Web3.HTTPProvider(get_config().get_rpc_url("ethereum")))
                    if w3.is_connected():
                        ens_name = w3.ens.name(address)
                        if ens_name:
                            name = ens_name
                except Exception as e:
                    logger.warning(f"[WatchWallet] Error resolving ENS for {address}: {e}")
            
            valid_wallets.append({
                "address": address,
                "name": name or address,  # Use address as name if no name/ENS found
                "type": wallet_type
            })
        else:
            invalid_wallets.append(address)

    if not valid_wallets:
        return {
            "success": False,
            "message": f"Không tìm thấy địa chỉ ví hợp lệ trong danh sách: {', '.join(invalid_wallets)}"
        }

    # Create watch rule
    rule = {
        "rule_id": generate_rule_id(),
        "user_id": str(user_id),
        "user_name": user_name,
        "watch_type": "wallet",
        "target": [w["address"] for w in valid_wallets],
        "target_data": {
            w["address"]: {
                "address": w["address"],
                "name": w["name"],
                "type": w["type"]
            } for w in valid_wallets
        },
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
        logger.info(f"[WatchWallet] Saving rule to MongoDB: {json.dumps(rule, cls=MongoJSONEncoder)}")
        if not await storage.save_rule(rule):
            logger.error("[WatchWallet] Failed to save rule to MongoDB")
            return {
                "success": False,
                "message": "Lỗi khi lưu rule vào database"
            }
        logger.info(f"[WatchWallet] Successfully saved rule {rule['rule_id']} to MongoDB")
    except Exception as e:
        logger.error(f"[WatchWallet] Error connecting to MongoDB: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Lỗi kết nối database: {str(e)}"
        }

    # Publish rule to register_rule channel
    try:
        redis = get_redis_client()
        channel = "wallet_watch:register_rule"
        logger.info(f"[WatchWallet] Publishing rule to Redis channel {channel}")
        if not redis.publish(channel, json.dumps(rule, cls=MongoJSONEncoder)):
            # Deactivate rule if publish fails
            logger.error("[WatchWallet] Failed to publish rule to Redis")
            await storage.deactivate_rule(rule["rule_id"])
            return {
                "success": False,
                "message": "Lỗi khi đăng ký rule vào Redis"
            }
        logger.info(f"[WatchWallet] Successfully published rule {rule['rule_id']} to Redis")
    except Exception as e:
        # Deactivate rule if Redis operation fails
        logger.error(f"[WatchWallet] Error connecting to Redis: {e}", exc_info=True)
        await storage.deactivate_rule(rule["rule_id"])
        return {
            "success": False,
            "message": f"Lỗi kết nối Redis: {str(e)}"
        }

    msg = "Đã đăng ký theo dõi"
    if valid_wallets:
        msg += f": {', '.join(w['address'] for w in valid_wallets)}"
        if conditions:
            msg += f"\nĐiều kiện: {json.dumps(conditions, ensure_ascii=False)}"
        if invalid_wallets:
            msg += f"\nKhông hợp lệ: {', '.join(invalid_wallets)}"

    return {
        "success": True,
        "message": msg,
        "rule": rule
    } 