"""Type definitions for the MCP server"""
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field

class EmptyInput(BaseModel):
    """Empty input model for endpoints without parameters"""
    pass

class Trade(BaseModel):
    """Model for a single trade"""
    id: int
    price: str
    qty: str
    quote_qty: str
    time: int
    is_buyer_maker: bool

class MarketPair(BaseModel):
    """Model for market pair data"""
    symbol: str
    volume: str
    price_change: str = Field(..., description="Price change percentage")

class MarketInfoData(BaseModel):
    """Model for market information data"""
    price: Optional[str] = None
    price_change: Optional[str] = None
    volume24h: Optional[str] = None
    recent_trades: Optional[List[Trade]] = None
    top_pairs: Optional[List[MarketPair]] = None
    total_volume: Optional[float] = None

class MarketInfo(BaseModel):
    """Model for complete market information"""
    symbol: str
    data: MarketInfoData

class AlphaInsight(BaseModel):
    """Model for trading alpha insight"""
    pair: str
    volume_increase: float = Field(..., description="Volume increase percentage")
    pattern: Optional[str] = Field(None, description="Detected trading pattern")

class AlphaAnalysis(BaseModel):
    """Model for complete alpha analysis"""
    timeframe: Literal["24h", "7d", "30d"]
    insights: List[AlphaInsight]

class Tweet(BaseModel):
    """Model for a Twitter post"""
    id: str = Field(alias="_id")
    post_id: int
    post_link: str
    post_time: datetime
    text: str
    user: str
    likes: int = 0
    quotes: int = 0
    reposts: int = 0
    total_comments: int = 0
    comments: List[str] = Field(default_factory=list)

class TweetMetrics(BaseModel):
    """Aggregated metrics for tweets"""
    total_posts: int
    total_engagement: int
    avg_likes: float
    avg_reposts: float
    avg_comments: float
    timeframe: str

class SocialData(BaseModel):
    """Combined social media data and metrics"""
    tweets_by_user: Dict[str, List[Tweet]]
    metrics_by_user: Dict[str, TweetMetrics]
    timeframe: str
    total_engagement: int

# Tool input models
class GetMarketInfoInput(BaseModel):
    """Input model for get_market_info tool"""
    symbol: Optional[str] = Field(
        None,
        description="Trading pair symbol (e.g. 'BTCUSDT'). If not provided, returns market-wide data"
    )

class GetAlphaInput(BaseModel):
    """Input model for get_alpha tool"""
    timeframe: Literal["24h", "7d", "30d"] = Field(
        ...,
        description="Analysis timeframe"
    )

class GetSocialInput(BaseModel):
    """Input model for get_binance_social tool"""
    days_ago: int = Field(
        0,
        description="Days to look back (0 = today only)",
        ge=0
    )
    posts_per_user: int = Field(
        10,
        description="Number of posts per user (max 10)",
        ge=1,
        le=10
    )
