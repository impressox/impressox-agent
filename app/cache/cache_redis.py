import redis
import json
import pickle
import asyncio
from typing import Callable, Dict, Any
from bson import ObjectId
from app.configs import app_configs

class MongoJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for MongoDB objects"""
    def default(self, obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        return super().default(obj)

class RedisClient:
    def __init__(self):
        """Initialize Redis connection"""
        redis_config = app_configs.get_redis_config()
        connection = redis_config["connection"]
        host = connection["host"]
        port = connection["port"]
        password = connection["password"]
        db = redis_config["db"]
        decode_responses = connection["decode_responses"]

        # Main client for regular operations
        self.redis = redis.StrictRedis(
            host=host, 
            port=port, 
            password=password, 
            db=db, 
            decode_responses=decode_responses
        )
        # Pubsub client for subscriptions
        self.pubsub = self.redis.pubsub()
        self.cache_key_prefix = redis_config["cache_key_prefix"]

    def set(self, key: str, value: Any, expire: int = None) -> bool:
        """Save value to Redis with optional expiration time"""
        try:
            key = self.cache_key_prefix + key
            # Convert dictionary to JSON string if value is a dictionary
            if isinstance(value, dict):
                value = json.dumps(value, cls=MongoJSONEncoder)
            
            if expire:
                return self.redis.set(key, value, ex=expire)
            return self.redis.set(key, value)
        except Exception as e:
            print(f"Error setting key {key}: {e}")
            return False

    def get(self, key: str) -> Any:
        """Get value from Redis"""
        try:
            key = self.cache_key_prefix + key
            value = self.redis.get(key)
            if value is None:
                return None
            
            if isinstance(value, str):
                # Try to decode JSON string back to dictionary
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value  # Return as-is if not JSON
            else:
                return value
        except Exception as e:
            print(f"Error getting key {key}: {e}")
            return None

    def hset(self, name: str, key: str, value: Any) -> bool:
        """Set hash field to value"""
        try:
            name = self.cache_key_prefix + name
            if isinstance(value, (dict, list)):
                value = json.dumps(value, cls=MongoJSONEncoder)
            return bool(self.redis.hset(name, key, value))
        except Exception as e:
            print(f"Error setting hash field {key} in {name}: {e}")
            return False

    def hget(self, name: str, key: str) -> Any:
        """Get value of hash field"""
        try:
            name = self.cache_key_prefix + name
            value = self.redis.hget(name, key)
            if value is None:
                return None
            
            if isinstance(value, str):
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return value
        except Exception as e:
            print(f"Error getting hash field {key} from {name}: {e}")
            return None

    def hgetall(self, name: str) -> Dict[str, Any]:
        """Get all fields and values in hash"""
        try:
            name = self.cache_key_prefix + name
            result = self.redis.hgetall(name)
            if not result:
                return {}
            
            # Try to decode JSON values
            decoded = {}
            for key, value in result.items():
                if isinstance(value, str):
                    try:
                        decoded[key] = json.loads(value)
                    except json.JSONDecodeError:
                        decoded[key] = value
                else:
                    decoded[key] = value
            return decoded
        except Exception as e:
            print(f"Error getting all hash fields from {name}: {e}")
            return {}

    def hdel(self, name: str, key: str) -> bool:
        """Delete hash field"""
        try:
            name = self.cache_key_prefix + name
            return bool(self.redis.hdel(name, key))
        except Exception as e:
            print(f"Error deleting hash field {key} from {name}: {e}")
            return False

    def push_to_queue(self, queue_name: str, value: Any) -> bool:
        """Push value to list (Queue)"""
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value, cls=MongoJSONEncoder)
            return bool(self.redis.lpush(queue_name, value))
        except Exception as e:
            print(f"Error pushing to queue {queue_name}: {e}")
            return False

    def pop_from_queue(self, queue_name: str) -> Any:
        """Pop value from list (Queue)"""
        try:
            value = self.redis.rpop(queue_name)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            print(f"Error popping from queue {queue_name}: {e}")
            return None

    def publish(self, channel: str, message: Any) -> bool:
        """Publish message to channel"""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, cls=MongoJSONEncoder)
            return bool(self.redis.publish(channel, message))
        except Exception as e:
            print(f"Error publishing to channel {channel}: {e}")
            return False

    async def subscribe(self, channel: str, callback: Callable[[str, Any], None]) -> None:
        """Subscribe to channel with callback"""
        try:
            self.pubsub.subscribe(**{channel: self._message_handler(callback)})
            # Run pubsub listener in background
            asyncio.create_task(self._listen())
        except Exception as e:
            print(f"Error subscribing to channel {channel}: {e}")

    def _message_handler(self, callback: Callable[[str, Any], None]) -> Callable:
        """Create message handler for pubsub"""
        def handler(message):
            try:
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, str):
                        try:
                            data = json.loads(data)
                        except json.JSONDecodeError:
                            pass
                    callback(message["channel"], data)
            except Exception as e:
                print(f"Error handling pubsub message: {e}")
        return handler

    async def _listen(self) -> None:
        """Listen for pubsub messages"""
        while True:
            try:
                self.pubsub.get_message()
                await asyncio.sleep(0.001)  # Prevent busy loop
            except Exception as e:
                print(f"Error in pubsub listener: {e}")
                await asyncio.sleep(1)  # Error backoff

    def close(self) -> None:
        """Close Redis connections"""
        try:
            self.pubsub.close()
            self.redis.close()
        except Exception as e:
            print(f"Error closing Redis connections: {e}")

_redis_instance = None
def get_redis_client() -> RedisClient:
    """Get Redis client instance"""
    global _redis_instance
    if _redis_instance is None:
        _redis_instance = RedisClient()
    return _redis_instance
