import asyncio
import logging
import signal
import sys
import os
from typing import List, Optional
from workers.market_monitor.services.worker_pool import WorkerPool
from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.config import get_config
from workers.market_monitor.utils.mongo import MongoClient
from workers.market_monitor.processors.rule_matcher import RuleMatcher
from workers.market_monitor.processors.notify_dispatcher import NotifyDispatcher
from workers.market_monitor.processors.rule_processor import RuleProcessor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join('logs', 'market_monitor.log'))
    ]
)

# Set logging level for all loggers
logging.getLogger('workers.market_monitor').setLevel(logging.INFO)
logging.getLogger('workers.market_monitor.services').setLevel(logging.INFO)
logging.getLogger('workers.market_monitor.processors').setLevel(logging.INFO)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class MarketMonitor:
    def __init__(self):
        self.worker_pool = None
        self.redis_client = None
        self.rule_matcher = None
        self.notify_dispatcher = None
        self.rule_processor = None
        self.shutdown_event = asyncio.Event()
        self.config = get_config()
        self._shutdown_tasks = []

    async def initialize(self):
        """Initialize services and connections"""
        try:
            logger.info("[MarketMonitor] Initializing services...")
            
            # Initialize Redis
            logger.info("[MarketMonitor] Connecting to Redis...")
            self.redis_client = await RedisClient.get_instance()
            logger.info("[MarketMonitor] Redis connection established")
            
            # Initialize MongoDB
            logger.info("[MarketMonitor] Connecting to MongoDB...")
            await MongoClient.get_instance()
            logger.info("[MarketMonitor] MongoDB connection established")
            
            # Initialize processors
            logger.info("[MarketMonitor] Initializing processors...")
            self.rule_matcher = RuleMatcher()
            self.notify_dispatcher = NotifyDispatcher()
            self.rule_processor = RuleProcessor()
            logger.info("[MarketMonitor] Processors initialized")
            
            # Initialize worker pool
            logger.info("[MarketMonitor] Starting worker pool...")
            self.worker_pool = WorkerPool()
            await self.worker_pool.start()
            logger.info("[MarketMonitor] Worker pool started")
            
            logger.info("[MarketMonitor] All services initialized successfully")
            
        except Exception as e:
            logger.error(f"[MarketMonitor] Error initializing services: {e}")
            await self.stop()
            raise

    async def start(self):
        """Start market monitor"""
        try:
            # Initialize services
            await self.initialize()
            
            # Start processors
            logger.info("[MarketMonitor] Starting processors...")
            processor_tasks = []
            
            # Start RuleMatcher
            logger.info("[MarketMonitor] Starting RuleMatcher...")
            rule_matcher_task = asyncio.create_task(self.rule_matcher.start())
            processor_tasks.append(rule_matcher_task)
            
            # Start NotifyDispatcher
            logger.info("[MarketMonitor] Starting NotifyDispatcher...")
            notify_dispatcher_task = asyncio.create_task(self.notify_dispatcher.start())
            processor_tasks.append(notify_dispatcher_task)
            
            # Start RuleProcessor
            logger.info("[MarketMonitor] Starting RuleProcessor...")
            rule_processor_task = asyncio.create_task(self.rule_processor.start())
            processor_tasks.append(rule_processor_task)
            
            self._shutdown_tasks.extend(processor_tasks)
            
            # Wait a bit to ensure processors are running
            await asyncio.sleep(2)
            
            # Check processor status
            for i, task in enumerate(processor_tasks):
                if task.done():
                    try:
                        await task
                    except Exception as e:
                        logger.error(f"[MarketMonitor] Processor {i} failed to start: {e}")
                        raise
                else:
                    logger.info(f"[MarketMonitor] Processor {i} is running")
            
            # Check worker pool status
            if self.worker_pool:
                workers = await self.worker_pool.get_workers()
                logger.info(f"[MarketMonitor] Active workers: {[w.__class__.__name__ for w in workers]}")
                for worker in workers:
                    logger.info(f"[MarketMonitor] Worker {worker.__class__.__name__} status: running={worker.is_running}, targets={len(worker.watching_targets)}")
            
            # Register signal handlers
            for sig in (signal.SIGTERM, signal.SIGINT):
                signal.signal(sig, self._handle_signal)
                
            logger.info("[MarketMonitor] Market monitor started successfully")
            
            # Start monitoring loop
            while not self.shutdown_event.is_set():
                try:
                    # Check if any processor has failed
                    for i, task in enumerate(processor_tasks):
                        if task.done():
                            try:
                                await task
                            except Exception as e:
                                logger.error(f"[MarketMonitor] Processor {i} failed: {e}")
                                # Attempt to restart the processor
                                logger.info(f"[MarketMonitor] Attempting to restart processor {i}...")
                                if i == 0:
                                    self.rule_matcher = RuleMatcher()
                                    processor_tasks[i] = asyncio.create_task(self.rule_matcher.start())
                                elif i == 1:
                                    self.notify_dispatcher = NotifyDispatcher()
                                    processor_tasks[i] = asyncio.create_task(self.notify_dispatcher.start())
                                elif i == 2:
                                    self.rule_processor = RuleProcessor()
                                    processor_tasks[i] = asyncio.create_task(self.rule_processor.start())
                    
                    # Check worker pool status
                    if self.worker_pool:
                        workers = await self.worker_pool.get_workers()
                        for worker in workers:
                            if not worker.is_running:
                                logger.warning(f"[MarketMonitor] Worker {worker.__class__.__name__} is not running")
                    
                    await asyncio.sleep(5)  # Check every 5 seconds
                    
                except Exception as e:
                    logger.error(f"[MarketMonitor] Error in monitoring loop: {e}")
                    await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"[MarketMonitor] Error starting market monitor: {e}")
            await self.stop()
            sys.exit(1)
            
    async def stop(self):
        """Stop market monitor"""
        try:
            logger.info("[MarketMonitor] Stopping market monitor...")
            
            # Cancel all running tasks
            for task in self._shutdown_tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            
            # Stop processors
            if self.rule_matcher:
                await self.rule_matcher.close()
            if self.notify_dispatcher:
                await self.notify_dispatcher.close()
            if self.rule_processor:
                await self.rule_processor.close()
                
            # Stop worker pool
            if self.worker_pool:
                # Cleanup Web3 connections
                workers = await self.worker_pool.get_workers()
                for worker in workers:
                    if hasattr(worker, 'cleanup'):
                        await worker.cleanup()
                await self.worker_pool.stop()
                
            # Close Redis connection
            if self.redis_client:
                await RedisClient.close()
                
            # Close MongoDB connection
            await MongoClient.close()
            
            logger.info("[MarketMonitor] Market monitor stopped")
            
        except Exception as e:
            logger.error(f"[MarketMonitor] Error stopping market monitor: {e}")
            
    def _handle_signal(self, signum, frame):
        """Handle termination signals"""
        logger.info(f"[MarketMonitor] Received signal {signum}")
        self.shutdown_event.set()
        asyncio.create_task(self.stop())

async def main():
    """Main entry point"""
    logger.info("[MarketMonitor] Starting market monitor application...")
    monitor = MarketMonitor()
    try:
        logger.info("[MarketMonitor] Creating monitor instance...")
        await monitor.start()
        logger.info("[MarketMonitor] Monitor started successfully")
    except KeyboardInterrupt:
        logger.info("[MarketMonitor] Received keyboard interrupt, shutting down...")
        await monitor.stop()
    except Exception as e:
        logger.error(f"[MarketMonitor] Unexpected error: {e}", exc_info=True)
        await monitor.stop()
        sys.exit(1)
    
if __name__ == "__main__":
    try:
        logger.info("[MarketMonitor] Starting main process...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[MarketMonitor] Shutdown complete")
    except Exception as e:
        logger.error(f"[MarketMonitor] Fatal error: {e}", exc_info=True)
        sys.exit(1)
