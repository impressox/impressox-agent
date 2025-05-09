# services/notification_service.py

import json
import logging
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from workers.market_monitor.utils.mongo import get_mongo
from workers.market_monitor.shared.models import Rule
from workers.market_monitor.shared.redis_utils import RedisClient
from workers.market_monitor.utils.config import get_config

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.redis_client = None
        self.config = get_config()
        self.mongo = None
        self.notification_collection = None

    async def start(self):
        """Start notification service"""
        try:
            # Initialize Redis client
            self.redis_client = await RedisClient.get_instance()
            
            # Initialize MongoDB client
            self.mongo = await get_mongo()
            self.notification_collection = self.mongo.db.notifications
            
            logger.info("Notification service started")
        except Exception as e:
            logger.error(f"Error starting notification service: {e}")
            raise
            
    async def stop(self):
        """Stop notification service"""
        try:
            if self.redis_client:
                await RedisClient.close()
            logger.info("Notification service stopped")
        except Exception as e:
            logger.error(f"Error stopping notification service: {e}")
            
    async def send_notification(self, notification: Dict[str, Any]):
        """Send notification to Redis queue"""
        try:
            if not self.redis_client:
                self.redis_client = await RedisClient.get_instance()
                
            # Add timestamp
            notification["timestamp"] = datetime.utcnow().isoformat()
            
            # Push to notification queue
            await self.redis_client.lpush("notifications", notification)
            logger.info(f"Notification sent: {notification}")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            raise
            
    async def get_notifications(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent notifications"""
        try:
            if not self.redis_client:
                self.redis_client = await RedisClient.get_instance()
                
            # Get notifications from queue
            notifications = await self.redis_client.lrange("notifications", 0, limit - 1)
            return [json.loads(n) for n in notifications]
            
        except Exception as e:
            logger.error(f"Error getting notifications: {e}")
            return []

    async def create_notification(self, rule: Rule, matches: List[Dict], data: Dict) -> Dict:
        """Create a notification based on rule type and matches"""
        try:
            notification = {
                "rule_id": rule.rule_id,
                "user_id": rule.user_id,
                "type": rule.watch_type,
                "matches": matches,
                "data": data,
                "created_at": datetime.utcnow(),
                "status": "pending"
            }

            # Format message based on watch type
            if rule.watch_type == "token":
                notification["message"] = self._format_token_message(rule, matches, data)
            elif rule.watch_type == "wallet":
                notification["message"] = self._format_wallet_message(rule, matches, data)
            else:
                notification["message"] = "Alert triggered"

            # Save to MongoDB
            result = await self.notification_collection.insert_one(notification)
            notification["_id"] = result.inserted_id

            # Publish to Redis for real-time notifications
            await self.redis_client.lpush(
                "notifications",
                json.dumps(notification)
            )

            logger.info(f"Created notification for rule {rule.rule_id}: {notification['message']}")
            return notification

        except Exception as e:
            logger.error(f"Error creating notification: {e}")
            return None

    def _format_token_message(self, rule: Rule, matches: List[Dict], data: Dict) -> str:
        """Format message for token notifications"""
        try:
            token = rule.target[0]  # Token symbol
            messages = []

            for match in matches:
                condition = match.get("condition")
                if condition == "price_above":
                    messages.append(
                        f"{token} price above {match['threshold']} (current: {match['value']})"
                    )
                elif condition == "price_below":
                    messages.append(
                        f"{token} price below {match['threshold']} (current: {match['value']})"
                    )
                elif condition == "price_change":
                    direction = "increased" if match["change"] > 0 else "decreased"
                    messages.append(
                        f"{token} {direction} by {abs(match['change'])}% "
                        f"(from {match['old_price']} → {match['new_price']})"
                    )
                elif condition == "price_change_24h":
                    direction = "increased" if match["change"] > 0 else "decreased"
                    messages.append(
                        f"{token} {direction} by {abs(match['change'])}% in 24h"
                    )

            return " | ".join(messages) if messages else "Token alert triggered"

        except Exception as e:
            logger.error(f"Error formatting token message: {e}")
            return "Token alert triggered"

    def _format_wallet_message(self, rule: Rule, matches: List[Dict], data: Dict) -> str:
        """Format message for wallet notifications"""
        try:
            messages = []

            for match in matches:
                wallet = match.get("wallet")
                condition = match.get("condition")

                if condition == "balance_below":
                    messages.append(
                        f"Wallet {wallet} balance below {match['threshold']} "
                        f"(current: {match['value']})"
                    )
                elif condition == "balance_change":
                    direction = "increased" if match["value"] > 0 else "decreased"
                    messages.append(
                        f"Wallet {wallet} balance {direction} by {abs(match['value'])} "
                        f"(from {match['old_balance']} → {match['new_balance']})"
                    )
                elif condition == "token_transfer":
                    direction = "received" if match["direction"] == "in" else "sent"
                    messages.append(
                        f"Wallet {wallet} {direction} {match['amount']} {match['token']} "
                        f"(tx: {match['tx_hash'][:8]}...)"
                    )
                elif condition == "nft_transfer":
                    direction = "received" if match["direction"] == "in" else "sent"
                    messages.append(
                        f"Wallet {wallet} {direction} NFT {match['token_id']} "
                        f"from {match['collection']} (tx: {match['tx_hash'][:8]}...)"
                    )

            return " | ".join(messages) if messages else "Wallet alert triggered"

        except Exception as e:
            logger.error(f"Error formatting wallet message: {e}")
            return "Wallet alert triggered"

    async def get_user_notifications(self, user_id: str, limit: int = 50) -> List[Dict]:
        """Get recent notifications for a user"""
        try:
            cursor = self.notification_collection.find(
                {"user_id": user_id}
            ).sort("created_at", -1).limit(limit)
            
            notifications = await cursor.to_list(length=limit)
            return notifications

        except Exception as e:
            logger.error(f"Error getting user notifications: {e}")
            return []

    async def mark_notification_read(self, notification_id: str) -> bool:
        """Mark a notification as read"""
        try:
            result = await self.notification_collection.update_one(
                {"_id": notification_id},
                {"$set": {"status": "read"}}
            )
            return result.modified_count > 0

        except Exception as e:
            logger.error(f"Error marking notification as read: {e}")
            return False 