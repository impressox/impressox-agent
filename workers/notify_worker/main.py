import asyncio
import logging
from workers.notify_worker.scheduler import schedule_notify
from workers.notify_worker.redis_listener import listen_notify_control

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    try:
        logger.info("Starting notify worker...")
        logger.info("Initializing scheduler...")
        schedule_notify()
        logger.info("Scheduler started successfully")
        
        logger.info("Starting Redis listener...")
        await listen_notify_control()
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
        raise

if __name__ == '__main__':
    try:
        logger.info("Starting notify worker application")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        raise 