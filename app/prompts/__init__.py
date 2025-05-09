from app.prompts.general_prompt import system_prompt as general_node_system_prompt
from app.prompts.swap_executor_prompt import swap_executor_prompt as swap_executor_system_prompt
from app.prompts.wallet_monitor_prompt import system_prompt as wallet_monitor_system_prompt
from app.prompts.news_intelligence_prompt import system_prompt as news_intelligence_system_prompt
from app.prompts.trend_detector_prompt import system_prompt as trend_detector_system_prompt
from app.prompts.portfolio_strategy_prompt import system_prompt as portfolio_strategy_system_prompt

__all__ = [
    'general_node_system_prompt',
    'swap_executor_system_prompt',
    'wallet_monitor_system_prompt',
    'news_intelligence_system_prompt',
    'trend_detector_system_prompt', 
    'portfolio_strategy_system_prompt',
]
