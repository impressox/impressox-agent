import asyncio
import logging
import aiohttp
import json
from typing import Dict, Optional
from datetime import datetime, timedelta

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

    async def start(self):
        """Start the notification dispatcher"""
        try:
            logger.info("[NotifyDispatcher] Initializing...")
            self.redis = await RedisClient.get_instance()
            logger.info("[NotifyDispatcher] Redis connection established")
            
            self.session = aiohttp.ClientSession()
            logger.info("[NotifyDispatcher] HTTP session created")
            
            logger.info("[NotifyDispatcher] Subscribing to market_watch:send_notify channel")
            await self.redis.subscribe("market_watch:send_notify", self.process_notification)
            logger.info("[NotifyDispatcher] Successfully subscribed to send_notify channel")

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
            recent_messages = await self.redis.lrange(recent_key, 0, -1)
            
            # Check if this message is in recent messages
            if message_hash.encode() in recent_messages:
                logger.info(f"[NotifyDispatcher] Found duplicate notification for {notification.user} on {notification.channel}: {notification.message[:50]}...")
                return True
                
            # Add this message to recent messages
            await self.redis.lpush(recent_key, message_hash)
            # Trim list to keep only last N messages
            await self.redis.ltrim(recent_key, 0, self.dedup_max_messages - 1)
            # Set expiry on the list
            await self.redis.expire(recent_key, self.dedup_window)
            
            logger.info(f"[NotifyDispatcher] Added new notification to recent list for {notification.user} on {notification.channel}")
            return False
            
        except Exception as e:
            logger.error(f"[NotifyDispatcher] Error checking duplicate notification: {e}")
            return False  # Allow notification on error

    async def check_rate_limit(self, channel: NotifyChannel, user: str) -> bool:
        """Check if user has exceeded rate limit for the channel"""
        try:
            key = f"rate_limit:{channel.value}:{user}"
            current = await self.redis.get(key)
            
            if current and int(current) >= self.rate_limits[channel]["max_per_minute"]:
                logger.warning(f"Rate limit exceeded for {user} on {channel}")
                return False
            
            # Use setex to set value with expiry in one command
            if not current:
                await self.redis.set(key, "1", 60)  # 1 minute expiry
            else:
                await self.redis.set(key, str(int(current) + 1), 60)
            
            return True
        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            return False  # Deny notification on error to prevent spam

    async def process_notification(self, channel: str, notify_data: Dict):
        """Process notification from send_notify channel"""
        try:
            logger.info(f"[NotifyDispatcher] Processing notification: {json.dumps(notify_data, cls=MongoJSONEncoder)}")
            
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
                await self.redis.publish(
                    "market_watch:notify_duplicate",
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
                await self.redis.publish(
                    "market_watch:notify_failed",
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
                        await self.redis.set(status_key, "sent", self.dedup_window)
                        await self.redis.publish(
                            "market_watch:notify_sent",
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
            await self.redis.publish(
                "market_watch:notify_failed",
                json.dumps({
                    "rule_id": notification.metadata.get("rule_id"),
                    "user_id": notification.metadata.get("user_id"),
                    "channel": notification.channel.value,
                    "error": f"Failed after {self.max_retries} attempts"
                }, cls=MongoJSONEncoder)
            )

        except Exception as e:
            logger.error(f"[NotifyDispatcher] Error processing notification {notify_data}: {e}", exc_info=True)
            if notify_data.get("metadata"):
                await self.redis.publish(
                    "market_watch:notify_failed",
                    json.dumps({
                        "rule_id": notify_data["metadata"].get("rule_id"),
                        "user_id": notify_data["metadata"].get("user_id"),
                        "channel": notify_data.get("channel"),
                        "error": str(e)
                    }, cls=MongoJSONEncoder)
                )

    async def send_telegram(self, notification: Notification) -> bool:
        """Send notification via Telegram Bot API"""
        try:
            # Get bot token from config
            bot_token = self.config.notification["telegram"]["bot_token"]
            if not bot_token:
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
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            logger.info(f"Sending Telegram message to {notification.user}: {message}")
            
            async with self.session.post(
                url, 
                json=message, 
                timeout=self.config.notification["telegram"]["timeout"]
            ) as response:
                response_text = await response.text()
                logger.info(f"Telegram API response: {response.status} - {response_text}")
                
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
        if self.redis:
            await self.redis.close()
        if self.session:
            await self.session.close()

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
