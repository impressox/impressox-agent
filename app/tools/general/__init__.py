from langchain_core.tools import tool
from app.core.tool_registry import register_tool
from app.constants import NodeName
from app.tools.general.coin_price import get_token_price
from app.tools.general.summary_social import get_social_summary
from app.tools.general.watch_market import watch_market
from app.tools.general.unwatch_market import unwatch_market
import asyncio

@register_tool(NodeName.GENERAL_NODE, "get_token_price")
@tool
def get_token_price_tool(asset: str) -> dict:
    """
    Lấy giá token từ CoinGecko hoặc DEX (Uniswap/Raydium) theo asset (địa chỉ hoặc tên/symbol).
    Đầu vào: asset (có thể là địa chỉ token EVM/SOL, tên, symbol).
    Trả về dict: {"success": bool, "data": {...} hoặc "error": "..."}
    Luôn kèm theo phân tích cơ bản ngắn gọn, ví dụ như vốn hóa, cung lưu hành, hoặc tính thanh khoản với định dạng có cấu trúc rõ ràng
    """
    try:
        return asyncio.run(get_token_price(asset))
    except Exception as e:
        return {"success": False, "error": str(e)}

__all__ = [
    "get_social_summary",
    "watch_market",
    "unwatch_market"
]