# services/base.py

import asyncio
import json
import logging
from typing import Dict, List, Optional, Set, Any

from workers.market_monitor.shared.models import Rule, RuleMatch
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.mongo import MongoClient, MongoJSONEncoder

logger = logging.getLogger(__name__)

class BaseWatcher:
    def __init__(self):
        self.redis: Optional[RedisClient] = None
        self.mongo: Optional[MongoClient] = None
        self.watch_interval: int = 60  # Default interval in seconds
        self.watching_targets: Set[str] = set()  # Targets being watched (addresses, ids, ...)
        self.is_running: bool = False
        self._watch_task: Optional[asyncio.Task] = None
        self._subscription_task: Optional[asyncio.Task] = None
        self.watch_type: Optional[str] = None  # Must be set by child classes

    async def start(self):
        """Start the watcher and subscription loop."""
        try:
            if not self.watch_type:
                raise ValueError("watch_type must be set by child class")

            self.redis = await RedisClient.get_instance()
            self.mongo = await MongoClient.get_instance()
            logger.info(f"[{self.__class__.__name__}] Connected to Redis & MongoDB")

            # Main watch loop
            self._watch_task = asyncio.create_task(self.watch_cycle())
            self.is_running = True
            logger.info(f"[{self.__class__.__name__}] Started watch cycle")

            # Rule subscription loop
            self._subscription_task = asyncio.create_task(self._maintain_subscriptions())
            logger.info(f"[{self.__class__.__name__}] Started subscription maintenance")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error starting watcher: {e}", exc_info=True)
            raise

    async def _maintain_subscriptions(self):
        """Keep Redis subscriptions for rule register/deactivate."""
        while self.is_running:
            try:
                await self.redis.subscribe(f"{self.watch_type}_watch:register_rule", self.handle_rule_registration)
                logger.info(f"[{self.__class__.__name__}] Subscribed to register_rule")

                await self.redis.subscribe(f"{self.watch_type}_watch:deactivate_rule", self.handle_rule_deactivation)
                logger.info(f"[{self.__class__.__name__}] Subscribed to deactivate_rule")

                while self.is_running:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] Subscription maintenance error: {e}")
                await asyncio.sleep(5)
                try:
                    if not self.redis or not await self.redis.ping():
                        self.redis = await RedisClient.get_instance()
                        logger.info(f"[{self.__class__.__name__}] Reconnected Redis")
                except Exception as conn_err:
                    logger.error(f"[{self.__class__.__name__}] Redis reconnect failed: {conn_err}")

    async def stop(self):
        """Stop watcher and all background tasks. Always await this method on shutdown."""
        try:
            logger.info(f"[{self.__class__.__name__}] Stopping...")
            self.is_running = False

            if self._watch_task and not self._watch_task.done():
                self._watch_task.cancel()
                try:
                    await self._watch_task
                except asyncio.CancelledError:
                    pass

            if self._subscription_task and not self._subscription_task.done():
                self._subscription_task.cancel()
                try:
                    await self._subscription_task
                except asyncio.CancelledError:
                    pass

            await self.close()
            logger.info(f"[{self.__class__.__name__}] Stopped")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error stopping: {e}", exc_info=True)
            raise

    async def close(self):
        """Cleanup resources: Close Redis & Mongo connections."""
        try:
            if self.redis:
                await self.redis.close()
                self.redis = None
            if self.mongo:
                await self.mongo.close()
                self.mongo = None
            logger.info(f"[{self.__class__.__name__}] Closed connections")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error closing connections: {e}", exc_info=True)

    async def watch_cycle(self):
        """Main interval loop for checking watched targets."""
        while self.is_running:
            try:
                if self.watching_targets:
                    await self.watch_targets()
                await asyncio.sleep(self.watch_interval)
            except asyncio.CancelledError:
                logger.info(f"[{self.__class__.__name__}] Watch cycle cancelled")
                break
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] Error in watch cycle: {e}")
                await asyncio.sleep(5)

    async def watch_targets(self):
        """Child class must implement: logic to check all watching_targets."""
        raise NotImplementedError

    async def handle_rule_registration(self, channel: str, event_data: Dict[str, Any]):
        """Process a new rule registration: update watching_targets & save rule."""
        try:
            logger.info(f"[{self.__class__.__name__}] Register rule: {event_data}")
            if event_data["watch_type"] == self.watch_type:
                new_targets = set(event_data["target"])
                self.watching_targets.update(new_targets)
                logger.info(f"[{self.__class__.__name__}] Watching targets: {new_targets}")

                await self.initialize_cache(list(new_targets))

                for target in new_targets:
                    rule_key = await self.get_rule_key(event_data)
                    await self.redis.hset(rule_key, event_data["rule_id"], json.dumps(event_data, cls=MongoJSONEncoder))
                    logger.info(f"[{self.__class__.__name__}] Saved rule {event_data['rule_id']} for {target}")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error handling rule registration: {e}", exc_info=True)

    async def initialize_cache(self, targets: List[str]):
        """(Optional) Override for child class: cache init when tracking new targets."""
        pass

    async def handle_rule_deactivation(self, channel: str, event_data: Dict[str, Any]):
        """Handle deactivation: remove rule from Redis & possibly stop watching target."""
        try:
            if event_data["watch_type"] == self.watch_type:
                to_remove: Set[str] = set()
                for target in event_data["target"]:
                    rule_key = await self.get_rule_key(event_data)
                    rules = await self.redis.hgetall(rule_key)
                    if event_data["rule_id"] in rules:
                        await self.redis.hdel(rule_key, event_data["rule_id"])
                        logger.info(f"[{self.__class__.__name__}] Removed rule {event_data['rule_id']} from {target}")

                    remaining = await self.redis.hgetall(rule_key)
                    if not remaining:
                        to_remove.add(target)
                        logger.info(f"[{self.__class__.__name__}] No active rules left for {target}")
                if to_remove:
                    self.watching_targets -= to_remove
                    logger.info(f"[{self.__class__.__name__}] Stopped watching: {to_remove}")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error handling rule deactivation: {e}", exc_info=True)

    async def get_target_rules(self, target: str) -> List[Rule]:
        """Load all rules for a given target from Redis."""
        try:
            rule_key = await self.get_rule_key({"target": target})
            rule_data = await self.redis.hgetall(rule_key)
            rules = []
            for rule_json in rule_data.values():
                rules.append(Rule.from_dict(json.loads(rule_json)))
            return rules
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error loading rules for {target}: {e}")
            return []

    async def check_rules(self, rules: List[Rule], target_data: Dict):
        """Evaluate all rules and publish matches."""
        for rule in rules:
            try:
                matches = self.evaluate_conditions(rule, target_data)
                if matches:
                    match_data = {
                        "target_data": target_data,
                        "matches": matches,
                    }
                    match = RuleMatch(rule=rule, match_data=match_data)
                    await self.redis.publish(
                        f"{self.watch_type}_watch:rule_matched",
                        json.dumps(match.to_dict(), cls=MongoJSONEncoder),
                    )
                    logger.info(f"[{self.__class__.__name__}] Rule {rule.rule_id} matched: {json.dumps(matches, cls=MongoJSONEncoder)}")
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] Error checking rule {rule.rule_id}: {e}", exc_info=True)

    def evaluate_conditions(self, rule: Rule, target_data: Dict) -> List[Dict]:
        """Child class must override: returns a list of match dicts if rule is matched."""
        raise NotImplementedError

    async def get_rule_key(self, event_data: Dict) -> str:
        """Build the Redis rule key for a target."""
        return f"watch:active:{self.watch_type}:{event_data['target']}"
