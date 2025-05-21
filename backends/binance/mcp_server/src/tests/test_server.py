"""Tests for FastMCP server functionality"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import logging

from ..server import (
    app_lifespan, 
    main,
    mcp,
    AppContext,
    MongoDBError
)
from ..types import (
    EmptyInput,
    GetMarketInfoInput,
    GetAlphaInput,
    GetSocialInput
)

@pytest.fixture
def mock_mongodb_service():
    """Create mock MongoDB service"""
    service = AsyncMock()
    service.close = AsyncMock()
    return service

@pytest.fixture
def mock_binance_service():
    """Create mock Binance service"""
    return AsyncMock()

@pytest.fixture
async def test_context(mock_binance_service, mock_mongodb_service):
    """Create test context with mocked services"""
    async with app_lifespan(mcp) as context:
        context.binance_service = mock_binance_service
        context.mongo_service = mock_mongodb_service
        yield context

@pytest.mark.asyncio
async def test_health_check(test_context):
    """Test health check tool"""
    # Create empty input for health check
    empty_input = EmptyInput()
    
    result = await mcp.execute_tool(
        "health_check",
        test_context,
        empty_input
    )
    
    assert result["status"] == "healthy"
    assert result["version"] == test_context.version

@pytest.mark.asyncio
async def test_get_market_info(test_context, mock_binance_service):
    """Test market info tool"""
    # Mock market info response
    mock_binance_service.get_market_info.return_value = {
        "symbol": "BTCUSDT",
        "data": {
            "price": "50000",
            "volume24h": "1000",
            "price_change": "5%"
        }
    }
    
    # Test with symbol
    input_data = GetMarketInfoInput(symbol="BTCUSDT")
    result = await mcp.execute_tool(
        "get_market_info",
        test_context,
        input_data
    )
    
    assert result["symbol"] == "BTCUSDT"
    assert result["data"]["price"] == "50000"
    mock_binance_service.get_market_info.assert_called_once_with("BTCUSDT")

@pytest.mark.asyncio
async def test_get_alpha(test_context, mock_binance_service):
    """Test alpha analysis tool"""
    # Mock alpha analysis response
    mock_binance_service.get_alpha.return_value = {
        "timeframe": "24h",
        "insights": [
            {
                "pair": "BTCUSDT",
                "volume_increase": 15.5,
                "pattern": "bullish"
            }
        ]
    }
    
    input_data = GetAlphaInput(timeframe="24h")
    result = await mcp.execute_tool(
        "get_alpha",
        test_context,
        input_data
    )
    
    assert result["timeframe"] == "24h"
    assert len(result["insights"]) == 1
    assert result["insights"][0]["pair"] == "BTCUSDT"
    mock_binance_service.get_alpha.assert_called_once_with("24h")

@pytest.mark.asyncio
async def test_get_binance_social(test_context, mock_mongodb_service):
    """Test social media data tool"""
    # Mock MongoDB response
    mock_mongodb_service.get_binance_tweets.return_value = {
        "binance": [
            {
                "_id": "1",
                "post_id": 12345,
                "text": "Test tweet",
                "post_time": "2025-05-20T09:00:00Z",
                "user": "binance",
                "likes": 100,
                "quotes": 10,
                "reposts": 50,
                "total_comments": 25,
                "comments": []
            }
        ]
    }
    
    input_data = GetSocialInput(days_ago=0, posts_per_user=10)
    result = await mcp.execute_tool(
        "get_binance_social",
        test_context,
        input_data
    )
    
    assert "tweets_by_user" in result
    assert "binance" in result["tweets_by_user"]
    assert len(result["tweets_by_user"]["binance"]) == 1
    mock_mongodb_service.get_binance_tweets.assert_called_once_with(
        days_ago=0,
        posts_per_user=10
    )

@pytest.mark.asyncio
async def test_mongodb_error_handling(test_context, mock_mongodb_service):
    """Test MongoDB error handling"""
    mock_mongodb_service.get_binance_tweets.side_effect = MongoDBError("Test error")
    
    input_data = GetSocialInput(days_ago=0, posts_per_user=10)
    result = await mcp.execute_tool(
        "get_binance_social",
        test_context,
        input_data
    )
    
    assert "error" in result
    assert result["error"] == "mongodb_error"
    assert "Test error" in result["message"]

@pytest.mark.asyncio
async def test_server_startup(caplog):
    """Test server startup with streamable-http transport"""
    caplog.set_level(logging.INFO)
    
    with patch("mcp.server.fastmcp.FastMCP.run") as mock_run:
        with patch.dict('os.environ', {
            'MCP_HOST': '127.0.0.1',
            'MCP_PORT': '5000'
        }):
            main()
            
            # Verify logging
            assert "Starting Binance MCP Server on 127.0.0.1:5000" in caplog.text
            
            # Verify MCP run called with correct args
            mock_run.assert_called_once_with(
                transport="streamable-http",
                mount_path="/mcp"
            )
