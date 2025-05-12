import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from workers.notify_worker.data_fetcher import fetch_alerts, fetch_airdrop_alerts, fetch_social_sentiment
from workers.notify_worker.telegram_notifier import notify_users
from workers.notify_worker.store import redis_client
import os
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

schedule_interval = int(os.getenv('SCHEDULE_INTERVAL', "1"))
social_sentiment_interval = int(os.getenv('SOCIAL_SENTIMENT_INTERVAL', "1"))

# Redis key for storing last sentiment hash
LAST_SENTIMENT_HASH_KEY = 'last_sentiment_hash'

async def scheduled_job():
    try:
        logger.info("Starting scheduled notification job")
        
        logger.info("Fetching market alerts...")
        alerts = await fetch_alerts()
        logger.info(f"Fetched {len(alerts)} market alerts")
        
        logger.info("Fetching airdrop alerts...")
        airdrops = await fetch_airdrop_alerts()
        logger.info(f"Fetched {len(airdrops)} airdrop alerts")
        
        logger.info("Sending notifications...")
        await notify_users(alerts, airdrops)
        logger.info("Notifications sent successfully")
    except Exception as e:
        logger.error(f"Error in scheduled job: {str(e)}")
        raise

async def social_sentiment_job():
    try:
        logger.info("Starting social sentiment analysis job")
        
        logger.info("Fetching social media sentiment data...")
        sentiment = await fetch_social_sentiment()
        if sentiment:
            # Calculate hash of current sentiment
            sentiment_hash = hashlib.md5(str(sentiment).encode()).hexdigest()
            
            # Get last sentiment hash from Redis
            last_hash = await redis_client.get(LAST_SENTIMENT_HASH_KEY)
            
            # Only send notification if sentiment is different
            if sentiment_hash != last_hash:
                logger.info("Sending social sentiment notification...")
                await notify_users([sentiment], [])
                # Store new hash in Redis
                await redis_client.set(LAST_SENTIMENT_HASH_KEY, sentiment_hash)
                logger.info("Social sentiment notification sent successfully")
            else:
                logger.info("Skipping notification - sentiment is the same as last time")
        else:
            logger.warning("No social sentiment data available to send")
    except Exception as e:
        logger.error(f"Error in social sentiment job: {str(e)}")
        raise

def schedule_notify():
    try:
        logger.info("Initializing notification scheduler")
        scheduler = AsyncIOScheduler()
        
        # Create a new event loop for the scheduler
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Add the regular notification job
        # scheduler.add_job(scheduled_job, 'interval', minutes=schedule_interval)
        
        # Add the social sentiment job (every 4 hours)
        scheduler.add_job(social_sentiment_job, 'interval', hours=social_sentiment_interval)
        
        scheduler.start()
        logger.info("Notification scheduler started successfully")
    except Exception as e:
        logger.error(f"Error starting scheduler: {str(e)}")
        raise 