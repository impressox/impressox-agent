import redis
import json
import logging
from dotenv import load_dotenv
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', '')
REDIS_DB = int(os.getenv('REDIS_DB', 0))

# Redis channel
NOTIFY_CONTROL_CHANNEL = 'notify_control'

def get_redis_client():
    """Get Redis client instance"""
    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            db=REDIS_DB,
            decode_responses=True
        )
        # Test connection
        client.ping()
        return client
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {str(e)}")
        raise

def publish_notify_on(user_id: str, chat_type: str):
    """Publish notification on message to Redis"""
    try:
        client = get_redis_client()
        message = {
            'user_id': user_id,
            'active': True
        }
        client.publish(NOTIFY_CONTROL_CHANNEL, json.dumps(message))
        logger.info(f"Published notification on message for {chat_type} {user_id}")
    except Exception as e:
        logger.error(f"Error publishing notify on message: {str(e)}")
        raise

def publish_notify_off(user_id: str, chat_type: str):
    """Publish notification off message to Redis"""
    try:
        client = get_redis_client()
        message = {
            'user_id': user_id,
            'active': False
        }
        client.publish(NOTIFY_CONTROL_CHANNEL, json.dumps(message))
        logger.info(f"Published notification off message for {chat_type} {user_id}")
    except Exception as e:
        logger.error(f"Error publishing notify off message: {str(e)}")
        raise 