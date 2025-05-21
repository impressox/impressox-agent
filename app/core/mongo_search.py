from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from app.configs.config import app_configs
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("uvicorn.error")

class MongoSearch:
    _instance = None
    _initialized = False

    def __init__(self):
        self.mongo = None
        self.db = None
        self.collection = None
        self.collection_binance = None

    @classmethod
    async def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        if not cls._initialized:
            await cls._instance.initialize()
            cls._initialized = True
        return cls._instance

    async def initialize(self):
        """Initialize MongoDB connection"""
        try:
            mongodb_config = app_configs.get_mongo_config()
            mongodb_url = mongodb_config["connection"]["url"]
            db_name = mongodb_config.get("data_db_name", "cpx-data")

            self.mongo = AsyncIOMotorClient(mongodb_url)
            self.db = self.mongo[db_name]
            self.collection = self.db["tweets"]
            self.collection_binance = self.db["cex_knowledge"]

            # Create indexes
            await self.collection.create_index([("text", "text")])
            await self.collection.create_index([("post_time", -1)])

            logger.info("[MongoSearch] MongoDB initialized")
        except Exception as e:
            logger.error(f"[MongoSearch] MongoDB initialization error: {e}")
            raise

    async def close(self):
        """Close MongoDB connection"""
        if self.mongo:
            self.mongo.close()
            self.mongo = None
            self.db = None
            self.collection = None
            self._instance = None

    async def search(self, query: str, top_k: int = 20,days_ago: int = 0,
                     min_likes: int = 0, min_reposts: int = 0, user_name: Optional[str] = None) -> Dict:
        """
        Full-text search using MongoDB aggregation
        """
        try:
            logger.info(f"[MongoSearch] Searching for query: {query}")
            now = datetime.utcnow()
            filters = {
                "text": {"$ne": None},
            }
            
            if min_likes > 0:
                filters["likes"] = {"$gte": min_likes}
            if min_reposts > 0:
                filters["reposts"] = {"$gte": min_reposts}
            if days_ago:
                filters["post_time"] = {"$gte": now - timedelta(days=days_ago)}
            if user_name:
                filters["user"] = {"$regex": user_name, "$options": "i"}

            pipeline = [
                {"$match": {"$text": {"$search": query}}},
                {"$addFields": {"score": {"$meta": "textScore"}}},
                {"$match": filters},
                {"$sort": {"score": -1, "post_time": -1}},
                {"$limit": top_k},
                {"$project": {
                    "_id": 0,
                    "text": 1,
                    "post_id": 1,
                    "post_time": 1,
                    "user": 1,
                    "post_link": 1,
                    "likes": 1,
                    "reposts": 1,
                    "quotes": 1,
                    "total_comments": 1,
                    "score": 1
                }}
            ]
            logger.info(f"[MongoSearch] Pipeline: {pipeline}")
            cursor = self.collection.aggregate(pipeline)
            results = []
            async for doc in cursor:
                results.append({
                    "content": doc.get("text", ""),
                    "metadata": {
                        "post_id": doc.get("post_id"),
                        "post_time": doc.get("post_time"),
                        "user": doc.get("user"),
                        "post_link": doc.get("post_link"),
                        "likes": doc.get("likes", 0),
                        "reposts": doc.get("reposts", 0),
                        "quotes": doc.get("quotes", 0),
                        "total_comments": doc.get("total_comments", 0)
                    },
                    "relevance_score": doc.get("score", 0.0)
                })
            logger.info(f"[MongoSearch] Search results: {results}")
            return {
                "success": True,
                "data": {
                    "results": results,
                    "query": query,
                    "total_results": len(results)
                }
            }

        except Exception as e:
            logger.error(f"[MongoSearch] Search error: {e}")
            return {
                "success": False,
                "error": f"Search failed: {str(e)}"
            }

    async def search_binance(self, query: str, top_k: int = 10, days_ago: int = 0,
                                  min_likes: int = 0, min_reposts: int = 0, users: list = None) -> Dict:
        try:
            logger.info(f"[MongoSearch] Searching for query: {query} for users: {users}")
            now = datetime.utcnow()
            results = []
            total_results = 0

            users_query = ["binance", "BinanceWallet"]

            for user in users_query:
                filters = {
                    "text": {"$ne": None},
                    "user": user
                }
                if min_likes > 0:
                    filters["likes"] = {"$gte": min_likes}
                if min_reposts > 0:
                    filters["reposts"] = {"$gte": min_reposts}
                if days_ago:
                    filters["post_time"] = {"$gte": now - timedelta(days=days_ago)}

                pipeline = [
                    {"$match": filters},
                    {"$sort": {"post_time": -1}},
                    {"$limit": top_k},
                    {"$project": {
                        "_id": 0,
                        "text": 1,
                        "post_id": 1,
                        "post_time": 1,
                        "user": 1,
                        "post_link": 1,
                        "likes": 1,
                        "reposts": 1,
                        "quotes": 1,
                        "total_comments": 1
                    }}
                ]
                cursor = self.collection.aggregate(pipeline)
                async for doc in cursor:
                    results.append({
                        "content": doc.get("text", ""),
                        "metadata": {
                            "post_id": doc.get("post_id"),
                            "post_time": doc.get("post_time"),
                            "user": doc.get("user"),
                            "post_link": doc.get("post_link"),
                            "likes": doc.get("likes", 0),
                            "reposts": doc.get("reposts", 0),
                            "quotes": doc.get("quotes", 0),
                            "total_comments": doc.get("total_comments", 0)
                        },
                        "relevance_score": 1.0
                    })
                    total_results += 1

            return {
                "success": True,
                "data": {
                    "results": results,
                    "query": query,
                    "total_results": total_results
                }
            }
        except Exception as e:
            logger.error(f"[MongoSearch] Search error: {e}")
            return {
                "success": False,
                "error": f"Search failed: {str(e)}"
            }


    async def search_binance_knowledge(self) -> Dict:
        try:
            cursor = self.collection_binance.find({"name": "binance"})
            results = []
            async for doc in cursor:
                results.append(doc)
            return {
                "success": True,
                "data": results
            }
        except Exception as e:
            logger.error(f"[MongoSearch] Search error: {e}")
            return {
                "success": False,
                "error": f"Search failed: {str(e)}"
            }