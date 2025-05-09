import asyncio
import logging
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_redis_rules():
    """Reset all Redis keys related to market watch rules"""
    try:
        # Get Redis client
        redis = await RedisClient.get_instance()
        logger.info("Connected to Redis")

        # Patterns to match
        patterns = [
            "watch:active:token:*",  # Active rules for tokens
            "market_watch:*",        # Market watch events
            "notify:recent:*",       # Recent notifications
            "notify:dedup:*",        # Deduplication keys
            "notify:status:*",       # Notification status
            "rate_limit:*"           # Rate limit keys
        ]

        # Delete keys matching patterns
        for pattern in patterns:
            keys = await redis.keys(pattern)
            if keys:
                logger.info(f"Found {len(keys)} keys matching pattern: {pattern}")
                for key in keys:
                    await redis.delete(key)
                    logger.info(f"Deleted key: {key}")
            else:
                logger.info(f"No keys found matching pattern: {pattern}")

        logger.info("Successfully reset all Redis rules")
        
    except Exception as e:
        logger.error(f"Error resetting Redis rules: {e}")
        raise
    finally:
        # Close Redis connection
        await RedisClient.close()

if __name__ == "__main__":
    asyncio.run(reset_redis_rules()) 