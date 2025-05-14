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
social_sentiment_interval = int(os.getenv('SOCIAL_SENTIMENT_INTERVAL', "4"))

# Redis keys for storing hashes
LAST_SENTIMENT_HASH_KEY = 'last_sentiment_hash'
AIRDROP_HASHES_SET = 'airdrop_notification_hashes'

async def scheduled_job():
    try:
        logger.info("Starting scheduled notification job")
        
        logger.info("Fetching market alerts...")
        # alerts = await fetch_alerts()
        # logger.info(f"Fetched {len(alerts)} market alerts")
        
        logger.info("Fetching airdrop alerts...")
        airdrops_data = await fetch_airdrop_alerts()
        logger.info(f"Fetched airdrop alerts data: {airdrops_data}")
        
        # Filter out duplicate airdrops
        unique_airdrops = []
        if airdrops_data and isinstance(airdrops_data, dict) and 'airdrops' in airdrops_data:
            for airdrop in airdrops_data['airdrops']:
                logger.info(f"Processing airdrop: {airdrop}")
                if not isinstance(airdrop, dict):
                    logger.warning(f"Invalid airdrop data: {airdrop}")
                    continue
                    
                # Create a hash of the airdrop text
                airdrop_text = airdrop.get('text', '')
                if not airdrop_text:
                    continue
                    
                airdrop_hash = hashlib.md5(airdrop_text.encode()).hexdigest()
                
                # Check if this hash exists in Redis
                is_duplicate = await redis_client.sismember(AIRDROP_HASHES_SET, airdrop_hash)
                
                if not is_duplicate:
                    # Add to unique airdrops and store hash in Redis
                    unique_airdrops.append({
                        'alert_type': 'airdrop',
                        'text': airdrop_text,
                        'post_link': airdrop.get('post_link', '')
                    })
                    await redis_client.sadd(AIRDROP_HASHES_SET, airdrop_hash)
                    # Set expiration for the hash (e.g., 7 days)
                    await redis_client.expire(AIRDROP_HASHES_SET, 7 * 24 * 60 * 60)
        logger.info(f"Unique airdrops: {unique_airdrops}")
        if unique_airdrops and len(unique_airdrops) > 0:
            logger.info(f"Sending notifications for {len(unique_airdrops)} unique airdrops...")
            await notify_users([], unique_airdrops)
            logger.info("Notifications sent successfully")
        else:
            logger.info("No new unique airdrops to notify")
            
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
        scheduler.add_job(scheduled_job, 'interval', hours=schedule_interval)
        
        # Add the social sentiment job (every 4 hours)
        scheduler.add_job(social_sentiment_job, 'interval', hours=social_sentiment_interval)
        
        scheduler.start()
        logger.info("Notification scheduler started successfully")
    except Exception as e:
        logger.error(f"Error starting scheduler: {str(e)}")
        raise 