from datetime import datetime
from typing import List, Dict, Optional, Any
import os
import logging
import time
from dotenv import load_dotenv
from pymongo import MongoClient
from workers.rag_processor.common.chunker import SemanticChunker
from workers.rag_processor.common.vector_store import VectorStore
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from httpcore import ReadTimeout
import asyncio

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class TwitterProcessor:
    def __init__(self, mongo_uri: str = None, db_name: str = None):
        """Initialize Twitter processor with MongoDB connection"""
        self.client = MongoClient(
            mongo_uri or os.getenv('TWITTER_MONGODB_URI', 'mongodb://localhost:27017'),
            serverSelectionTimeoutMS=5000,  # 5 seconds timeout for server selection
            connectTimeoutMS=5000,  # 5 seconds timeout for connection
            socketTimeoutMS=30000  # 30 seconds timeout for operations
        )
        self.db = self.client[db_name or os.getenv('TWITTER_MONGODB_DB_NAME', 'cpx-data')]
        self.tweets_collection = self.db["tweets"]
        self.airdrop_tweets_collection = self.db["airdrop_tweets"]
        self.chunker = SemanticChunker(language='en')
        self.vector_store = VectorStore()
        self.semaphore = asyncio.Semaphore(5)  # Giới hạn 5 luồng đồng thời
        logger.info("TwitterProcessor initialized")

    def _get_safe_value(self, value: any, default: any = '') -> any:
        """Get safe value from tweet field"""
        return value if value is not None else default

    def _get_safe_timestamp(self, tweet: Dict) -> int:
        """Get safe timestamp as integer Unix timestamp"""
        try:
            post_time = tweet.get("post_time")
            if post_time is None:
                logger.warning(f"Tweet {tweet.get('post_id', 'unknown')} has no post_time, using current time")
                return int(datetime.now().timestamp())
            return int(post_time.timestamp())
        except Exception as e:
            logger.warning(f"Error getting timestamp for tweet {tweet.get('post_id', 'unknown')}: {str(e)}")
            return int(datetime.now().timestamp())
    
    def _get_safe_post_time(self, tweet: Dict) -> str:
        """Get safe post_time from tweet"""
        try:
            post_time = tweet.get("post_time")
            if post_time is None:
                logger.warning(f"Tweet {tweet.get('post_id', 'unknown')} has no post_time, using current time")
                return datetime.now().isoformat()
            return post_time.isoformat()
        except Exception as e:
            logger.warning(f"Error getting timestamp for tweet {tweet.get('post_id', 'unknown')}: {str(e)}")
            return datetime.now().isoformat()

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
                "keyword": self._get_safe_value(tweet.get("keyword", "")),
                "post_id": str(self._get_safe_value(tweet.get("post_id", ""))),
                "post_time": self._get_safe_post_time(tweet),
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

    @retry(
        stop=stop_after_attempt(3),  # Retry 3 times
        wait=wait_exponential(multiplier=1, min=4, max=10),  # Wait between retries
        retry=retry_if_exception_type((ReadTimeout, ConnectionError)),  # Retry on timeout and connection errors
        before_sleep=lambda retry_state: logger.warning(f"Retrying after error. Attempt {retry_state.attempt_number}/3")
    )
    def _add_to_vector_store(self, chunks: List[Dict]) -> None:
        """Add documents to vector store with retry mechanism"""
        self.vector_store.add_documents(chunks)

    async def _process_tweet_with_semaphore(self, tweet: Dict[str, Any]) -> bool:
        """Xử lý một tweet với semaphore để giới hạn số luồng đồng thời"""
        async with self.semaphore:
            try:
                chunks = self._process_tweet(tweet)
                if chunks:
                    self._add_to_vector_store(chunks)
                    return True
            except Exception as e:
                logger.error(f"Error processing tweet {tweet.get('post_id', 'unknown')}: {str(e)}")
            return False

    async def process_tweets(self, last_run_time: Optional[str] = None) -> bool:
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
            tweets = list(self.tweets_collection.find(query).sort("post_time", -1))
            # airdrop_tweets = list(self.airdrop_tweets_collection.find(query).sort("post_time", -1))

            # tweets.extend(airdrop_tweets)
            logger.info(f"Found {len(tweets)} tweets to process")

            if not tweets:
                logger.info("No new tweets to process")
                return False

            # Tạo danh sách các task xử lý tweets
            tasks = [self._process_tweet_with_semaphore(tweet) for tweet in tweets]
            
            # Chạy tất cả các task đồng thời và đợi kết quả
            results = await asyncio.gather(*tasks)
            
            # Đếm số tweet được xử lý thành công
            processed_count = sum(1 for result in results if result)
            
            logger.info(f"Processed {processed_count} tweets successfully")
            return True

        except Exception as e:
            logger.error(f"Error processing tweets: {str(e)}", exc_info=True)
            return False

def process_twitter_data(last_run_time: Optional[str] = None) -> bool:
    """Process Twitter data since last run time and return True if data was processed"""
    try:
        # Initialize processor with MongoDB connection details from environment variables
        processor = TwitterProcessor()
        # Create and run event loop for async execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(processor.process_tweets(last_run_time))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error in process_twitter_data: {str(e)}", exc_info=True)
        return False 