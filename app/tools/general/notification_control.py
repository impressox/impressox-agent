import json
import logging
from langchain_core.tools import tool
from app.cache.cache_redis import get_redis_client
from app.constants import NodeName
from app.core.tool_registry import register_tool
from langchain_core.runnables import RunnableConfig

logger = logging.getLogger(__name__)

CHANNEL = 'notify_control'

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

@register_tool(NodeName.GENERAL_NODE, "toggle_notification")
@tool
async def toggle_notification(active, runable_config: RunnableConfig = None):
    """
    Tên: Bật/Tắt Thông Báo Định Kỳ

    Mô tả:
    Bật hoặc tắt tính năng nhận thông báo mặc định được hệ thống gửi định kỳ (mỗi 30 phút)
    về biến động thị trường và dự án airdrop. Khi người dùng chọn bật hoặc tắt, tool này
    sẽ publish một message lên kênh Redis 'notify_control' để worker backend cập nhật
    trạng thái người dùng theo thời gian thực.

    Tham số:
        active (bool): True để bật thông báo, False để tắt.

    Hệ thống sẽ sử dụng user_id (được sinh từ user_id/app/conversation_id/chat_type)
    để định danh người dùng duy nhất trong Redis và MongoDB.
    """
    user_id = runable_config["configurable"].get("user_id", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)
    chat_type = runable_config["configurable"].get("chat_type", None)
    notify_id = get_notify_id(user_id, app, conversation_id, chat_type)
    redis = get_redis_client()
    message = json.dumps({'user_id': notify_id, 'active': active})
    await redis.publish(CHANNEL, message)
    return f"Notification {'enabled' if active else 'disabled'} for {notify_id}" 