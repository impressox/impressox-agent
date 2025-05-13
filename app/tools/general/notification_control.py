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

@register_tool(NodeName.GENERAL_NODE, "toggle_schedule_notification")
@tool
def toggle_schedule_notification(active, runable_config: RunnableConfig = None):
    """
    Tên: Bật/Tắt Thông Báo Định Kỳ

    Mô tả:
    Bật hoặc tắt **thông báo định kỳ tự động** từ hệ thống, được gửi mỗi 30 phút.
    Các thông báo này bao gồm tóm tắt biến động thị trường và các cơ hội airdrop nổi bật.
    
    ⚠️ Lưu ý:
    - Tool này KHÔNG dùng để theo dõi chi tiết từng biến động hoặc token cụ thể.
    - Nếu bạn muốn nhận thông báo ngay khi có biến động lớn, vui lòng sử dụng công cụ khác như `track_market_event`.

    Khi bật hoặc tắt, tool sẽ gửi một thông điệp lên Redis channel `notify_control` để hệ thống backend cập nhật
    trạng thái theo dõi định kỳ của người dùng theo thời gian thực.

    Tham số:
        active (bool): 
            - `True`: bật thông báo định kỳ.
            - `False`: tắt thông báo định kỳ.
    """
    user_id = runable_config["configurable"].get("user_id", "")
    app = runable_config["configurable"].get("app", None)
    conversation_id = runable_config["configurable"].get("conversation_id", None)
    chat_type = runable_config["configurable"].get("chat_type", None)
    notify_id = get_notify_id(user_id, app, conversation_id, chat_type)
    redis = get_redis_client()
    message = json.dumps({'user_id': notify_id, 'active': active})
    redis.publish(CHANNEL, message)
    return f"Notification {'enabled' if active else 'disabled'} for {notify_id}" 