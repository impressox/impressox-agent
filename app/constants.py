class NodeName():
    """Loại agent xử lý yêu cầu người dùng"""

    # Agent mặc định (chung chung)
    GENERAL_NODE = "general_node"

    # Agent chuyên xử lý yêu cầu swap / giao dịch
    # SWAP_EXECUTOR = "swap_executor"

    # # Agent phát hiện trend từ X/Twitter, Telegram...
    # TREND_DETECTOR = "trend_detector"

    # # Agent tóm tắt & phân tích tác động tin tức crypto/macro
    # NEWS_INTELLIGENCE = "news_intelligence"

    # # Agent tư vấn chiến lược đầu tư, phân bổ danh mục
    # PORTFOLIO_STRATEGY = "portfolio_strategy"

    # # Agent giám sát ví (đăng ký cảnh báo giao dịch bất thường)
    # WALLET_MONITOR = "wallet_monitor"
    
subgraph_mapping = {
    "A0": {
        "type": NodeName.GENERAL_NODE,
        "description": """Handles general or fallback requests.
- Examples: "Làm thơ đi", "Giải thích lại giúp tôi", "Hệ thống hoạt động thế nào?"
- For chit-chat, help requests, or non-financial interactions.""",
    },
#     "A1": {
#         "type": NodeName.SWAP_EXECUTOR,
#         "description": """Executes token swap or trading requests.
# - Examples: "Mua 100 USDC đổi sang ETH", "Swap PEPE sang BNB dùm"
# - Handles DEX swaps, auto-DCA, and multi-chain execution (via Espresso).""",
#     },
#     "A2": {
#         "type": NodeName.TREND_DETECTOR,
#         "description": """Detects trending tokens and topics from social networks.
# - Examples: "Có gì hot không?", "Token nào đang trend trên Twitter?"
# - Monitors platforms like X/Twitter, Telegram, Discord.""",
#     },
#     "A3": {
#         "type": NodeName.NEWS_INTELLIGENCE,
#         "description": """Summarizes and analyzes crypto/macroeconomic news.
# - Examples: "Tin CPI hôm nay ảnh hưởng gì không?", "ETH có bị ảnh hưởng không?"
# - Identifies impact on user's portfolio and suggests actions.""",
#     },
#     "A4": {
#         "type": NodeName.PORTFOLIO_STRATEGY,
#         "description": """Advises on investment and portfolio strategy.
# - Examples: "Danh mục của tôi có ổn không?", "Nên chia bao nhiêu phần trăm vào stablecoin?"
# - Provides suggestions on rebalancing and allocation.""",
#     },
#     "A5": {
#         "type": NodeName.WALLET_MONITOR,
#         "description": """Monitors wallet activity and sets custom alerts.
# - Examples: "Ví tôi có rút lạ thì báo nhé", "Theo dõi ví của tôi hộ"
# - Schedules background checks for unusual wallet behavior.""",
#     },
}