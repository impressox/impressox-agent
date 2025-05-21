"""
FastMCP server for Binance market data and analysis.
"""
import os
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from dataclasses import dataclass
from statistics import mean
from typing import Dict, Union

from mcp.server.fastmcp import FastMCP, Context

from .services.binance import BinanceService
from .services.mongodb import MongoDBService
from .types import (
    EmptyInput,
    MarketInfo,
    MarketInfoData,
    GetMarketInfoInput,
    GetAlphaInput,
    AlphaAnalysis,
    GetSocialInput,
    SocialData,
    TweetMetrics
)
from .errors import (
    BinanceAPIError, 
    ConnectionError, 
    ServiceError,
    MongoDBError
)

logger = logging.getLogger(__name__)

# Create context class for dependency injection
@dataclass
class AppContext:
    """Application context with dependencies"""
    binance_service: BinanceService
    mongo_service: MongoDBService
    version: str = "0.1.0"

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage application lifecycle and dependencies"""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Initialize services
    binance_service = BinanceService()
    mongo_service = MongoDBService()
    logger.info("Services initialized")
    
    try:
        yield AppContext(
            binance_service=binance_service,
            mongo_service=mongo_service
        )
    finally:
        # Cleanup
        await mongo_service.close()
        logger.info("Shutting down MCP server")

# Create FastMCP server instance
mcp = FastMCP(
    "Binance MCP Server",
    lifespan=app_lifespan,
    dependencies=["aiohttp", "motor", "pydantic"],
    host = os.getenv("MCP_HOST", "0.0.0.0"),
    port = int(os.getenv("MCP_PORT", 5000)),
    log_level = os.getenv("MCP_LOG_LEVEL", "INFO"),
)

ErrorResponse = Dict[str, Union[str, int]]

# Register MCP tools
@mcp.tool()
async def health_check(ctx: Context[AppContext, EmptyInput], input_data: EmptyInput) -> Dict[str, str]:
    """Get server health status"""
    return {
        "status": "healthy",
        "version": ctx.version
    }

@mcp.tool()
async def get_market_info(ctx: Context[AppContext, GetMarketInfoInput], input_data: GetMarketInfoInput) -> Union[MarketInfo, ErrorResponse]:
    """
    Get market information for a specific trading pair or overall market data.
    
    If symbol is provided, returns detailed info for that pair.
    If no symbol is provided, returns market-wide data with top trading pairs.
    """
    try:
        return await ctx.binance_service.get_market_info(input_data.symbol)
    except BinanceAPIError as e:
        logger.error(f"Binance API error in get_market_info: {e}")
        return {
            "error": "binance_api_error",
            "message": str(e),
            "status_code": e.status_code
        }
    except ConnectionError as e:
        logger.error(f"Connection error in get_market_info: {e}")
        return {
            "error": "connection_error",
            "message": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_market_info: {e}")
        return {
            "error": "internal_error",
            "message": "An unexpected error occurred"
        }

@mcp.tool()
async def get_alpha(ctx: Context[AppContext, GetAlphaInput], input_data: GetAlphaInput) -> Union[AlphaAnalysis, ErrorResponse]:
    """
    Get trading alpha insights based on volume and price pattern analysis.
    
    Analyzes major pairs over the specified timeframe 
    to identify significant volume changes and price patterns.
    """
    try:
        return await ctx.binance_service.get_alpha(input_data.timeframe)
    except BinanceAPIError as e:
        logger.error(f"Binance API error in get_alpha: {e}")
        return {
            "error": "binance_api_error",
            "message": str(e),
            "status_code": e.status_code
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_alpha: {e}")
        return {
            "error": "internal_error",
            "message": "An unexpected error occurred"
        }

@mcp.tool()
async def get_binance_social(ctx: Context[AppContext, GetSocialInput], input_data: GetSocialInput) -> Union[SocialData, ErrorResponse]:
    """
    Get Binance social media posts and engagement metrics
    
    Args:
        days_ago: Number of days to look back (0 = today only)
        posts_per_user: Number of most recent posts per user (max 10)
        
    Returns:
        Social media data and engagement metrics by user
    """
    try:
        tweets_by_user = await ctx.mongo_service.get_binance_tweets(
            days_ago=input_data.days_ago,
            posts_per_user=input_data.posts_per_user
        )
        
        # Calculate metrics for each user
        metrics_by_user = {}
        total_engagement = 0
        
        for user, tweets in tweets_by_user.items():
            if not tweets:
                continue
                
            user_engagement = sum(
                t.likes + t.quotes + t.reposts + t.total_comments 
                for t in tweets
            )
            total_engagement += user_engagement
            
            metrics_by_user[user] = TweetMetrics(
                total_posts=len(tweets),
                total_engagement=user_engagement,
                avg_likes=mean(t.likes for t in tweets),
                avg_reposts=mean(t.reposts for t in tweets),
                avg_comments=mean(t.total_comments for t in tweets),
                timeframe="Today" if input_data.days_ago == 0 
                         else f"Last {input_data.days_ago} days"
            )
        
        return SocialData(
            tweets_by_user=tweets_by_user,
            metrics_by_user=metrics_by_user,
            timeframe="Today" if input_data.days_ago == 0 
                     else f"Last {input_data.days_ago} days",
            total_engagement=total_engagement
        )
        
    except MongoDBError as e:
        logger.error(f"MongoDB error in get_binance_social: {e}")
        return {
            "error": "mongodb_error",
            "message": str(e)
        }
    except Exception as e:
        logger.error(f"Unexpected error in get_binance_social: {e}")
        return {
            "error": "internal_error",
            "message": "An unexpected error occurred"
        }

def main():
    """Entry point for running the server"""
    try:
        # Log server startup
        # host = os.getenv("MCP_HOST", "127.0.0.1")
        # port = int(os.getenv("MCP_PORT", "5000"))
        # logger.info(f"Starting Binance MCP Server on {host}:{port}")
        
        # Run with streamable-http transport
        mcp.run(
            transport="streamable-http",
            mount_path="/mcp"  # Base path for MCP tools
        )
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise

if __name__ == "__main__":
    main()
