from datetime import datetime
from typing import List, Dict, Optional
import tweepy
from ..common.chunker import SemanticChunker
from ..common.vector_store import VectorStore

class TwitterProcessor:
    def __init__(self, api_key: str, api_secret: str, access_token: str, access_token_secret: str):
        """Initialize Twitter API client"""
        auth = tweepy.OAuthHandler(api_key, api_secret)
        auth.set_access_token(access_token, access_token_secret)
        self.api = tweepy.API(auth)
        self.chunker = SemanticChunker()
        self.vector_store = VectorStore()

    def _get_tweet_text(self, tweet) -> str:
        """Extract full text from tweet"""
        if hasattr(tweet, 'full_text'):
            return tweet.full_text
        return tweet.text

    def _process_tweet(self, tweet) -> Dict:
        """Process a single tweet into chunks with metadata"""
        text = self._get_tweet_text(tweet)
        
        metadata = {
            "source": "twitter",
            "post_id": str(tweet.id),
            "sender": tweet.user.screen_name,
            "timestamp": tweet.created_at.isoformat(),
            "chat_type": "tweet",
            "retweet_count": tweet.retweet_count,
            "favorite_count": tweet.favorite_count
        }

        return self.chunker.chunk_with_metadata(text, metadata)

    def process_tweets(self, last_run: Optional[str] = None) -> bool:
        """Process new tweets since last run"""
        try:
            # Get timeline tweets
            tweets = self.api.home_timeline(
                count=100,
                tweet_mode='extended',
                since_id=last_run if last_run else None
            )

            if not tweets:
                return False

            # Process each tweet
            for tweet in tweets:
                chunks = self._process_tweet(tweet)
                if chunks:
                    self.vector_store.add_documents(chunks)

            return True

        except Exception as e:
            print(f"Error processing tweets: {str(e)}")
            return False

def process_twitter_data(last_run: Optional[str] = None) -> bool:
    """Process Twitter data and return True if new data was processed"""
    # Initialize processor with Twitter API credentials
    processor = TwitterProcessor(
        api_key="YOUR_API_KEY",
        api_secret="YOUR_API_SECRET",
        access_token="YOUR_ACCESS_TOKEN",
        access_token_secret="YOUR_ACCESS_TOKEN_SECRET"
    )
    
    return processor.process_tweets(last_run) 