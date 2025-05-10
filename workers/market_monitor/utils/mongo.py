import logging
import time
from typing import Dict, List, Optional, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo.errors import PyMongoError
from bson import ObjectId
import json
from datetime import datetime
from workers.market_monitor.utils.config import get_config

logger = logging.getLogger(__name__)

class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB documents"""
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

class MongoClient:
    _instance = None
    _client = None
    _db = None
    
    @classmethod
    async def get_instance(cls):
        """Get MongoDB client instance"""
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._connect()
        return cls._instance
        
    @classmethod
    async def close(cls):
        """Close MongoDB connection"""
        if cls._client is not None:
            cls._client.close()
            cls._client = None
            cls._db = None
            cls._instance = None
            
    async def _connect(self):
        """Connect to MongoDB"""
        try:
            config = get_config()
            mongo_url = config.get_mongo_url()
            db_name = config.get_mongo_db()
            
            self._client = AsyncIOMotorClient(mongo_url)
            self._db = self._client[db_name]
            
            # Test connection
            await self._db.command('ping')
            logger.info("Connected to MongoDB")
            
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise
            
    @property
    def db(self):
        """Get database instance"""
        if self._db is None:
            raise RuntimeError("MongoDB not connected")
        return self._db
        
    async def get_collection(self, name: str):
        """Get collection by name"""
        return self.db[name]
        
    async def insert_one(self, collection: str, document: dict):
        """Insert one document"""
        return await self.db[collection].insert_one(document)
        
    async def find_one(self, collection: str, query: dict):
        """Find one document"""
        return await self.db[collection].find_one(query)
        
    async def find(self, collection: str, query: dict):
        """Find documents"""
        return self.db[collection].find(query)
        
    async def update_one(self, collection: str, query: dict, update: dict):
        """Update one document"""
        return await self.db[collection].update_one(query, update)
        
    async def delete_one(self, collection: str, query: dict):
        """Delete one document"""
        return await self.db[collection].delete_one(query)

    async def get_active_rules(self, watch_type: Optional[str] = None, active_only: bool = True) -> List[Dict]:
        """Get active rules, optionally filtered by watch type"""
        try:
            query = {}
            if watch_type:
                query["watch_type"] = watch_type
            if active_only:
                query["active"] = True
            cursor = self.db.watch_rules.find(query)
            rules = await cursor.to_list(length=None)
            return json.loads(json.dumps(rules, cls=MongoJSONEncoder))
        except PyMongoError as e:
            logger.error(f"Error getting active rules: {e}")
            return []

    async def update_rule(self, rule_id: str, update: Dict) -> bool:
        """Update a rule"""
        try:
            result = await self.db.watch_rules.update_one(
                {"rule_id": rule_id},
                {"$set": update}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logger.error(f"Error updating rule {rule_id}: {e}")
            return False

    async def deactivate_rule(self, rule_id: str) -> bool:
        """Deactivate a rule"""
        return await self.update_rule(rule_id, {"active": False})

    async def load_active_rule_targets(self, watch_type: str) -> List[str]:
        """Load all unique targets from active rules"""
        try:
            pipeline = [
                {"$match": {"watch_type": watch_type, "active": True}},
                {"$unwind": "$target"},
                {"$group": {"_id": None, "targets": {"$addToSet": "$target"}}}
            ]
            result = await self.db.watch_rules.aggregate(pipeline).to_list(length=1)
            return result[0]["targets"] if result else []
        except PyMongoError as e:
            logger.error(f"Error loading active targets: {e}")
            return []

    async def update_rule_status(self, rule_id: str, status: str, error: Optional[str] = None) -> bool:
        """Update rule status and error if any"""
        update = {
            "status": status,
            "last_updated": time.time()
        }
        if error:
            update["last_error"] = error
        return await self.update_rule(rule_id, update)

class RuleStorage:
    _instance = None

    def __init__(self, mongo_client):
        self.mongo_client = mongo_client
        self.rules_collection = mongo_client.db.watch_rules

    @classmethod
    async def get_instance(cls) -> 'RuleStorage':
        """Get singleton instance"""
        if not cls._instance:
            mongo_client = await MongoClient.get_instance()
            cls._instance = cls(mongo_client)
            logger.info("[RuleStorage] Created new instance")
        return cls._instance

    async def get_active_rules(self, watch_type: str = None) -> List[Dict]:
        """Get all active rules, optionally filtered by watch_type"""
        try:
            query = {"active": True}
            if watch_type:
                query["watch_type"] = watch_type
                
            cursor = self.rules_collection.find(query)
            rules = await cursor.to_list(length=None)
            return json.loads(json.dumps(rules, cls=MongoJSONEncoder))
        except Exception as e:
            logger.error(f"[RuleStorage] Error getting active rules: {e}")
            return []

    async def save_rule(self, rule_data: Dict) -> str:
        """Save a new rule"""
        try:
            result = await self.rules_collection.insert_one(rule_data)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"[RuleStorage] Error saving rule: {e}")
            raise

    async def update_rule(self, rule_id: str, update_data: Dict) -> bool:
        """Update an existing rule"""
        try:
            result = await self.rules_collection.update_one(
                {"rule_id": rule_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"[RuleStorage] Error updating rule: {e}")
            return False

    async def deactivate_rule(self, rule_id: str) -> bool:
        """Deactivate a rule"""
        try:
            result = await self.rules_collection.update_one(
                {"rule_id": rule_id},
                {"$set": {"active": False}}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"[RuleStorage] Error deactivating rule: {e}")
            return False

    async def update_rule_status(self, rule_id: str, status: str, error: str = None) -> bool:
        """Update rule status and optional error message"""
        try:
            update_data = {
                "status": status,
                "last_updated": time.time()
            }
            if error:
                update_data["last_error"] = error
                
            result = await self.rules_collection.update_one(
                {"rule_id": rule_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"[RuleStorage] Error updating rule status: {e}")
            return False

async def get_mongo() -> MongoClient:
    """Get MongoDB client instance"""
    return await MongoClient.get_instance()
