# services/base.py

import asyncio
import json
import logging
from typing import Dict, List, Optional

from workers.market_monitor.shared.models import Rule, RuleMatch
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.mongo import MongoClient, MongoJSONEncoder

logger = logging.getLogger(__name__)

class BaseWatcher:
    def __init__(self):
        self.redis = None
        self.mongo = None
        self.watch_interval = 60  # Default 60 seconds
        self.watching_targets = set()  # Set of targets being watched
        self.is_running = False
        self._watch_task = None

    async def start(self):
        """Start the watcher"""
        try:
            self.redis = await RedisClient.get_instance()
            self.mongo = await MongoClient.get_instance()
            logger.info(f"[{self.__class__.__name__}] Successfully connected to Redis and MongoDB")

            # Start watching cycle in a separate task
            self._watch_task = asyncio.create_task(self.watch_cycle())
            self.is_running = True
            logger.info(f"[{self.__class__.__name__}] Started watching cycle")

            # Start subscription task
            self._subscription_task = asyncio.create_task(self._maintain_subscriptions())
            logger.info(f"[{self.__class__.__name__}] Started subscription maintenance task")

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error starting watcher: {e}", exc_info=True)
            raise

    async def _maintain_subscriptions(self):
        """Maintain Redis subscriptions with retry logic"""
        while self.is_running:
            try:
                # Subscribe to rule registration events
                await self.redis.subscribe("market_watch:register_rule", self.handle_rule_registration)
                logger.info(f"[{self.__class__.__name__}] Subscribed to rule registration events")

                # Subscribe to rule deactivation events
                await self.redis.subscribe("market_watch:deactivate_rule", self.handle_rule_deactivation)
                logger.info(f"[{self.__class__.__name__}] Subscribed to rule deactivation events")

                # Keep the subscription alive
                while self.is_running:
                    try:
                        await asyncio.sleep(1)
                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"[{self.__class__.__name__}] Error in subscription loop: {e}")
                        break

            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] Error in subscription maintenance: {e}")
                # Wait before retrying
                await asyncio.sleep(5)
                # Try to reconnect Redis if needed
                try:
                    if not self.redis or not self.redis.ping():
                        self.redis = await RedisClient.get_instance()
                        logger.info(f"[{self.__class__.__name__}] Reconnected to Redis")
                except Exception as conn_err:
                    logger.error(f"[{self.__class__.__name__}] Failed to reconnect to Redis: {conn_err}")

    async def stop(self):
        """Stop the watcher"""
        try:
            logger.info(f"[{self.__class__.__name__}] Stopping...")
            self.is_running = False
            
            # Cancel watch task if running
            if self._watch_task and not self._watch_task.done():
                self._watch_task.cancel()
                try:
                    await self._watch_task
                except asyncio.CancelledError:
                    pass

            # Cancel subscription task if running
            if hasattr(self, '_subscription_task') and self._subscription_task and not self._subscription_task.done():
                self._subscription_task.cancel()
                try:
                    await self._subscription_task
                except asyncio.CancelledError:
                    pass
            
            # Close connections
            if self.redis:
                await self.redis.close()
                self.redis = None
            if self.mongo:
                await self.mongo.close()
                self.mongo = None
                
            logger.info(f"[{self.__class__.__name__}] Successfully stopped")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error stopping: {e}", exc_info=True)
            raise

    async def watch_cycle(self):
        """Main cycle for watching targets"""
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
        """Watch targets and check conditions"""
        raise NotImplementedError

    async def handle_rule_registration(self, channel: str, event_data: Dict):
        """Handle rule registration events"""
        try:
            if event_data["watch_type"] == self.watch_type:
                # Add targets to watching set
                self.watching_targets.update(event_data["target"])
                logger.info(f"[{self.__class__.__name__}] Now watching targets: {event_data['target']}")
                
                # Save rule to Redis
                for target in event_data["target"]:
                    rule_key = f"watch:active:{self.watch_type}:{target}"
                    await self.redis.hset(rule_key, event_data["rule_id"], json.dumps(event_data, cls=MongoJSONEncoder))
                    logger.info(f"[{self.__class__.__name__}] Saved rule {event_data['rule_id']} for target {target}")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error handling rule registration: {e}", exc_info=True)

    async def handle_rule_deactivation(self, channel: str, event_data: Dict):
        """Handle rule deactivation events"""
        try:
            if event_data["watch_type"] == self.watch_type:
                # Track targets that need to be removed
                targets_to_remove = set()
                
                # Check each target in the deactivated rule
                for target in event_data["target"]:
                    rule_key = f"watch:active:{self.watch_type}:{target}"
                    rules = await self.redis.hgetall(rule_key)
                    
                    # Remove the deactivated rule from Redis
                    if event_data["rule_id"] in rules:
                        await self.redis.hdel(rule_key, event_data["rule_id"])
                        logger.info(f"[{self.__class__.__name__}] Removed rule {event_data['rule_id']} for target {target}")
                    
                    # Check if any rules remain for this target
                    remaining_rules = await self.redis.hgetall(rule_key)
                    if not remaining_rules:
                        targets_to_remove.add(target)
                        logger.info(f"[{self.__class__.__name__}] No active rules left for target {target}")
                
                # Remove targets from watching set
                if targets_to_remove:
                    self.watching_targets -= targets_to_remove
                    logger.info(f"[{self.__class__.__name__}] Removed targets from watching set: {targets_to_remove}")
                
                logger.info(f"[{self.__class__.__name__}] Processed deactivation for rule {event_data['rule_id']}")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error handling rule deactivation: {e}", exc_info=True)

    async def get_target_rules(self, target: str) -> List[Rule]:
        """Get all active rules for a target"""
        try:
            rules = []
            rule_key = f"watch:active:{self.watch_type}:{target}"
            rule_data = await self.redis.hgetall(rule_key)
            for rule_json in rule_data.values():
                rule = Rule.from_dict(json.loads(rule_json))
                rules.append(rule)
            return rules
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error getting rules for target {target}: {e}")
            return []

    async def check_rules(self, rules: List[Rule], target_data: Dict):
        """Check conditions for each rule against target data"""
        for rule in rules:
            try:
                matches = await self.evaluate_conditions(rule, target_data)
                if matches:
                    # Create match data with consistent format
                    match_data = {
                        "target_data": target_data,
                        "matches": matches
                    }
                    
                    # Create and publish match event
                    match = RuleMatch(
                        rule=rule,
                        match_data=match_data
                    )
                    # Publish match event
                    await self.redis.publish(
                        "market_watch:rule_matched",
                        json.dumps(match.to_dict(), cls=MongoJSONEncoder)
                    )
                    logger.info(f"[{self.__class__.__name__}] Rule {rule.rule_id} matched: {json.dumps(matches, cls=MongoJSONEncoder)}")
            except Exception as e:
                logger.error(f"[{self.__class__.__name__}] Error checking rule {rule.rule_id}: {e}", exc_info=True)

    async def evaluate_conditions(self, rule: Rule, target_data: Dict) -> List[Dict]:
        """Evaluate rule conditions against target data"""
        raise NotImplementedError

    async def close(self):
        """Cleanup resources"""
        try:
            if self.redis:
                await self.redis.close()
                self.redis = None
            if self.mongo:
                await self.mongo.close()
                self.mongo = None
            logger.info(f"[{self.__class__.__name__}] Successfully closed connections")
        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Error closing connections: {e}", exc_info=True) 