"""Tests for MongoDB service"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection

from src.services.mongodb import MongoDBService
from src.errors import MongoConnectionError, MongoQueryError

@pytest.fixture
def mock_motor_client(monkeypatch):
    """Create a mock MongoDB client"""
    mock_client = AsyncMock(spec=AsyncIOMotorClient)
    mock_db = AsyncMock()
    mock_collection = AsyncMock(spec=AsyncIOMotorCollection)
    
    mock_client.__getitem__.return_value = mock_db
    mock_db.__getitem__.return_value = mock_collection
    
    with patch("motor.motor_asyncio.AsyncIOMotorClient") as mock:
        mock.return_value = mock_client
        yield mock_collection

@pytest.fixture
def mock_tweet_data():
    """Sample tweet data for testing"""
    return {
        "_id": "123456789",
        "post_id": 1234567890,
        "post_link": "/binance/status/1234567890",
        "post_time": datetime.utcnow(),
        "text": "Test tweet content",
        "user": "binance",
        "likes": 100,
        "quotes": 10,
        "reposts": 50,
        "total_comments": 25,
        "comments": []
    }

@pytest.mark.asyncio
async def test_mongodb_service_init(mock_motor_client):
    """Test MongoDB service initialization"""
    service = MongoDBService()
    assert service.tweets == mock_motor_client
    assert "binance" in service.users
    assert "BinanceWallet" in service.users

@pytest.mark.asyncio
async def test_find_user_tweets(mock_motor_client, mock_tweet_data):
    """Test finding tweets for a specific user"""
    mock_motor_client.find.return_value.sort.return_value.limit.return_value = [mock_tweet_data]
    
    service = MongoDBService()
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=1)
    
    tweets = await service.find_user_tweets(
        user="binance",
        start_date=start_date,
        end_date=end_date,
        limit=10
    )
    
    assert len(tweets) == 1
    tweet = tweets[0]
    assert tweet.id == mock_tweet_data["_id"]
    assert tweet.post_id == mock_tweet_data["post_id"]
    assert tweet.user == "binance"
    assert tweet.likes == 100

@pytest.mark.asyncio
async def test_get_binance_tweets_today(mock_motor_client, mock_tweet_data):
    """Test getting today's tweets"""
    mock_motor_client.find.return_value.sort.return_value.limit.return_value = [mock_tweet_data]
    
    service = MongoDBService()
    tweets_by_user = await service.get_binance_tweets(days_ago=0)
    
    assert "binance" in tweets_by_user
    assert len(tweets_by_user["binance"]) == 1
    
    # Verify query used today's date range
    call_args = mock_motor_client.find.call_args[0][0]
    assert "post_time" in call_args
    query_range = call_args["post_time"]
    
    start_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=1)
    
    assert query_range["$gte"].date() == start_date.date()
    assert query_range["$lt"].date() == end_date.date()

@pytest.mark.asyncio
async def test_get_binance_tweets_days_ago(mock_motor_client, mock_tweet_data):
    """Test getting tweets from days ago"""
    mock_motor_client.find.return_value.sort.return_value.limit.return_value = [mock_tweet_data]
    
    service = MongoDBService()
    tweets_by_user = await service.get_binance_tweets(days_ago=7)
    
    assert "binance" in tweets_by_user
    assert "BinanceWallet" in tweets_by_user
    
    # Verify query used correct date range
    call_args = mock_motor_client.find.call_args[0][0]
    assert "post_time" in call_args
    query_range = call_args["post_time"]
    
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    
    assert query_range["$gte"].date() <= week_ago.date()
    assert query_range["$lt"].date() >= now.date()

@pytest.mark.asyncio
async def test_mongodb_connection_error():
    """Test handling of MongoDB connection errors"""
    with patch("motor.motor_asyncio.AsyncIOMotorClient", side_effect=Exception("Connection failed")):
        with pytest.raises(MongoConnectionError):
            MongoDBService()

@pytest.mark.asyncio
async def test_mongodb_query_error(mock_motor_client):
    """Test handling of MongoDB query errors"""
    mock_motor_client.find.side_effect = Exception("Query failed")
    
    service = MongoDBService()
    with pytest.raises(MongoQueryError):
        await service.get_binance_tweets()

@pytest.mark.asyncio
async def test_max_posts_per_user_limit(mock_motor_client, mock_tweet_data):
    """Test enforcement of maximum posts per user"""
    # Create multiple mock tweets
    mock_tweets = [
        {**mock_tweet_data, "_id": str(i), "post_id": i}
        for i in range(15)
    ]
    mock_motor_client.find.return_value.sort.return_value.limit.return_value = mock_tweets
    
    service = MongoDBService()
    tweets_by_user = await service.get_binance_tweets(posts_per_user=12)  # Should be limited to 10
    
    assert len(tweets_by_user["binance"]) <= 10
    assert len(tweets_by_user["BinanceWallet"]) <= 10
    
    # Verify limit was applied in query
    limit_value = mock_motor_client.find.return_value.sort.return_value.limit.call_args[0][0]
    assert limit_value <= 10
