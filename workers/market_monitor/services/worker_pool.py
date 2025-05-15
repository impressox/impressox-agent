import asyncio
import json
import logging
from typing import Dict, List, Optional, Type
from datetime import datetime

from workers.market_monitor.services.base import BaseWatcher
from workers.market_monitor.services.token_watcher import TokenWatcher
from workers.market_monitor.services.wallet_watcher import WalletWatcher
from workers.market_monitor.services.airdrop_watcher import AirdropWatcher
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.config import get_config

logger = logging.getLogger(__name__)

class WorkerPool:
    def __init__(self):
        self.workers: Dict[str, BaseWatcher] = {}
        self.redis_client = None
        self.config = get_config()
        self.worker_status = {}
        self.last_health_check = None
        self._health_check_task = None

    async def start(self):
        """Start worker pool and health check."""
        try:
            self.redis_client = await RedisClient.get_instance()
            logger.info("[WorkerPool] Redis client initialized")

            # Khởi tạo workers song song
            workers_to_start = [
                ("token", TokenWatcher),
                ("wallet", WalletWatcher),
                ("airdrop", AirdropWatcher),
            ]
            await asyncio.gather(*[self.add_worker(wid, wclass) for wid, wclass in workers_to_start])

            # Log status workers
            for worker_id, worker in self.workers.items():
                logger.info(
                    f"[WorkerPool] Worker {worker_id} {'is running' if worker.is_running else 'failed'} "
                    f"with {len(getattr(worker, 'watching_targets', []))} targets"
                )

            # Health check loop
            self._health_check_task = asyncio.create_task(self._health_check_loop())
            logger.info("[WorkerPool] Health check loop started")

        except Exception as e:
            logger.error(f"[WorkerPool] Error starting worker pool: {e}", exc_info=True)
            await self.stop()
            raise

    async def stop(self):
        """Stop all workers and clean up."""
        logger.info("[WorkerPool] Stopping worker pool...")
        try:
            if self._health_check_task:
                self._health_check_task.cancel()
                try:
                    await self._health_check_task
                except asyncio.CancelledError:
                    pass

            await asyncio.gather(*(worker.stop() for worker in self.workers.values()), return_exceptions=True)
            self.workers.clear()

            if self.redis_client:
                await RedisClient.close()
            logger.info("[WorkerPool] Worker pool stopped")

        except Exception as e:
            logger.error(f"[WorkerPool] Error stopping worker pool: {e}", exc_info=True)

    async def add_worker(self, worker_id: str, worker_class: Type[BaseWatcher], **kwargs):
        """Add a new worker to the pool."""
        if worker_id in self.workers:
            logger.warning(f"[WorkerPool] Worker {worker_id} already exists")
            return
        try:
            worker = worker_class(**kwargs)
            await worker.start()
            if not worker.is_running:
                logger.error(f"[WorkerPool] Worker {worker_id} failed to start")
                return
            self.workers[worker_id] = worker
            logger.info(f"[WorkerPool] Added worker {worker_id}")
        except Exception as e:
            logger.error(f"[WorkerPool] Error adding worker {worker_id}: {e}", exc_info=True)
            raise

    async def remove_worker(self, worker_id: str):
        """Remove a worker from the pool."""
        worker = self.workers.pop(worker_id, None)
        if not worker:
            logger.warning(f"[WorkerPool] Worker {worker_id} not found")
            return
        try:
            await worker.stop()
            logger.info(f"[WorkerPool] Removed worker {worker_id}")
        except Exception as e:
            logger.error(f"[WorkerPool] Error removing worker {worker_id}: {e}", exc_info=True)

    async def get_worker(self, worker_id: str) -> Optional[BaseWatcher]:
        """Get a worker by ID."""
        return self.workers.get(worker_id)

    async def get_workers(self) -> List[BaseWatcher]:
        """Get all workers."""
        return list(self.workers.values())

    async def _health_check_loop(self):
        """Periodic health check of workers."""
        while True:
            try:
                now = datetime.utcnow()
                for wid, watcher in self.workers.items():
                    try:
                        if not watcher.is_running:
                            logger.warning(f"[WorkerPool] Worker {wid} is not running, restarting...")
                            await self.remove_worker(wid)
                            await self.add_worker(wid, type(watcher))
                        self.worker_status[wid] = {
                            "active": watcher.is_running,
                            "targets": len(getattr(watcher, 'watching_targets', [])),
                            "last_check": now.isoformat(),
                        }
                    except Exception as e:
                        logger.error(f"[WorkerPool] Error checking worker {wid}: {e}", exc_info=True)

                # Publish status to Redis
                try:
                    await self.redis_client.set("worker:status", json.dumps(self.worker_status), 60)
                except Exception as e:
                    logger.error(f"[WorkerPool] Error publishing worker status: {e}", exc_info=True)

                self.last_health_check = now
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"[WorkerPool] Error in health check loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def register_rule(self, rule: Dict):
        """Register a new rule with appropriate watcher."""
        try:
            watch_type = rule.get("watch_type", "token")
            watcher = self.workers.get(watch_type)
            if not watcher:
                logger.error(f"[WorkerPool] Unknown watch type: {watch_type}")
                return False
            return await watcher.register_rule(rule)
        except Exception as e:
            logger.error(f"[WorkerPool] Error registering rule: {e}", exc_info=True)
            return False

    async def unregister_rule(self, rule_id: str, watch_type: str = "token"):
        """Unregister a rule from watcher."""
        try:
            watcher = self.workers.get(watch_type)
            if not watcher:
                logger.error(f"[WorkerPool] Unknown watch type: {watch_type}")
                return False
            return await watcher.unregister_rule(rule_id)
        except Exception as e:
            logger.error(f"[WorkerPool] Error unregistering rule: {e}", exc_info=True)
            return False

    async def get_worker_status(self) -> Dict:
        """Get current status of all workers."""
        return {
            "workers": self.worker_status,
            "last_health_check": self.last_health_check.isoformat() if self.last_health_check else None,
        }

    async def scale_workers(self, watch_type: str, target_count: int):
        """Scale number of workers for a specific type (if supported)."""
        try:
            watcher = self.workers.get(watch_type)
            if not watcher or not hasattr(watcher, "workers"):
                logger.error(f"[WorkerPool] Unknown or non-scalable watch type: {watch_type}")
                return False

            current_count = len(watcher.workers)
            if target_count == current_count:
                return True

            if target_count > current_count:
                await asyncio.gather(*(watcher.add_worker() for _ in range(target_count - current_count)))
            else:
                await asyncio.gather(*(watcher.remove_worker() for _ in range(current_count - target_count)))
            logger.info(f"[WorkerPool] Scaled {watch_type} workers from {current_count} to {target_count}")
            return True
        except Exception as e:
            logger.error(f"[WorkerPool] Error scaling workers: {e}", exc_info=True)
            return False
