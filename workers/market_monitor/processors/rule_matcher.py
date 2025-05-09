import asyncio
import logging
import json
from typing import Dict, List, Optional

from workers.market_monitor.shared.models import Rule, RuleMatch, Notification
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RuleMatcher:
    def __init__(self):
        self.redis = None

    async def start(self):
        """Start the rule matcher processor"""
        try:
            logger.info("[RuleMatcher] Initializing...")
            self.redis = await RedisClient.get_instance()
            logger.info("[RuleMatcher] Redis connection established")

            # Subscribe to rule matched events
            logger.info("[RuleMatcher] Subscribing to market_watch:rule_matched channel")
            await self.redis.subscribe("market_watch:rule_matched", self.process_match)
            logger.info("[RuleMatcher] Successfully subscribed to rule_matched channel")

            logger.info("[RuleMatcher] Processor started and running")
            # Keep the processor running
            while True:
                try:
                    await asyncio.sleep(0.1)  # Prevent tight loop
                except Exception as e:
                    logger.error(f"[RuleMatcher] Error in main loop: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[RuleMatcher] Failed to start: {e}")
            raise

    async def process_match(self, channel: str, match_data: Dict):
        """Process match from rule_matched channel"""
        try:
            logger.info(f"[RuleMatcher] Processing match data: {json.dumps(match_data, cls=MongoJSONEncoder)}")
            
            # Convert data to RuleMatch
            rule = Rule.from_dict(match_data["rule"])
            match = RuleMatch(
                rule=rule,
                match_data=match_data["match_data"]
            )
            logger.info(f"[RuleMatcher] Created RuleMatch for rule {rule.rule_id}")

            # Validate match
            if not self.validate_match(match):
                logger.warning(f"[RuleMatcher] Invalid match data: {match_data}")
                return
            logger.info(f"[RuleMatcher] Match data validated successfully")

            # Check for duplicate notification
            notification_key = f"notify:last:{rule.rule_id}"
            last_notify = await self.redis.get(notification_key)
            
            # Get current match data for comparison
            current_match = json.dumps(match.match_data, cls=MongoJSONEncoder, sort_keys=True)
            
            # Handle both string and dict data types from Redis
            if last_notify:
                try:
                    if isinstance(last_notify, bytes):
                        last_notify = last_notify.decode()
                    elif isinstance(last_notify, dict):
                        last_notify = json.dumps(last_notify, cls=MongoJSONEncoder, sort_keys=True)
                    elif isinstance(last_notify, str):
                        pass
                    else:
                        last_notify = str(last_notify)
                        
                    if last_notify == current_match:
                        logger.info(f"[RuleMatcher] Skipping duplicate notification for rule {rule.rule_id}")
                        return
                except Exception as e:
                    logger.warning(f"[RuleMatcher] Error comparing notification data: {e}")
                    # Continue processing if comparison fails
                    
            logger.info(f"[RuleMatcher] No duplicate found, proceeding with notification")
                
            # Create notification
            notification = self.create_notification(match)
            if notification:
                logger.info(f"[RuleMatcher] Created notification: {json.dumps(notification.to_dict(), cls=MongoJSONEncoder)}")
                
                # Publish to notification channel
                await self.redis.publish(
                    "market_watch:send_notify",
                    json.dumps(notification.to_dict(), cls=MongoJSONEncoder)
                )
                logger.info(f"[RuleMatcher] Published notification to market_watch:send_notify")
                
                # Store current match data to prevent duplicates
                await self.redis.set(notification_key, current_match, 60)  # Expire after 60 seconds
                logger.info(f"[RuleMatcher] Stored match data in Redis for deduplication")
                
                logger.info(f"[RuleMatcher] Match processed successfully for rule {rule.rule_id}")
            else:
                logger.warning(f"[RuleMatcher] Failed to create notification for rule {rule.rule_id}")

        except Exception as e:
            logger.error(f"[RuleMatcher] Error processing match {match_data}: {e}", exc_info=True)

    def validate_match(self, match: RuleMatch) -> bool:
        """Validate match data"""
        try:
            if not match.rule or not match.match_data:
                return False

            # Validate matches list exists
            matches = match.match_data.get("matches", [])
            if not isinstance(matches, list):
                return False

            # Validate each match
            for m in matches:
                if not isinstance(m, dict):
                    return False
                    
                # For price alerts, require token
                if m.get("condition") in ["price_above", "price_below", "price_change", "price_change_24h"]:
                    if "token" not in m:
                        return False
                        
                # For general alerts, require message
                elif m.get("condition") == "alert":
                    if "message" not in m:
                        return False

            return True

        except Exception as e:
            logger.error(f"Error validating match: {e}")
            return False

    def create_notification(self, match: RuleMatch) -> Optional[Notification]:
        """Create notification from match data"""
        try:
            # Extract data
            rule = match.rule
            matches = match.match_data["matches"]
            token_data = match.match_data.get("token_data", {})

            # Build notification message
            messages = []
            for m in matches:
                condition = m.get("condition")
                token = m["token"]
                
                if condition == "price_above":
                    current_price = m["value"]  # Giá hiện tại
                    msg = f"<b>{token}</b> price above ${m['threshold']:,.2f} (current: ${current_price:,.2f})"
                elif condition == "price_below":
                    current_price = m["value"]  # Giá hiện tại
                    msg = f"<b>{token}</b> price below ${m['threshold']:,.2f} (current: ${current_price:,.2f})"
                elif condition == "price_change":
                    change = m["value"]  # Phần trăm thay đổi
                    old_price = m["old_price"]
                    new_price = m["new_price"]
                    direction = "increased" if change > 0 else "decreased"
                    msg = f"<b>{token}</b> {direction} by {abs(change):.1f}% (from ${old_price:,.2f} → ${new_price:,.2f})"
                elif condition == "price_change_24h":
                    change = m["value"]  # Phần trăm thay đổi 24h
                    current_price = m.get("current_price", 0)  # Lấy giá hiện tại từ match data
                    direction = "increased" if change > 0 else "decreased"
                    msg = f"<b>{token}</b> {direction} by {abs(change):.1f}% in 24h (current: ${current_price:,.2f})"
                elif condition == "alert":
                    # For alert messages, use the message directly
                    msg = m.get("message", "")
                    if not msg:
                        continue
                else:  # any condition
                    price = m["price"]
                    change = m["change"]
                    change_24h = m["change_24h"]
                    msg = f"<b>{token}</b>: ${price:,.2f} ({'+' if change >= 0 else ''}{change:.1f}% | {'+' if change_24h >= 0 else ''}{change_24h:.1f}% 24h)"

                messages.append(msg)

            if not messages:
                return None

            return Notification(
                user=rule.notify_id,
                channel=rule.notify_channel,
                message="\n".join(messages),
                metadata={
                    "rule_id": rule.rule_id,
                    "user_id": rule.user_id,
                    "conversation_id": rule.metadata.get("conversation_id"),
                    "parse_mode": "HTML"  # Add parse_mode for HTML formatting
                }
            )

        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None

    async def close(self):
        """Cleanup resources"""
        if self.redis:
            await self.redis.close()

async def main():
    """Main entry point for rule matcher"""
    matcher = RuleMatcher()
    try:
        await matcher.start()
    except KeyboardInterrupt:
        logger.info("Rule matcher shutting down")
    finally:
        await matcher.close()

if __name__ == "__main__":
    asyncio.run(main())
