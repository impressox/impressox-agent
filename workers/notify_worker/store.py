import redis.asyncio as aioredis
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
import logging
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

load_dotenv()

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017')
MONGO_DB = os.getenv('MONGO_DB', 'cpx_dev')

logger.info(f"Initializing Redis connection with URL: {REDIS_URL}")
try:
    redis_client = aioredis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Redis client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize Redis client: {str(e)}")
    raise

logger.info(f"Initializing MongoDB connection with URI: {MONGO_URI}")
try:
    mongo_client = AsyncIOMotorClient(MONGO_URI)
    db = mongo_client[MONGO_DB]
    users_col = db['users']
    logger.info("MongoDB client initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize MongoDB client: {str(e)}")
    raise

ACTIVE_USERS_SET = 'notification_active_users'

async def initialize_active_users():
    """Load all active users from MongoDB into Redis when worker starts"""
    try:
        logger.info("Loading active users from MongoDB...")
        # Find all users with active=True
        cursor = users_col.find({'active': True}, {'telegram_id': 1})
        active_users = [str(doc['telegram_id']) async for doc in cursor]
        
        if active_users:
            # Add all active users to Redis set
            await redis_client.sadd(ACTIVE_USERS_SET, *active_users)
            logger.info(f"Loaded {len(active_users)} active users from MongoDB to Redis")
        else:
            logger.info("No active users found in MongoDB")
            
    except Exception as e:
        logger.error(f"Error loading active users from MongoDB: {str(e)}")
        raise

async def get_active_users():
    try:
        logger.info("Fetching active users from Redis")
        active_users = await redis_client.smembers(ACTIVE_USERS_SET)
        
        if not active_users:
            logger.info("No active users found in Redis, fetching from MongoDB")
            # Nếu Redis không có, lấy từ MongoDB (chỉ lấy active=True)
            cursor = users_col.find({'active': True}, {'telegram_id': 1})
            active_users = [str(doc['telegram_id']) async for doc in cursor]
            
            # Cập nhật lại Redis
            if active_users:
                logger.info(f"Found {len(active_users)} active users in MongoDB, updating Redis")
                await redis_client.sadd(ACTIVE_USERS_SET, *active_users)
            else:
                logger.info("No active users found in MongoDB")
        else:
            logger.info(f"Found {len(active_users)} active users in Redis")
            
        return active_users
    except Exception as e:
        logger.error(f"Error in get_active_users: {str(e)}")
        raise

async def add_active_user(user_id):
    """Add a user to active users and push their rules back to Redis"""
    try:
        # Add to Redis set
        await redis_client.sadd(ACTIVE_USERS_SET, user_id)
        
        # Update MongoDB
        await users_col.update_one(
            {'telegram_id': int(user_id)}, 
            {'$set': {'active': True}}, 
            upsert=True
        )
    except Exception as e:
        logger.error(f"Error adding active user {user_id}: {str(e)}")
        raise

async def remove_active_user(user_id):
    await redis_client.srem(ACTIVE_USERS_SET, user_id)
    await users_col.update_one({'telegram_id': int(user_id)}, {'$set': {'active': False}}, upsert=True) 