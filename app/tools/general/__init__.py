from langchain_core.tools import tool
from app.core.tool_registry import register_tool
from app.constants import NodeName
from app.tools.general.coin_price import get_token_price
from app.tools.general.summary_social import get_social_summary
from app.tools.general.watch_market import watch_market
from app.tools.general.unwatch_market import unwatch_market
from app.tools.general.search_knowledge import search_knowledge_tool
# from app.tools.general.notification_control import toggle_schedule_notification
from app.tools.general.watch_wallet import watch_wallet
from app.tools.general.unwatch_wallet import unwatch_wallet
from app.tools.general.watch_airdrop import watch_airdrop
from app.tools.general.unwatch_airdrop import unwatch_airdrop
from app.tools.general.search_knowledge_binance import search_binance_knowledge, search_x_binance
from app.tools.general.safe_python_tool import safe_python_tool


@register_tool(NodeName.GENERAL_NODE, "get_token_price")
@tool
async def get_token_price_tool(asset: str) -> dict:
    """
    Retrieves token price and concise market analysis from CoinGecko or DEX (Uniswap/Raydium) based on the given asset.

    Input:
    - asset: token name, symbol, or contract address (EVM/Solana)

    Description:
    Get full market info for any token including price, market cap, sentiment, and breakout signals.

    Response format:
    Return a dictionary that includes at least the field `summary`, which should be a concise natural language string.
    This string must:
    - Present the token's current price and market cap in a human-readable format.
    - Optionally include all-time high (ATH), 24h change, and basic sentiment info (e.g., % bullish/bearish).
    - Provide a short and professional assessment of the token’s current trend or status (e.g., "showing early signs of a breakout" or "currently facing downward pressure").

    Always write the `summary` to be used directly in user replies without further formatting.
    """
    try:
        return await get_token_price(asset)
    except Exception as e:
        return {"success": False, "error": str(e)}

__all__ = [
    "get_social_summary",
    "watch_market",
    "unwatch_market",
    "search_knowledge_tool",
    # "toggle_schedule_notification",
    "watch_wallet",
    "unwatch_wallet",
    "watch_airdrop",
    "unwatch_airdrop",
    "safe_python_tool",
    "search_binance_knowledge",
    "search_x_binance"
]