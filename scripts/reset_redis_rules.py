import asyncio
import logging
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def reset_redis_rules():
    """Reset all Redis keys related to watch rules"""
    try:
        # Get Redis client
        redis = await RedisClient.get_instance()
        logger.info("Connected to Redis")

        # Patterns to match
        patterns = [
            # Active rules for all watch types
            "watch:active:token:*",    # Token rules
            "watch:active:wallet:*",   # Wallet rules
            "watch:active:airdrop:*",  # Airdrop rules
            "watch:active:market:*",   # Legacy market rules
            
            # Watch events for all types
            "token_watch:*",           # Token watch events
            "wallet_watch:*",          # Wallet watch events
            "airdrop_watch:*",         # Airdrop watch events
            "market_watch:*",          # Legacy market watch events
            
            # Notification related keys
            "notify:recent:*",         # Recent notifications
            "notify:dedup:*",          # Deduplication keys
            "notify:status:*",         # Notification status
            "rate_limit:*",            # Rate limit keys
            
            # Rule processing keys
            "rule:active:*",           # Active rules
            "rule:processing:*",       # Rules being processed
            "rule:matched:*",          # Matched rules
            "rule:failed:*"            # Failed rules
        ]

        # Delete keys matching patterns
        total_deleted = 0
        for pattern in patterns:
            keys = await redis.keys(pattern)
            if keys:
                logger.info(f"Found {len(keys)} keys matching pattern: {pattern}")
                for key in keys:
                    await redis.delete(key)
                    total_deleted += 1
                    logger.info(f"Deleted key: {key}")
            else:
                logger.info(f"No keys found matching pattern: {pattern}")

        logger.info(f"Successfully reset all Redis rules. Total keys deleted: {total_deleted}")
        
    except Exception as e:
        logger.error(f"Error resetting Redis rules: {e}")
        raise
    finally:
        # Close Redis connection
        await RedisClient.close()

if __name__ == "__main__":
    asyncio.run(reset_redis_rules()) 