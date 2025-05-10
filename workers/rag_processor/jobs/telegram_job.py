from datetime import datetime
from typing import List, Dict, Optional
from pymongo import MongoClient
from ..common.chunker import SemanticChunker
from ..common.vector_store import VectorStore

class TelegramProcessor:
    def __init__(self, mongo_uri: str, db_name: str):
        """Initialize MongoDB client"""
        self.client = MongoClient(mongo_uri)
        self.db = self.client[db_name]
        self.chunker = SemanticChunker()
        self.vector_store = VectorStore()

    def _process_message(self, message: Dict) -> List[Dict]:
        """Process a single message into chunks with metadata"""
        text = message.get('text', '')
        if not text:
            return []

        metadata = {
            "source": "telegram",
            "message_id": str(message['_id']),
            "sender": message.get('from', {}).get('username', 'unknown'),
            "chat_id": str(message.get('chat', {}).get('id')),
            "chat_type": message.get('chat', {}).get('type', 'unknown'),
            "timestamp": message.get('date', datetime.now()).isoformat()
        }

        return self.chunker.chunk_with_metadata(text, metadata)

    def process_messages(self, last_run: Optional[str] = None) -> bool:
        """Process new messages since last run"""
        try:
            # Query for new messages
            query = {}
            if last_run:
                query['date'] = {'$gt': datetime.fromisoformat(last_run)}

            messages = self.db.messages.find(query).sort('date', 1)

            processed_any = False
            for message in messages:
                chunks = self._process_message(message)
                if chunks:
                    self.vector_store.add_documents(chunks)
                    processed_any = True

            return processed_any

        except Exception as e:
            print(f"Error processing Telegram messages: {str(e)}")
            return False

def process_telegram_data(last_run: Optional[str] = None) -> bool:
    """Process Telegram data and return True if new data was processed"""
    # Initialize processor with MongoDB connection details
    processor = TelegramProcessor(
        mongo_uri="mongodb://localhost:27017",
        db_name="telegram_db"
    )
    
    return processor.process_messages(last_run) 