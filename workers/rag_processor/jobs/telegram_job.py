from datetime import datetime
from typing import List, Dict, Optional
import os
import logging
from dotenv import load_dotenv
from pymongo import MongoClient
from workers.rag_processor.common.chunker import SemanticChunker
from workers.rag_processor.common.vector_store import VectorStore

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class TelegramProcessor:
    def __init__(self, mongo_uri: str = None, db_name: str = None):
        """Initialize MongoDB client with environment variables"""
        self.client = MongoClient(mongo_uri or os.getenv('TELE_MONGODB_URI', 'mongodb://localhost:27017'))
        self.db = self.client[db_name or os.getenv('TELE_MONGODB_DB_NAME', 'telegram_db')]
        self.messages_collection = self.db["chat_history"]
        self.chunker = SemanticChunker(language='en')  # Use English for sentence splitting
        self.vector_store = VectorStore()
        logger.info("TelegramProcessor initialized")

    def _get_safe_value(self, value: any, default: any = '') -> any:
        """Get a safe value for metadata, replacing None with default"""
        return value if value is not None else default

    def _process_message(self, message: Dict) -> List[Dict]:
        """Process a single message into chunks with metadata"""
        try:
            text = message.get('message', '')
            if not text:
                logger.debug(f"Skipping message {message.get('_id', 'unknown')} - empty text")
                return []

            # Extract timestamp from MongoDB ISODate format
            timestamp = message.get('timestamp', {})
            if isinstance(timestamp, dict) and '$date' in timestamp:
                timestamp = timestamp['$date']
            else:
                timestamp = datetime.now().isoformat()

            # Get metadata with safe values
            metadata = message.get('metadata', {})
            metadata_dict = {
                "source": "telegram",
                "message_id": str(message.get('_id', '')),
                "sender": self._get_safe_value(metadata.get('user_name')),
                "sender_full_name": self._get_safe_value(metadata.get('user_full_name')),
                "chat_id": str(message.get('chat_id', '')),
                "chat_type": self._get_safe_value(message.get('chat_type')),
                "timestamp": timestamp,
                "message_type": self._get_safe_value(metadata.get('message_type')),
                "is_reply": bool(metadata.get('is_reply', False)),
                "reply_to_message_id": self._get_safe_value(metadata.get('reply_to_message_id')),
                "reply_to_user_id": self._get_safe_value(metadata.get('reply_to_user_id'))
            }

            chunks = self.chunker.chunk_with_metadata(text, metadata_dict)
            logger.debug(f"Processed message {message.get('_id', 'unknown')} into {len(chunks)} chunks")
            return chunks
        except Exception as e:
            logger.error(f"Error processing message {message.get('_id', 'unknown')}: {str(e)}")
            return []

    def process_messages(self, last_run: Optional[str] = None) -> bool:
        """Process new messages since last run"""
        try:
            # Query for new messages
            if last_run:
                last_run_dt = datetime.fromisoformat(last_run)
                logger.info(f"Querying messages after {last_run}")
                pipeline = [
                    {
                        "$addFields": {
                            "timestamp_date": {
                                "$toDate": {
                                    "$getField": {
                                        "field": "date",
                                        "input": "$timestamp"
                                    }
                                }
                            }
                        }
                    },
                    {
                        "$match": {
                            "timestamp_date": {"$gt": last_run_dt}
                        }
                    },
                    {
                        "$sort": {"timestamp_date": 1}
                    }
                ]
            else:
                logger.info("Processing all available messages")
                pipeline = [
                    {
                        "$addFields": {
                            "timestamp_date": {
                                "$toDate": {
                                    "$getField": {
                                        "field": "date",
                                        "input": "$timestamp"
                                    }
                                }
                            }
                        }
                    },
                    {
                        "$sort": {"timestamp_date": 1}
                    }
                ]

            messages = self.messages_collection.aggregate(pipeline)
            messages_list = list(messages)
            logger.info(f"Found {len(messages_list)} messages to process")

            if not messages_list:
                logger.info("No new messages to process")
                return False

            # Process each message
            processed_count = 0
            for message in messages_list:
                chunks = self._process_message(message)
                if chunks:
                    self.vector_store.add_documents(chunks)
                    processed_count += 1

            logger.info(f"Successfully processed {processed_count} messages")
            return True

        except Exception as e:
            logger.error(f"Error processing Telegram messages: {str(e)}", exc_info=True)
            return False

def process_telegram_data(last_run: Optional[str] = None) -> bool:
    """Process Telegram data and return True if new data was processed"""
    try:
        # Initialize processor with MongoDB connection details from environment variables
        processor = TelegramProcessor()
        return processor.process_messages(last_run)
    except Exception as e:
        logger.error(f"Error in process_telegram_data: {str(e)}", exc_info=True)
        return False 