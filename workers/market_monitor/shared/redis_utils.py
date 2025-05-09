import logging
import json
import asyncio
from typing import Dict, List, Optional, Any, Callable
from redis.asyncio import Redis
from redis.exceptions import RedisError
from bson import ObjectId
from workers.market_monitor.utils.config import get_config

logger = logging.getLogger(__name__)

class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB objects"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

def mongo_json_decoder(obj):
    """Custom JSON decoder for MongoDB objects"""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if isinstance(value, str) and len(value) == 24:  # ObjectId length
                try:
                    obj[key] = ObjectId(value)
                except:
                    pass
    return obj

class RedisClient:
    """Redis client wrapper with utility methods"""
    
    _instance = None
    _redis = None
    
    def __init__(self):
        self.config = get_config()
        
    @classmethod
    async def get_instance(cls) -> 'RedisClient':
        """Get singleton instance"""
        if not cls._instance:
            cls._instance = cls()
            await cls._instance.connect()
        return cls._instance
        
    async def connect(self):
        """Connect to Redis"""
        if not self._redis:
            try:
                self._redis = Redis.from_url(
                    self.config.get_redis_url(),
                    decode_responses=True
                )
                logger.info("Connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
                
    @classmethod
    async def close(cls):
        """Close Redis connection"""
        if cls._instance and cls._instance._redis:
            await cls._instance._redis.close()
            cls._instance._redis = None
            cls._instance = None
            logger.info("Closed Redis connection")
            
    async def get(self, key: str) -> Optional[str]:
        """Get value from Redis"""
        if not self._redis:
            await self.connect()
        try:
            value = await self._redis.get(key)
            if value:
                try:
                    return json.loads(value, object_hook=mongo_json_decoder)
                except json.JSONDecodeError:
                    return value
            return None
        except RedisError as e:
            logger.error(f"Error getting key {key}: {e}")
            return None
        
    async def set(self, key: str, value: Any, ex: Optional[int] = None):
        """Set value in Redis"""
        if not self._redis:
            await self.connect()
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, cls=MongoJSONEncoder)
            await self._redis.set(key, value, ex=ex)
        except RedisError as e:
            logger.error(f"Error setting key {key}: {e}")
            raise
        
    async def delete(self, key: str):
        """Delete key from Redis"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.delete(key)
        except RedisError as e:
            logger.error(f"Error deleting key {key}: {e}")
            raise
        
    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis"""
        if not self._redis:
            await self.connect()
        try:
            return bool(await self._redis.exists(key))
        except RedisError as e:
            logger.error(f"Error checking key {key}: {e}")
            return False
        
    async def set_json(self, key: str, value: Dict[str, Any], expire: Optional[int] = None):
        """Set JSON value in Redis"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.set(key, json.dumps(value, cls=MongoJSONEncoder), ex=expire)
        except RedisError as e:
            logger.error(f"Error setting JSON key {key}: {e}")
            raise
        
    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Get JSON value from Redis"""
        if not self._redis:
            await self.connect()
        try:
            value = await self._redis.get(key)
            return json.loads(value, object_hook=mongo_json_decoder) if value else None
        except RedisError as e:
            logger.error(f"Error getting JSON key {key}: {e}")
            return None
        
    async def lpush(self, key: str, value: str):
        """Push value to list head"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.lpush(key, value)
        except RedisError as e:
            logger.error(f"Error pushing to list {key}: {e}")
            raise
        
    async def rpush(self, key: str, value: str):
        """Push value to list tail"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.rpush(key, value)
        except RedisError as e:
            logger.error(f"Error pushing to list {key}: {e}")
            raise
        
    async def lpop(self, key: str) -> Optional[str]:
        """Pop value from list head"""
        if not self._redis:
            await self.connect()
        try:
            return await self._redis.lpop(key)
        except RedisError as e:
            logger.error(f"Error popping from list {key}: {e}")
            return None
        
    async def rpop(self, key: str) -> Optional[str]:
        """Pop value from list tail"""
        if not self._redis:
            await self.connect()
        try:
            return await self._redis.rpop(key)
        except RedisError as e:
            logger.error(f"Error popping from list {key}: {e}")
            return None
        
    async def lrange(self, key: str, start: int, end: int) -> List[str]:
        """Get list range"""
        if not self._redis:
            await self.connect()
        try:
            return await self._redis.lrange(key, start, end)
        except RedisError as e:
            logger.error(f"Error getting list range {key}: {e}")
            return []
        
    async def llen(self, key: str) -> int:
        """Get list length"""
        if not self._redis:
            await self.connect()
        try:
            return await self._redis.llen(key)
        except RedisError as e:
            logger.error(f"Error getting list length {key}: {e}")
            return 0
        
    async def sadd(self, key: str, value: str):
        """Add value to set"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.sadd(key, value)
        except RedisError as e:
            logger.error(f"Error adding to set {key}: {e}")
            raise
        
    async def srem(self, key: str, value: str):
        """Remove value from set"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.srem(key, value)
        except RedisError as e:
            logger.error(f"Error removing from set {key}: {e}")
            raise
        
    async def smembers(self, key: str) -> List[str]:
        """Get set members"""
        if not self._redis:
            await self.connect()
        try:
            return await self._redis.smembers(key)
        except RedisError as e:
            logger.error(f"Error getting set members {key}: {e}")
            return []
        
    async def sismember(self, key: str, value: str) -> bool:
        """Check if value is in set"""
        if not self._redis:
            await self.connect()
        try:
            return bool(await self._redis.sismember(key, value))
        except RedisError as e:
            logger.error(f"Error checking set membership {key}: {e}")
            return False
        
    async def hset(self, key: str, field: str, value: Any):
        """Set hash field"""
        if not self._redis:
            await self.connect()
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, cls=MongoJSONEncoder)
            await self._redis.hset(key, field, value)
        except RedisError as e:
            logger.error(f"Error setting hash field {key}.{field}: {e}")
            raise
        
    async def hget(self, key: str, field: str) -> Optional[Any]:
        """Get hash field"""
        if not self._redis:
            await self.connect()
        try:
            value = await self._redis.hget(key, field)
            if value:
                try:
                    return json.loads(value, object_hook=mongo_json_decoder)
                except json.JSONDecodeError:
                    return value
            return None
        except RedisError as e:
            logger.error(f"Error getting hash field {key}.{field}: {e}")
            return None
        
    async def hgetall(self, key: str) -> Dict[str, Any]:
        """Get all hash fields"""
        if not self._redis:
            await self.connect()
        try:
            result = await self._redis.hgetall(key)
            if result:
                return {k: json.loads(v, object_hook=mongo_json_decoder) if isinstance(v, str) else v 
                       for k, v in result.items()}
            return {}
        except RedisError as e:
            logger.error(f"Error getting hash {key}: {e}")
            return {}
        
    async def hdel(self, key: str, field: str):
        """Delete hash field"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.hdel(key, field)
        except RedisError as e:
            logger.error(f"Error deleting hash field {key}.{field}: {e}")
            raise
        
    async def expire(self, key: str, seconds: int):
        """Set key expiration"""
        if not self._redis:
            await self.connect()
        try:
            await self._redis.expire(key, seconds)
        except RedisError as e:
            logger.error(f"Error setting expiration for key {key}: {e}")
            raise
        
    async def ttl(self, key: str) -> int:
        """Get key TTL"""
        if not self._redis:
            await self.connect()
        try:
            return await self._redis.ttl(key)
        except RedisError as e:
            logger.error(f"Error getting TTL for key {key}: {e}")
            return -1
        
    async def keys(self, pattern: str) -> List[str]:
        """Get keys matching pattern"""
        if not self._redis:
            await self.connect()
        try:
            return await self._redis.keys(pattern)
        except RedisError as e:
            logger.error(f"Error getting keys matching pattern {pattern}: {e}")
            return []
        
    async def scan_iter(self, pattern: str = "*", count: int = 100):
        """Scan keys matching pattern"""
        if not self._redis:
            await self.connect()
        try:
            async for key in self._redis.scan_iter(match=pattern, count=count):
                yield key
        except RedisError as e:
            logger.error(f"Error scanning keys matching pattern {pattern}: {e}")
            
    async def publish(self, channel: str, message: Any):
        """Publish message to channel"""
        if not self._redis:
            await self.connect()
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, cls=MongoJSONEncoder)
            await self._redis.publish(channel, message)
        except RedisError as e:
            logger.error(f"Error publishing to channel {channel}: {e}")
            raise
        
    async def subscribe(self, channel: str, callback: Callable):
        """Subscribe to channel with callback"""
        if not self._redis:
            await self.connect()
        try:
            pubsub = self._redis.pubsub()
            await pubsub.subscribe(channel)
            # Run pubsub listener in background
            asyncio.create_task(self._listen(pubsub, callback, channel))
        except RedisError as e:
            logger.error(f"Error subscribing to channel {channel}: {e}")
            raise

    async def _listen(self, pubsub, callback: Callable, channel: str) -> None:
        """Listen for messages on pubsub connection"""
        while True:
            try:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    # Extract data from message
                    data = message.get('data')
                    if isinstance(data, str):
                        try:
                            data = json.loads(data, object_hook=mongo_json_decoder)
                        except json.JSONDecodeError:
                            pass
                    # Call callback with channel and data
                    await callback(channel, data)
                await asyncio.sleep(0.001)  # Prevent busy loop
            except Exception as e:
                logger.error(f"Error in pubsub listener: {e}")
                await asyncio.sleep(1)  # Error backoff
