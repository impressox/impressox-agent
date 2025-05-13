from langchain_core.tools import tool
from app.core.tool_registry import register_tool
from app.constants import NodeName
from app.tools.general.coin_price import get_token_price
from app.tools.general.summary_social import get_social_summary
from app.tools.general.watch_market import watch_market
from app.tools.general.unwatch_market import unwatch_market
from app.tools.general.search_knowledge import search_knowledge_tool
from app.tools.general.notification_control import toggle_notification
from app.tools.general.watch_wallet import watch_wallet
from app.tools.general.unwatch_wallet import unwatch_wallet
from app.tools.general.watch_airdrop import watch_airdrop
from app.tools.general.unwatch_airdrop import unwatch_airdrop

@register_tool(NodeName.GENERAL_NODE, "get_token_price")
@tool
async def get_token_price_tool(asset: str) -> dict:
    """
    Retrieves token price and concise market analysis from CoinGecko or DEX (Uniswap/Raydium) based on the given asset.

    Input:
    - asset: token name, symbol, or contract address (EVM/Solana)

    "Get full market info for any token including price, market cap, sentiment, and breakout signals. "
    "Always use the 'summary' field in the result to reply directly to the user."

    Response format markdown
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
    "toggle_notification",
    "watch_wallet",
    "unwatch_wallet",
    "watch_airdrop",
    "unwatch_airdrop"
]