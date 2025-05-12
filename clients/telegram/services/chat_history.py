# services/chat_history.py

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from clients.config import MONGO_URI, MONGO_DB
from clients.telegram.utils.logger import logger

class ChatHistoryService:
    def __init__(self):
        # MongoDB setup
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client[MONGO_DB]
        self.collection = self.db["chat_history"]

        # Create text index for search
        self.collection.create_index([("message", "text")])

    async def save_message(self, 
                          message: str,
                          user_id: str,
                          chat_id: str,
                          chat_type: str,
                          metadata: Dict[str, Any]) -> None:
        """
        Save a message to chat history
        Args:
            message: Message content
            user_id: ID of the user who sent the message
            chat_id: ID of the chat (group or private)
            chat_type: Type of chat (private, group, supergroup)
            metadata: Additional message metadata including:
                - message_type: Type of message (user, ai, system)
                - user_name: Username of sender
                - user_full_name: Full name of sender
                - message_id: Telegram message ID
                - thread_id: Thread ID if in a forum
                - is_reply: Whether message is a reply
                - reply_to_message_id: ID of message being replied to
                - reply_to_user_id: ID of user being replied to
                - replied_message_content: Content of replied message
        """
        try:
            document = {
                "message": message,
                "user_id": user_id,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "metadata": {
                    "message_type": metadata.get("message_type", "user"),  # user, ai, or system
                    "user_name": metadata.get("user_name"),
                    "user_full_name": metadata.get("user_full_name"),
                    "message_id": metadata.get("message_id"),
                    "thread_id": metadata.get("thread_id"),
                    "is_reply": metadata.get("is_reply", False),
                    "reply_to_message_id": metadata.get("reply_to_message_id"),
                    "reply_to_user_id": metadata.get("reply_to_user_id"),
                    "replied_message_content": metadata.get("replied_message_content"),
                    "timestamp": datetime.utcnow().isoformat()
                }
            }
            await self.collection.insert_one(document)
            logger.info(f"Saved {metadata.get('message_type', 'user')} message from {user_id} in {chat_type} {chat_id}")

        except Exception as e:
            logger.error(f"Error saving message to chat history: {e}")

    async def search_similar_messages(self, 
                                    query: str,
                                    chat_id: Optional[str] = None,
                                    limit: int = 5) -> list:
        """
        Search for similar messages in chat history
        """
        try:
            # MongoDB text search
            search_query = {"$text": {"$search": query}}
            if chat_id:
                search_query["chat_id"] = chat_id
            
            cursor = self.collection.find(
                search_query,
                {"score": {"$meta": "textScore"}}
            ).sort([("score", {"$meta": "textScore"})]).limit(limit)
            
            results = await cursor.to_list(length=limit)
            return results

        except Exception as e:
            logger.error(f"Error searching messages: {e}")
            return []

    async def get_chat_history(self,
                              chat_id: str,
                              limit: int = 50) -> list:
        """
        Get chat history for a specific chat
        """
        try:
            # MongoDB query
            cursor = self.collection.find(
                {"chat_id": chat_id}
            ).sort("timestamp", -1).limit(limit)
            
            results = await cursor.to_list(length=limit)
            return results

        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []

    async def clear_chat_history(self, chat_id: str):
        """
        Clear chat history for a specific chat
        """
        try:
            await self.collection.delete_many({"chat_id": chat_id})
        except Exception as e:
            logger.error(f"Error clearing chat history: {e}")

# Singleton instance
_chat_history_service = None

async def get_chat_history_service() -> ChatHistoryService:
    """
    Get or create chat history service instance
    """
    global _chat_history_service
    if _chat_history_service is None:
        _chat_history_service = ChatHistoryService()
    return _chat_history_service 