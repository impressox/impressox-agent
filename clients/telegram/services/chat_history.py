# services/chat_history.py

import logging
from datetime import datetime
from typing import Dict, Any, Optional
from motor.motor_asyncio import AsyncIOMotorClient
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
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

        # Vector store setup (disabled for now)
        self.use_vector_store = False
        if self.use_vector_store:
            self.embeddings = OpenAIEmbeddings()
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )
            self.vector_store = Chroma(
                collection_name="telegram_chat_history",
                embedding_function=self.embeddings,
                persist_directory="./data/chat_history"
            )

    async def save_message(self, 
                          message: str,
                          user_id: str,
                          chat_id: str,
                          chat_type: str,
                          metadata: Dict[str, Any]) -> None:
        """
        Save a message to chat history
        """
        try:
            document = {
                "message": message,
                "user_id": user_id,
                "chat_id": chat_id,
                "chat_type": chat_type,
                "metadata": metadata or {},
                "timestamp": datetime.utcnow()
            }
            await self.collection.insert_one(document)

            # Save to vector store if enabled
            if self.use_vector_store:
                vector_doc = Document(
                    page_content=message,
                    metadata={
                        "user_id": user_id,
                        "chat_id": chat_id,
                        "chat_type": chat_type,
                        "timestamp": datetime.now().isoformat(),
                        **metadata
                    }
                )
                docs = self.text_splitter.split_documents([vector_doc])
                self.vector_store.add_documents(docs)
                self.vector_store.persist()

            logger.info(f"Saved message from user {user_id} in chat {chat_id}")

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
            if self.use_vector_store:
                # Vector store search
                filter_dict = {}
                if chat_id:
                    filter_dict["chat_id"] = chat_id
                results = self.vector_store.similarity_search(
                    query,
                    k=limit,
                    filter=filter_dict if filter_dict else None
                )
                return results
            else:
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
            if self.use_vector_store:
                # Vector store search
                results = self.vector_store.similarity_search(
                    "",  # Empty query to get all
                    k=limit,
                    filter={"chat_id": chat_id}
                )
                results.sort(key=lambda x: x.metadata["timestamp"], reverse=True)
                return results
            else:
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