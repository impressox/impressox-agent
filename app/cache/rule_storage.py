import logging
from typing import Dict, List, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from app.configs.config import app_configs

logger = logging.getLogger(__name__)

class RuleStorage:
    _instance = None
    _client = None
    _db = None

    @classmethod
    async def get_instance(cls) -> 'RuleStorage':
        """Get singleton instance"""
        if not cls._instance:
            cls._instance = cls()
            try:
                # Get MongoDB config from app_configs
                mongodb_config = app_configs.get_mongo_config()
                mongodb_url = mongodb_config["connection"]["url"]
                db_name = mongodb_config["db_name"]
                cls._client = AsyncIOMotorClient(mongodb_url)
                cls._db = cls._client[db_name]
                # Create indexes
                await cls._db.watch_rules.create_index([("user_id", 1)])
                await cls._db.watch_rules.create_index([("watch_type", 1)])
                await cls._db.watch_rules.create_index([("active", 1)])
            except Exception as e:
                logger.error(f"Error initializing MongoDB: {e}")
                raise
        return cls._instance

    async def close(self):
        """Close MongoDB connection"""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None
            self._instance = None

    async def save_rule(self, rule: Dict) -> bool:
        """Save a watch rule to MongoDB"""
        try:
            result = await self._db.watch_rules.insert_one(rule)
            return bool(result.inserted_id)
        except PyMongoError as e:
            logger.error(f"Error saving rule: {e}")
            return False

    async def get_rule(self, rule_id: str) -> Optional[Dict]:
        """Get a rule by ID"""
        try:
            rule = await self._db.watch_rules.find_one({"rule_id": rule_id})
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
            cursor = self._db.watch_rules.find(query)
            return await cursor.to_list(length=None)
        except PyMongoError as e:
            logger.error(f"Error getting rules for user {user_id}: {e}")
            return []

    async def get_active_rules_by_type(self, watch_type: str) -> List[Dict]:
        """Get all active rules of a specific type"""
        try:
            cursor = self._db.watch_rules.find({
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
            result = await self._db.watch_rules.update_one(
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
            result = await self._db.watch_rules.delete_one({"rule_id": rule_id})
            return result.deleted_count > 0
        except PyMongoError as e:
            logger.error(f"Error deleting rule {rule_id}: {e}")
            return False
