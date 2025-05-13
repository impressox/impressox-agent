import asyncio
import logging
import aiohttp
import json
from typing import Dict, Optional, List
from datetime import datetime, timedelta
import time

from workers.market_monitor.shared.models import Notification, NotifyChannel
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.config import get_config
from workers.market_monitor.utils.mongo import MongoJSONEncoder

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotifyDispatcher:
    def __init__(self):
        self.redis = None
        self.config = get_config()
        self.notifiers = {
            NotifyChannel.TELEGRAM: self.send_telegram,
            NotifyChannel.WEB: self.send_web,
            NotifyChannel.DISCORD: self.send_discord
        }
        # Load rate limits from config
        self.rate_limits = {
            NotifyChannel.TELEGRAM: self.config.notification["rate_limits"]["telegram"],
            NotifyChannel.WEB: self.config.notification["rate_limits"]["web"],
            NotifyChannel.DISCORD: self.config.notification["rate_limits"]["discord"]
        }
        # Load retry settings from config
        self.max_retries = self.config.notification["retry"]["max_retries"]
        self.retry_delay = self.config.notification["retry"]["retry_delay"]
        # HTTP session for API calls
        self.session = None
        # Deduplication settings
        self.dedup_window = self.config.notification.get("dedup_window", 300)  # Default 5 minutes
        self.dedup_max_messages = self.config.notification.get("dedup_max_messages", 10)  # Keep last 10 messages
        # Supported watch types
        self.watch_types = ["market", "wallet", "airdrop"]
        # Telegram specific settings
        self.telegram_bot_token = self.config.notification["telegram"]["bot_token"]
        self.telegram_api_url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        self.telegram_timeout = self.config.notification["telegram"]["timeout"]

    async def start(self):
        """Start the notification dispatcher"""
        try:
            logger.info("[NotifyDispatcher] Initializing...")
            self.redis = await RedisClient.get_instance()
            logger.info("[NotifyDispatcher] Redis connection established")
            
            # Create HTTP session with optimized settings
            connector = aiohttp.TCPConnector(
                limit=100,  # Max concurrent connections
                ttl_dns_cache=300,  # DNS cache TTL
                force_close=False,  # Enable keep-alive
                enable_cleanup_closed=True  # Clean up closed connections
            )
            self.session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=self.telegram_timeout,
                    connect=5,  # Connection timeout
                    sock_read=5  # Read timeout
                )
            )
            logger.info("[NotifyDispatcher] HTTP session created with optimized settings")
            
            # Subscribe to all watch types
            for watch_type in self.watch_types:
                channel = f"{watch_type}_watch:send_notify"
                logger.info(f"[NotifyDispatcher] Subscribing to {channel}")
                await self.redis.subscribe(channel, self.process_notification)
                logger.info(f"[NotifyDispatcher] Successfully subscribed to {channel}")

            logger.info("[NotifyDispatcher] Processor started and running")
            # Keep the processor running
            while True:
                try:
                    await asyncio.sleep(0.1)  # Prevent tight loop
                except Exception as e:
                    logger.error(f"[NotifyDispatcher] Error in main loop: {e}")
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[NotifyDispatcher] Failed to start: {e}")
            raise

    async def is_duplicate_notification(self, notification: Notification) -> bool:
        """Check if this notification was recently sent"""
        try:
            # Create a unique key for this notification
            message_hash = f"{notification.channel.value}:{notification.user}:{notification.message}"
            key = f"notify:dedup:{message_hash}"
            
            # Get recent notifications for this user/channel
            recent_key = f"notify:recent:{notification.channel.value}:{notification.user}"
            
            # Check if this message is in recent messages
            is_member = await self.redis.sismember(recent_key, message_hash)
            if is_member:
                logger.info(f"[NotifyDispatcher] Found duplicate notification for {notification.user} on {notification.channel}: {notification.message[:50]}...")
                return True
                
            # Add this message to recent messages
            await self.redis.sadd(recent_key, message_hash)
            
            # Set expiry on the set
            await self.redis.expire(recent_key, self.dedup_window)
            
            # If set is too large, remove oldest entries
            set_size = await self.redis.scard(recent_key)
            if set_size > self.dedup_max_messages:
                # Remove random members to get back to max size
                await self.redis.spop(recent_key, set_size - self.dedup_max_messages)
            
            logger.info(f"[NotifyDispatcher] Added new notification to recent set for {notification.user} on {notification.channel}")
            return False
            
        except Exception as e:
            logger.error(f"[NotifyDispatcher] Error checking duplicate notification: {e}")
            return False  # Allow notification on error

    async def check_rate_limit(self, channel: NotifyChannel, user: str) -> bool:
        """Check if user has exceeded rate limit for the channel using basic Redis commands"""
        try:
            key = f"rate_limit:{channel.value}:{user}"
            now = int(time.time())
            window_size = 60  # 1 minute window
            max_messages = self.rate_limits[channel]["max_per_minute"]
            
            # Get all timestamps
            timestamps = await self.redis.hgetall(key)
            if timestamps:
                # Convert to dict of int timestamps
                timestamps = {k: int(v) for k, v in timestamps.items()}
                
                # Remove old messages
                current_timestamps = {k: v for k, v in timestamps.items() if v > now - window_size}
                
                # Count messages in current window
                message_count = len(current_timestamps)
                
                if message_count >= max_messages:
                    logger.warning(f"Rate limit exceeded for {user} on {channel}: {message_count}/{max_messages} messages in last minute")
                    return False
                
                # Update timestamps
                if current_timestamps != timestamps:
                    # Delete old key and create new one with current timestamps
                    await self.redis.delete(key)
                    if current_timestamps:
                        await self.redis.hmset(key, current_timestamps)
            else:
                message_count = 0
            
            # Add current message
            await self.redis.hset(key, str(now), now)
            
            # Set expiry on the key (2x window size to be safe)
            await self.redis.expire(key, window_size * 2)
            
            return True
            
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False  # Deny notification on error to prevent spam

    async def process_notification(self, channel: str, notify_data: Dict):
        """Process notification from send_notify channel"""
        try:
            logger.info(f"[NotifyDispatcher] Processing notification: {json.dumps(notify_data, cls=MongoJSONEncoder)}")
            
            # Handle both old and new notification formats
            if "rule" in notify_data and "match_data" in notify_data:
                # New format
                rule = notify_data.get("rule", {})
                match_data = notify_data.get("match_data", {})
                notification = Notification(
                    user=rule.get("notify_id"),
                    channel=NotifyChannel(rule.get("notify_channel")),
                    message=self._format_message(rule, match_data),
                    metadata={
                        "rule_id": rule.get("rule_id"),
                        "user_id": rule.get("user_id"),
                        "watch_type": rule.get("watch_type"),
                        "target": rule.get("target")
                    }
                )
            else:
                # Old format
                notification = Notification(
                    user=notify_data["user"],
                    channel=NotifyChannel(notify_data["channel"]),
                    message=notify_data["message"],
                    metadata=notify_data.get("metadata", {})
                )
            
            logger.info(f"[NotifyDispatcher] Created notification object for user {notification.user} on channel {notification.channel}")

            # Check for duplicate notification
            if await self.is_duplicate_notification(notification):
                logger.info(f"[NotifyDispatcher] Skipping duplicate notification for {notification.user} on {notification.channel}")
                # Publish duplicate event
                watch_type = notification.metadata.get("watch_type", "market")
                await self.redis.publish(
                    f"{watch_type}_watch:notify_duplicate",
                    json.dumps({
                        "rule_id": notification.metadata.get("rule_id"),
                        "user_id": notification.metadata.get("user_id"),
                        "channel": notification.channel.value,
                        "message": notification.message[:100]  # First 100 chars
                    }, cls=MongoJSONEncoder)
                )
                return
            logger.info(f"[NotifyDispatcher] No duplicate found, proceeding with notification")

            # Check rate limit
            if not await self.check_rate_limit(notification.channel, notification.user):
                logger.warning(f"[NotifyDispatcher] Rate limit exceeded for {notification.user} on {notification.channel}")
                watch_type = notification.metadata.get("watch_type", "market")
                await self.redis.publish(
                    f"{watch_type}_watch:notify_failed",
                    json.dumps({
                        "rule_id": notification.metadata.get("rule_id"),
                        "user_id": notification.metadata.get("user_id"),
                        "channel": notification.channel.value,
                        "error": "Rate limit exceeded"
                    }, cls=MongoJSONEncoder)
                )
                return
            logger.info(f"[NotifyDispatcher] Rate limit check passed")

            # Get appropriate notifier
            notifier = self.notifiers.get(notification.channel)
            if not notifier:
                logger.error(f"[NotifyDispatcher] No notifier found for channel: {notification.channel}")
                return
            logger.info(f"[NotifyDispatcher] Found notifier for channel {notification.channel}")

            # Track notification status
            status_key = f"notify:status:{notification.channel.value}:{notification.user}:{hash(notification.message)}"
            
            # Retry mechanism
            for attempt in range(self.max_retries):
                try:
                    # Check if notification was already sent successfully
                    status = await self.redis.get(status_key)
                    if status == "sent":
                        logger.info(f"[NotifyDispatcher] Notification already sent successfully for {notification.user} on {notification.channel}")
                        return

                    success = await notifier(notification)
                    if success:
                        logger.info(f"[NotifyDispatcher] Notification sent via {notification.channel} to {notification.user}")
                        # Mark notification as sent
                        await self.redis.set(status_key, "sent", ex=self.dedup_window)
                        watch_type = notification.metadata.get("watch_type", "market")
                        await self.redis.publish(
                            f"{watch_type}_watch:notify_sent",
                            json.dumps({
                                "rule_id": notification.metadata.get("rule_id"),
                                "user_id": notification.metadata.get("user_id"),
                                "channel": notification.channel.value,
                                "success": True,
                                "attempt": attempt + 1
                            }, cls=MongoJSONEncoder)
                        )
                        return
                    else:
                        logger.warning(f"[NotifyDispatcher] Failed to send notification on attempt {attempt + 1}")
                except Exception as e:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"[NotifyDispatcher] Retry {attempt + 1}/{self.max_retries} failed: {e}")
                        await asyncio.sleep(self.retry_delay)
                    else:
                        raise

            logger.error(f"[NotifyDispatcher] Failed to send notification via {notification.channel} after {self.max_retries} attempts")
            watch_type = notification.metadata.get("watch_type", "market")
            await self.redis.publish(
                f"{watch_type}_watch:notify_failed",
                json.dumps({
                    "rule_id": notification.metadata.get("rule_id"),
                    "user_id": notification.metadata.get("user_id"),
                    "channel": notification.channel.value,
                    "error": f"Failed after {self.max_retries} attempts"
                }, cls=MongoJSONEncoder)
            )

        except Exception as e:
            logger.error(f"[NotifyDispatcher] Error processing notification {notify_data}: {e}", exc_info=True)
            watch_type = "market"  # Default to market for old format
            if "rule" in notify_data:
                watch_type = notify_data["rule"].get("watch_type", "market")
            await self.redis.publish(
                f"{watch_type}_watch:notify_failed",
                json.dumps({
                    "rule_id": notify_data.get("rule_id") or notify_data.get("metadata", {}).get("rule_id"),
                    "user_id": notify_data.get("user_id") or notify_data.get("metadata", {}).get("user_id"),
                    "channel": notify_data.get("channel"),
                    "error": str(e)
                }, cls=MongoJSONEncoder)
            )

    def _format_message(self, rule: Dict, match_data: Dict) -> str:
        """Format notification message based on rule and match data"""
        try:
            watch_type = rule.get("watch_type", "unknown")
            target = rule.get("target", [])[0] if rule.get("target") else "unknown"
            matches = match_data.get("matches", [])
            
            # Format message based on watch type
            if watch_type == "token":
                return self._format_token_message(target, matches)
            elif watch_type == "wallet":
                return self._format_wallet_message(target, matches)
            elif watch_type == "airdrop":
                return self._format_airdrop_message(target, matches)
            else:
                return f"Alert: {watch_type} condition met for {target}"
                
        except Exception as e:
            logger.error(f"Error formatting message: {e}")
            return "Alert: Condition met"

    def _format_token_message(self, target: str, matches: List[Dict]) -> str:
        """Format message for token price alerts"""
        try:
            message = f"🚨 Token Alert: {target}\n"
            for match in matches:
                if "price" in match:
                    message += f"Current price: ${match['price']:.4f}\n"
                if "change_24h" in match:
                    message += f"24h change: {match['change_24h']:.2f}%\n"
            return message
        except Exception as e:
            logger.error(f"Error formatting token message: {e}")
            return f"Token Alert: {target}"

    def _format_wallet_message(self, target: str, matches: List[Dict]) -> str:
        """Format message for wallet activity alerts"""
        try:
            message = f"👛 Wallet Alert: {target}\n"
            for match in matches:
                if "transaction" in match:
                    tx = match["transaction"]
                    message += f"New transaction: {tx.get('hash', 'unknown')}\n"
                    message += f"Amount: {tx.get('amount', 'unknown')}\n"
            return message
        except Exception as e:
            logger.error(f"Error formatting wallet message: {e}")
            return f"Wallet Alert: {target}"

    def _format_airdrop_message(self, target: str, matches: List[Dict]) -> str:
        """Format message for airdrop alerts"""
        try:
            message = f"🎁 Airdrop Alert: {target}\n"
            for match in matches:
                if "airdrop" in match:
                    airdrop = match["airdrop"]
                    message += f"New airdrop: {airdrop.get('name', 'unknown')}\n"
                    message += f"Value: {airdrop.get('value', 'unknown')}\n"
            return message
        except Exception as e:
            logger.error(f"Error formatting airdrop message: {e}")
            return f"Airdrop Alert: {target}"

    async def send_telegram(self, notification: Notification) -> bool:
        """Send notification via Telegram Bot API"""
        try:
            if not self.telegram_bot_token:
                logger.error("Telegram bot token not configured")
                return False

            # Prepare message
            message = {
                "chat_id": notification.user,
                "text": notification.message,
                "parse_mode": notification.metadata.get("parse_mode", self.config.notification["telegram"]["parse_mode"])
            }
            
            # Add additional options if provided in metadata
            if notification.metadata:
                if "reply_markup" in notification.metadata:
                    message["reply_markup"] = notification.metadata["reply_markup"]
                if "disable_web_page_preview" in notification.metadata:
                    message["disable_web_page_preview"] = notification.metadata["disable_web_page_preview"]

            # Send message using Telegram Bot API
            logger.info(f"Sending Telegram message to {notification.user}")
            
            async with self.session.post(
                self.telegram_api_url, 
                json=message,
                timeout=self.telegram_timeout
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("ok"):
                        logger.info(f"Telegram message sent successfully to {notification.user}")
                        return True
                    else:
                        error_msg = result.get("description", "Unknown error")
                        logger.error(f"Telegram API error: {error_msg}")
                        return False
                else:
                    response_text = await response.text()
                    logger.error(f"Failed to send Telegram message. Status: {response.status}, Response: {response_text}")
                    return False

        except asyncio.TimeoutError:
            logger.error("Timeout while sending Telegram message")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram notification: {e}", exc_info=True)
            return False

    async def send_web(self, notification: Notification) -> bool:
        """Send notification via Web (e.g. WebSocket)"""
        try:
            # TODO: Implement web notification
            # For now, just log
            logger.info(f"[WEB] To {notification.user}: {notification.message}")
            return True
        except Exception as e:
            logger.error(f"Error sending Web notification: {e}")
            return False

    async def send_discord(self, notification: Notification) -> bool:
        """Send notification via Discord"""
        try:
            # TODO: Implement Discord sending
            # For now, just log
            logger.info(f"[DISCORD] To {notification.user}: {notification.message}")
            return True
        except Exception as e:
            logger.error(f"Error sending Discord notification: {e}")
            return False

    async def close(self):
        """Cleanup resources"""
        try:
            if self.redis:
                await self.redis.close()
                self.redis = None
            if self.session:
                await self.session.close()
                self.session = None
            logger.info("[NotifyDispatcher] Successfully closed all connections")
        except Exception as e:
            logger.error(f"[NotifyDispatcher] Error closing connections: {e}", exc_info=True)

async def main():
    """Main entry point for notify dispatcher"""
    dispatcher = NotifyDispatcher()
    try:
        await dispatcher.start()
    except KeyboardInterrupt:
        logger.info("Notify dispatcher shutting down")
    finally:
        await dispatcher.close()

if __name__ == "__main__":
    asyncio.run(main())
