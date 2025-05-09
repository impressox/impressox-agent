import logging
import json
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from app.configs.config import app_configs

logger = logging.getLogger(__name__)

class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB objects"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

class RuleStorage:
    _instance = None
    _initialized = False

    def __init__(self):
        self.mongo = None
        self.db = None
        self.collection = None

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
            # Get MongoDB config from app_configs
            mongodb_config = app_configs.get_mongo_config()
            mongodb_url = mongodb_config["connection"]["url"]
            db_name = mongodb_config["db_name"]
            
            # Create MongoDB client
            self.mongo = AsyncIOMotorClient(mongodb_url)
            self.db = self.mongo[db_name]
            self.collection = self.db["watch_rules"]
            
            # Create indexes
            await self.collection.create_index([("user_id", 1)])
            await self.collection.create_index([("watch_type", 1)])
            await self.collection.create_index([("active", 1)])
            
            logger.info("[RuleStorage] Successfully initialized MongoDB connection")
        except Exception as e:
            logger.error(f"[RuleStorage] Error initializing MongoDB connection: {e}")
            raise

    async def close(self):
        """Close MongoDB connection"""
        if self.mongo:
            self.mongo.close()
            self.mongo = None
            self.db = None
            self.collection = None
            self._instance = None

    async def save_rule(self, rule: Dict) -> bool:
        """Save a watch rule to MongoDB"""
        try:
            result = await self.collection.insert_one(rule)
            return bool(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Error saving rule: {e}")
            return False

    async def get_rule(self, rule_id: str) -> Optional[Dict]:
        """Get a rule by ID"""
        try:
            rule = await self.collection.find_one({"rule_id": rule_id})
            return rule
        except PyMongoError as e:
            logger.error(f"Error getting rule {rule_id}: {e}")
            return None

    async def get_user_rules(self, user_id: str, active_only: bool = True) -> List[Dict]:
        """Get all rules for a user"""
        try:
            query = {"user_id": user_id}
            if active_only:
                query["active"] = True
            cursor = self.collection.find(query)
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Error getting rules for user {user_id}: {e}")
            return []

    async def get_active_rules(self, user_id: str, watch_type: str = None) -> List[Dict]:
        """Get all active rules for a user"""
        try:
            # Initialize if not already initialized
            if self.collection is None:
                await self.initialize()

            query = {
                "user_id": user_id,
                "active": True
            }
            if watch_type:
                query["watch_type"] = watch_type

            cursor = self.collection.find(query)
            rules = await cursor.to_list(length=None)
            return rules
        except Exception as e:
            logger.error(f"[RuleStorage] Error getting active rules: {e}")
            return []

    async def get_active_rules_by_type(self, watch_type: str) -> List[Dict]:
        """Get all active rules of a specific type"""
        try:
            cursor = self.collection.find({
                "watch_type": watch_type,
                "active": True
            })
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Error getting rules of type {watch_type}: {e}")
            return []

    async def update_rule(self, rule_id: str, update: Dict) -> bool:
        """Update a rule"""
        try:
            result = await self.collection.update_one(
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

    async def delete_rule(self, rule_id: str) -> bool:
        """Delete a rule"""
        try:
            result = await self.collection.delete_one({"rule_id": rule_id})
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Error deleting rule {rule_id}: {e}")
            return False
