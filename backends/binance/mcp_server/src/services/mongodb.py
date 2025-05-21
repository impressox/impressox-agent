"""MongoDB service for MCP server"""
import os
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

import yaml
import motor.motor_asyncio
from bson import ObjectId

from ..errors import MongoDBError, MongoConnectionError

logger = logging.getLogger(__name__)

class MongoDBService:
    """Service for MongoDB operations"""

    def __init__(self):
        self.client = None
        self.db = None
        self._read_config()
        
        # Only initialize MongoDB if MONGO_REQUIRED=true
        if os.getenv("MONGO_REQUIRED", "false").lower() == "true":
            self._initialize_client()
        else:
            logger.warning("MongoDB initialization skipped (MONGO_REQUIRED=false)")

    def _read_config(self) -> Dict[str, Any]:
        """Read MongoDB config from file"""
        try:
            config_path = Path("configs/mongo.yaml")
            if not config_path.exists():
                logger.warning("MongoDB config not found, using defaults")
                self.config = {
                    "connection": {
                        "url": "mongodb://localhost:27017",
                        "database": "binance_mcp"
                    },
                    "collections": {
                        "tweets": "binance_tweets"
                    }
                }
                return

            with open(config_path) as f:
                self.config = yaml.safe_load(f)
                
        except Exception as e:
            logger.error(f"Error loading MongoDB config: {e}")
            raise MongoConnectionError(f"MongoDB config loading failed: {str(e)}")

    def _initialize_client(self):
        """Initialize MongoDB client"""
        try:
            # Get connection URL from env or config
            mongo_url = os.getenv(
                "MONGO_URL",
                self.config["connection"]["url"]
            )
            
            # Create client
            self.client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
            
            # Get database
            db_name = self.config["connection"]["database"]
            self.db = self.client[db_name]
            
            logger.info("MongoDB client initialized")
            
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e}")
            raise MongoConnectionError(f"MongoDB initialization failed: {str(e)}")

    async def get_binance_tweets(
        self,
        days_ago: int = 0,
        posts_per_user: int = 10
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get recent tweets from Binance accounts
        
        Args:
            days_ago: Number of days to look back
            posts_per_user: Maximum posts per user
            
        Returns:
            Dictionary of tweets by user
        """
        if not self.db:
            # Return mock data when MongoDB is not available
            logger.warning("MongoDB not available, returning mock data")
            return {
                "binance": [
                    {
                        "post_id": 1,
                        "text": "Mock tweet for testing",
                        "post_time": "2025-05-20T00:00:00Z",
                        "user": "binance",
                        "likes": 100,
                        "quotes": 10,
                        "reposts": 20,
                        "total_comments": 30,
                        "comments": []
                    }
                ]
            }
            
        try:
            collection = self.db[self.config["collections"]["tweets"]]
            
            # Find recent tweets
            cursor = collection.find(
                {"post_time": {"$gte": f"-{days_ago}d"}},
                limit=posts_per_user
            ).sort("post_time", -1)
            
            # Group by user
            tweets_by_user = {}
            async for tweet in cursor:
                user = tweet["user"]
                if user not in tweets_by_user:
                    tweets_by_user[user] = []
                if len(tweets_by_user[user]) < posts_per_user:
                    tweets_by_user[user].append(tweet)
                    
            return tweets_by_user
            
        except Exception as e:
            logger.error(f"Error fetching tweets: {e}")
            raise MongoDBError(f"Failed to fetch tweets: {str(e)}")

    async def close(self):
        """Close MongoDB connection"""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed")
