import asyncio
import json
import logging
from typing import Optional, Dict, Any, List

from workers.market_monitor.shared.models import Rule
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.mongo import MongoClient, RuleStorage
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RuleProcessor:
    def __init__(self):
        self.redis = None
        self.mongo = None
        self.rule_storage = None
        self.watch_types = ["market", "wallet", "airdrop"]  # List of supported watch types

    async def load_active_rules(self) -> List[Dict]:
        """Load all active rules from MongoDB"""
        try:
            logger.info("[RuleProcessor] Loading active rules from MongoDB...")
            self.rule_storage = await RuleStorage.get_instance()
            active_rules = await self.rule_storage.get_active_rules()
            logger.info(f"[RuleProcessor] Found {len(active_rules)} active rules")
            return active_rules
        except Exception as e:
            logger.error(f"[RuleProcessor] Error loading active rules: {e}")
            return []

    async def start(self):
        """Start the rule processor"""
        try:
            logger.info("[RuleProcessor] Initializing...")
            self.redis = await RedisClient.get_instance()
            logger.info("[RuleProcessor] Redis connection established")
            
            self.mongo = await MongoClient.get_instance()
            logger.info("[RuleProcessor] MongoDB connection established")

            # Load and process active rules
            active_rules = await self.load_active_rules()
            if not active_rules:
                logger.info("[RuleProcessor] No active rules found")
            else:
                logger.info(f"[RuleProcessor] Found {len(active_rules)} active rules")
                for rule_data in active_rules:
                    # Publish register_rule event for each rule
                    watch_type = rule_data.get("watch_type", "token")  # Default to token for backward compatibility
                    await self.redis.publish(
                        f"{watch_type}_watch:register_rule",
                        json.dumps(rule_data, cls=MongoJSONEncoder)
                    )
                    logger.info(f"[RuleProcessor] Published register_rule event for rule {rule_data.get('rule_id')}")
                logger.info("[RuleProcessor] Finished processing active rules")

            # Subscribe to register_rule channels for all watch types
            for watch_type in self.watch_types:
                channel = f"{watch_type}_watch:register_rule"
                logger.info(f"[RuleProcessor] Subscribing to {channel}")
                await self.redis.subscribe(channel, self.process_rule)
                logger.info(f"[RuleProcessor] Successfully subscribed to {channel}")

            logger.info("[RuleProcessor] Processor started and running")
            # Keep the processor running
            while True:
                try:
                    await asyncio.sleep(0.1)  # Prevent tight loop
                except Exception as e:
                    logger.error(f"[RuleProcessor] Error in main loop: {e}")
                    await asyncio.sleep(1)  # Error backoff
        except Exception as e:
            logger.error(f"[RuleProcessor] Failed to start: {e}")
            raise

    async def process_rule(self, channel: str, rule_data: Dict):
        """Process rule from pub/sub channel"""
        try:
            # Validate rule data format
            if not isinstance(rule_data, dict):
                logger.error(f"Invalid rule data format: {type(rule_data)}")
                return

            # Check required fields
            required_fields = ["rule_id", "user_id", "watch_type", "target", "notify_channel", "notify_id"]
            missing_fields = [field for field in required_fields if field not in rule_data]
            if missing_fields:
                logger.error(f"Missing required fields in rule: {missing_fields}")
                return

            # Convert to Rule object
            try:
                rule = Rule.from_dict(rule_data)
            except Exception as e:
                logger.error(f"Error converting rule data: {e}")
                return
            
            # Validate rule
            if not self.validate_rule(rule):
                logger.warning(f"Invalid rule: {rule_data}")
                # Deactivate invalid rule in MongoDB
                await self.mongo.deactivate_rule(rule.rule_id)
                return

            try:
                # Store in Redis for each target
                for target in rule.target:
                    # Use watch_type from rule
                    redis_key = f"watch:active:{rule.watch_type}:{target}"
                    logger.info(f"[RuleProcessor] Storing rule in Redis key: {redis_key}")
                    
                    # Store full rule data
                    await self.redis.hset(
                        redis_key,
                        str(rule.rule_id),
                        json.dumps(rule_data, cls=MongoJSONEncoder)
                    )
                    logger.info(f"[RuleProcessor] Rule {rule.rule_id} stored for target {target}")

                # Update rule status in MongoDB
                await self.mongo.update_rule_status(rule.rule_id, "active")
                logger.info(f"[RuleProcessor] Rule {rule.rule_id} activated in MongoDB")

                # Publish rule activated event
                await self.redis.publish(
                    f"{rule.watch_type}_watch:rule_activated",
                    json.dumps({
                        "rule_id": str(rule.rule_id),
                        "watch_type": rule.watch_type,
                        "target": rule.target
                    })
                )
                logger.info(f"[RuleProcessor] Published rule activation event for {rule.rule_id}")
            except Exception as e:
                logger.error(f"[RuleProcessor] Failed to register rule {rule.rule_id}: {e}")
                # Update error status in MongoDB
                await self.mongo.update_rule_status(rule.rule_id, "failed", str(e))

        except Exception as e:
            logger.error(f"[RuleProcessor] Error processing rule {rule_data}: {e}")
            # Try to update error status if rule_id exists
            if isinstance(rule_data, dict) and "rule_id" in rule_data:
                await self.mongo.update_rule_status(rule_data["rule_id"], "error", str(e))

    def validate_rule(self, rule: Rule) -> bool:
        """Validate rule before registration"""
        try:
            # Check required fields
            if not rule.rule_id or not rule.user_id or not rule.target:
                return False

            # Validate watch type
            if not rule.watch_type or rule.watch_type not in self.watch_types:
                return False

            # Validate condition if present
            if rule.condition and not self.validate_condition(rule.condition):
                return False

            # Validate notification channel
            if not rule.notify_channel or not rule.notify_id:
                return False

            return True

        except Exception as e:
            logger.error(f"Error validating rule: {e}")
            return False

    def validate_condition(self, condition: dict) -> bool:
        """Validate rule condition format"""
        # Basic validation - should be expanded based on condition types
        if not isinstance(condition, dict):
            return False
            
        # For "any" type conditions
        if condition.get("type") == "any":
            return True

        # For price conditions
        if "gt" in condition or "lt" in condition:
            return isinstance(condition.get("gt", 0), (int, float)) and \
                   isinstance(condition.get("lt", 0), (int, float))

        # Add more condition validations as needed
        return True

    async def close(self):
        """Cleanup resources"""
        try:
            if self.redis:
                await self.redis.close()
                self.redis = None
                logger.info("[RuleProcessor] Successfully closed Redis connection")
            if self.mongo:
                await self.mongo.close()
                self.mongo = None
                logger.info("[RuleProcessor] Successfully closed MongoDB connection")
        except Exception as e:
            logger.error(f"[RuleProcessor] Error closing connections: {e}", exc_info=True)

async def main():
    """Main entry point for rule processor"""
    processor = RuleProcessor()
    try:
        await processor.start()
    except KeyboardInterrupt:
        logger.info("[RuleProcessor] Rule processor shutting down")
    finally:
        await processor.close()

if __name__ == "__main__":
    asyncio.run(main())
