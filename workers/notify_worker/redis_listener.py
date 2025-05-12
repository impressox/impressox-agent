import asyncio
import json
import logging
from workers.notify_worker.store import add_active_user, remove_active_user, redis_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CHANNEL = 'notify_control'

async def listen_notify_control():
    try:
        logger.info(f"Starting Redis pubsub listener on channel: {CHANNEL}")
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(CHANNEL)
        logger.info(f"Successfully subscribed to channel: {CHANNEL}")
        
        async for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    logger.debug(f"Received message: {message['data']}")
                    data = json.loads(message['data'])
                    user_id = data.get('user_id')
                    active = data.get('active')
                    
                    if user_id is not None and active is not None:
                        logger.info(f"Processing notification control for user {user_id}, active: {active}")
                        if active:
                            await add_active_user(user_id)
                            logger.info(f"Added user {user_id} to active users")
                        else:
                            await remove_active_user(user_id)
                            logger.info(f"Removed user {user_id} from active users")
                    else:
                        logger.warning(f"Invalid message format: {data}")
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to decode message: {message['data']}, error: {str(e)}")
                except Exception as e:
                    logger.error(f"Error processing pubsub message: {str(e)}")
    except Exception as e:
        logger.error(f"Error in listen_notify_control: {str(e)}")
        raise 