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

class TwitterProcessor:
    def __init__(self, mongo_uri: str = None, db_name: str = None):
        """Initialize Twitter processor with MongoDB connection"""
        self.client = MongoClient(mongo_uri or os.getenv('TWITTER_MONGODB_URI', 'mongodb://localhost:27017'))
        self.db = self.client[db_name or os.getenv('TWITTER_MONGODB_DB_NAME', 'cpx-data')]
        self.tweets_collection = self.db["tweets"]
        self.chunker = SemanticChunker(language='en')
        self.vector_store = VectorStore()
        logger.info("TwitterProcessor initialized")

    def _get_safe_timestamp(self, tweet: Dict) -> str:
        """Get safe timestamp from tweet"""
        try:
            post_time = tweet.get("post_time")
            if post_time is None:
                logger.warning(f"Tweet {tweet.get('post_id', 'unknown')} has no post_time, using current time")
                return datetime.now().isoformat()
            return post_time.isoformat()
        except Exception as e:
            logger.warning(f"Error getting timestamp for tweet {tweet.get('post_id', 'unknown')}: {str(e)}")
            return datetime.now().isoformat()

    def _get_safe_value(self, value: any, default: any = '') -> any:
        """Get safe value from tweet field"""
        return value if value is not None else default

    def _process_tweet(self, tweet: Dict) -> List[Dict]:
        """Process a single tweet into vector store document"""
        try:
            # Get text with fallback
            text = self._get_safe_value(tweet.get("text", ""))
            if not text:
                logger.warning(f"Skipping tweet {tweet.get('post_id', 'unknown')} - empty text")
                return []
            
            metadata = {
                "source": "twitter",
                "post_id": str(self._get_safe_value(tweet.get("post_id", ""))),
                "sender": self._get_safe_value(tweet.get("user", "")),
                "timestamp": self._get_safe_timestamp(tweet),
                "chat_type": "tweet",
                "retweet_count": int(self._get_safe_value(tweet.get("reposts", 0))),
                "favorite_count": int(self._get_safe_value(tweet.get("likes", 0))),
                "original_text": text  # Store original text in metadata
            }

            # Check text length and chunk if needed
            MAX_TEXT_LENGTH = 10000  # Adjust this threshold as needed
            if len(text) > MAX_TEXT_LENGTH:
                logger.info(f"Text length {len(text)} exceeds {MAX_TEXT_LENGTH}, chunking...")
                return self.chunker.chunk_with_metadata(text, metadata)
            
            # Return single document for short texts
            return [{
                "text": text,
                "metadata": metadata
            }]
        except Exception as e:
            logger.error(f"Error processing tweet {tweet.get('post_id', 'unknown')}: {str(e)}")
            return []

    def process_tweets(self, last_run_time: Optional[str] = None) -> bool:
        """Process tweets since last run time"""
        try:
            # Build query based on last run time
            query = {}
            if last_run_time:
                last_run = datetime.fromisoformat(last_run_time)
                query["post_time"] = {"$gt": last_run}
                logger.info(f"Querying tweets after {last_run_time}")
            else:
                logger.info("Processing all available tweets")

            # Get tweets from MongoDB
            tweets = list(self.tweets_collection.find(query).sort("post_time", 1))
            logger.info(f"Found {len(tweets)} tweets to process")

            if not tweets:
                logger.info("No new tweets to process")
                return False

            # Process each tweet
            processed_count = 0
            for tweet in tweets:
                chunks = self._process_tweet(tweet)
                if chunks:
                    self.vector_store.add_documents(chunks)
                    processed_count += 1

            logger.info(f"Successfully processed {processed_count} tweets")
            return True

        except Exception as e:
            logger.error(f"Error processing tweets: {str(e)}", exc_info=True)
            return False

def process_twitter_data(last_run_time: Optional[str] = None) -> bool:
    """Process Twitter data since last run time and return True if data was processed"""
    try:
        # Initialize processor with MongoDB connection details from environment variables
        processor = TwitterProcessor()
        return processor.process_tweets(last_run_time)
    except Exception as e:
        logger.error(f"Error in process_twitter_data: {str(e)}", exc_info=True)
        return False 