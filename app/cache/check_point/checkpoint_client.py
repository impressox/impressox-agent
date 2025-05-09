import redis
from app.cache.check_point.redis_checkpointer import RedisSaver
from app.configs import app_configs

_redis_instance = None
_memory_instance = None

def get_memory_saver():
    global _redis_instance, _memory_instance
    if _redis_instance is None:
        redis_config = app_configs.get_redis_config()
        _redis_instance = redis.Redis(
            **redis_config["connection"],
            db=redis_config["db"]
        )
        _memory_instance = RedisSaver(conn=_redis_instance)
    return _memory_instance
