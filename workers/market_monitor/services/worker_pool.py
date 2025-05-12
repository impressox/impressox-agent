# services/worker_pool.py

import asyncio
import json
import logging
from typing import Dict, List, Optional, Type
from datetime import datetime

from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.services.token_watcher import TokenWatcher
from workers.market_monitor.services.wallet_watcher import WalletWatcher
from workers.market_monitor.services.airdrop_watcher import AirdropWatcher
from workers.market_monitor.services.notification_service import NotificationService
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.config import get_config

logger = logging.getLogger(__name__)

class WorkerPool:
    def __init__(self):
        self.workers: Dict[str, BaseWatcher] = {}
        self.redis_client = None
        self.notification_service = None
        self.config = get_config()
        self.worker_status = {}
        self.last_health_check = None
        
    async def start(self):
        """Start worker pool"""
        try:
            # Initialize Redis client
            self.redis_client = await RedisClient.get_instance()
            logger.info("[WorkerPool] Redis client initialized")
            
            # Initialize notification service
            self.notification_service = NotificationService()
            await self.notification_service.start()
            logger.info("[WorkerPool] Notification service started")
            
            # Initialize default workers
            logger.info("[WorkerPool] Initializing default workers...")
            await self.add_worker("token", TokenWatcher)
            await self.add_worker("wallet", WalletWatcher)
            await self.add_worker("airdrop", AirdropWatcher)
            
            # Verify workers are running
            for worker_id, worker in self.workers.items():
                if not worker.is_running:
                    logger.error(f"[WorkerPool] Worker {worker_id} failed to start")
                else:
                    logger.info(f"[WorkerPool] Worker {worker_id} is running with {len(worker.watching_targets)} targets")
            
            # Start health check loop
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("[WorkerPool] Health check loop started")
            
            logger.info("[WorkerPool] Worker pool started with default workers")
            
        except Exception as e:
            logger.error(f"[WorkerPool] Error starting worker pool: {e}")
            await self.stop()
            raise
            
    async def stop(self):
        """Stop worker pool"""
        try:
            logger.info("[WorkerPool] Stopping worker pool...")
            
            # Stop health check loop
            if hasattr(self, '_health_check_task'):
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass
            
            # Stop all workers
            for worker_id, worker in self.workers.items():
                try:
                    logger.info(f"[WorkerPool] Stopping worker {worker_id}...")
                    await worker.stop()
                except Exception as e:
                    logger.error(f"[WorkerPool] Error stopping worker {worker_id}: {e}")
            self.workers.clear()
            
            # Stop notification service
            if self.notification_service:
                await self.notification_service.stop()
                
            # Close Redis connection
            if self.redis_client:
                await RedisClient.close()
                
            logger.info("[WorkerPool] Worker pool stopped")
            
        except Exception as e:
            logger.error(f"[WorkerPool] Error stopping worker pool: {e}")
            
    async def add_worker(self, worker_id: str, worker_class: Type[BaseWatcher], **kwargs):
        """Add a new worker to the pool"""
        try:
            if worker_id in self.workers:
                logger.warning(f"[WorkerPool] Worker {worker_id} already exists")
                return
                
            # Create worker
            worker = worker_class(**kwargs)
            
            # Start worker in a separate task
            start_task = asyncio.create_task(worker.start())
            self.workers[worker_id] = worker
            
            # Wait a bit to ensure worker is initialized
            await asyncio.sleep(1)
            
            if not worker.is_running:
                logger.error(f"[WorkerPool] Worker {worker_id} failed to start")
                await self.remove_worker(worker_id)
                return
                
            logger.info(f"[WorkerPool] Added worker {worker_id}")
            
        except Exception as e:
            logger.error(f"[WorkerPool] Error adding worker {worker_id}: {e}")
            raise
            
    async def remove_worker(self, worker_id: str):
        """Remove a worker from the pool"""
        try:
            if worker_id not in self.workers:
                logger.warning(f"Worker {worker_id} not found")
                return
                
            # Stop and remove worker
            await self.workers[worker_id].stop()
            del self.workers[worker_id]
            
            logger.info(f"Removed worker {worker_id}")
            
        except Exception as e:
            logger.error(f"Error removing worker {worker_id}: {e}")
            raise
            
    async def get_worker(self, worker_id: str) -> Optional[BaseWatcher]:
        """Get a worker by ID"""
        return self.workers.get(worker_id)
        
    async def get_workers(self) -> List[BaseWatcher]:
        """Get all workers"""
        return list(self.workers.values())

    async def _health_check_loop(self):
        """Periodic health check of workers"""
        while True:
            try:
                current_time = datetime.utcnow()
                
                # Update worker status and check health
                for worker_type, watcher in self.workers.items():
                    try:
                        # Check if worker is running
                        if not watcher.is_running:
                            logger.warning(f"[WorkerPool] Worker {worker_type} is not running, attempting restart...")
                            await self.remove_worker(worker_type)
                            await self.add_worker(worker_type, type(watcher))
                            continue
                            
                        # Update status
                        self.worker_status[worker_type] = {
                            "active": watcher.is_running,
                            "targets": len(watcher.watching_targets),
                            "last_check": current_time.isoformat()
                        }
                    except Exception as e:
                        logger.error(f"[WorkerPool] Error checking worker {worker_type}: {e}")
                
                # Publish status to Redis
                try:
                    await self.redis_client.set(
                        "worker:status",
                        json.dumps(self.worker_status),
                        60  # Expire after 1 minute
                    )
                except Exception as e:
                    logger.error(f"[WorkerPool] Error publishing worker status: {e}")
                
                self.last_health_check = current_time
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"[WorkerPool] Error in health check loop: {e}")
                await asyncio.sleep(5)  # Wait before retrying

    async def register_rule(self, rule: Dict):
        """Register a new rule with appropriate watcher"""
        try:
            watch_type = rule.get("watch_type", "token")
            if watch_type not in self.workers:
                logger.error(f"Unknown watch type: {watch_type}")
                return False
            
            watcher = self.workers[watch_type]
            return await watcher.register_rule(rule)
            
        except Exception as e:
            logger.error(f"Error registering rule: {e}")
            return False

    async def unregister_rule(self, rule_id: str, watch_type: str = "token"):
        """Unregister a rule from watcher"""
        try:
            if watch_type not in self.workers:
                logger.error(f"Unknown watch type: {watch_type}")
                return False
            
            watcher = self.workers[watch_type]
            return await watcher.unregister_rule(rule_id)
            
        except Exception as e:
            logger.error(f"Error unregistering rule: {e}")
            return False

    async def get_worker_status(self) -> Dict:
        """Get current status of all workers"""
        return {
            "workers": self.worker_status,
            "last_health_check": self.last_health_check.isoformat()
        }

    async def scale_workers(self, watch_type: str, target_count: int):
        """Scale number of workers for a specific type"""
        try:
            if watch_type not in self.workers:
                logger.error(f"Unknown watch type: {watch_type}")
                return False
            
            current_count = len(self.workers[watch_type].workers)
            if target_count == current_count:
                return True
            
            watcher = self.workers[watch_type]
            if target_count > current_count:
                # Scale up
                for _ in range(target_count - current_count):
                    await watcher.add_worker()
            else:
                # Scale down
                for _ in range(current_count - target_count):
                    await watcher.remove_worker()
            
            logger.info(f"Scaled {watch_type} workers from {current_count} to {target_count}")
            return True
            
        except Exception as e:
            logger.error(f"Error scaling workers: {e}")
            return False 