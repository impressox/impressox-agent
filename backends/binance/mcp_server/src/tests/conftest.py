"""Shared test fixtures"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP, Context

from src.server import AppContext
from src.services.binance import BinanceService
from src.services.mongodb import MongoDBService
from src.types import MarketInfo, MarketInfoData, AlphaAnalysis, AlphaInsight

@pytest.fixture
def mock_binance_service():
    """Create a mock BinanceService instance"""
    return AsyncMock(spec=BinanceService)

@pytest.fixture
def mock_mongo_service():
    """Create a mock MongoDBService instance"""
    return AsyncMock(spec=MongoDBService)

@pytest.fixture
def app_context(mock_binance_service, mock_mongo_service):
    """Create an AppContext with mocked dependencies"""
    return AppContext(
        binance_service=mock_binance_service,
        mongo_service=mock_mongo_service
    )

@pytest.fixture
def ctx(app_context):
    """Create a Context instance with mocked AppContext"""
    return Context(app_context)

@pytest.fixture
def mcp():
    """Create a FastMCP server instance for testing"""
    return FastMCP("Test MCP Server")

@pytest.fixture
def mock_market_data():
    """Sample market data for testing"""
    return MarketInfo(
        symbol="BTCUSDT",
        data=MarketInfoData(
            price="50000",
            price_change="5%",
            volume24h="1000",
            recent_trades=[]
        )
    )

@pytest.fixture
def mock_alpha_data():
    """Sample alpha analysis data for testing"""
    return AlphaAnalysis(
        timeframe="24h",
        insights=[
            AlphaInsight(
                pair="BTCUSDT",
                volume_increase=15.5,
                pattern="Strong bullish trend detected"
            )
        ]
    )

@pytest.fixture
def mock_tweet():
    """Sample tweet data for testing"""
    return {
        "_id": "123456789",
        "post_id": 1234567890,
        "post_link": "/binance/status/1234567890",
        "post_time": datetime.utcnow(),
        "text": "Test tweet",
        "user": "binance",
        "likes": 100,
        "quotes": 10,
        "reposts": 50,
        "total_comments": 25,
        "comments": []
    }

@pytest.fixture
def mock_cursor():
    """Create a mock MongoDB cursor"""
    cursor = MagicMock()
    cursor.sort.return_value.limit.return_value = []
    return cursor

@pytest.fixture
def mock_motor_client():
    """Mock MongoDB motor client"""
    client = AsyncMock()
    client.db = AsyncMock()
    client.db.tweets = AsyncMock()
    client.db.tweets.find.return_value = mock_cursor()
    return client
