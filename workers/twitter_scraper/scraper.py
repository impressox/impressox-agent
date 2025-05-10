import os
import json
import time
import asyncio
import signal
import schedule
import requests
import sys
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv
from twscrape import API, gather
from twscrape.logger import set_log_level

# Load environment variables
load_dotenv()

# MongoDB configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://cpxdb:cpxDbUser1@185.192.97.148:4200/cpx-data?authSource=admin')
client = MongoClient(MONGO_URI)
db_name = os.getenv('DB_NAME', 'cpx-data')
db = client[db_name]
db_collection = os.getenv('DB_COLLECTION', 'tweets')
tweets_collection = db[db_collection]

# Directory configuration
BASE_DIR = os.path.dirname(__file__)
CONFIG_DIR = os.path.join(BASE_DIR, 'config')

# Ensure directories exist
os.makedirs(CONFIG_DIR, exist_ok=True)

# File paths
PROXY_API_URL = os.getenv("PROXY_API_URL", "https://proxyxoay.org/api/get.php?key=WQFISlkMuFcCNPSEsmjIyX&&nhamang=random&&tinhthanh=0")
PROXY_CACHE_FILE = os.path.join(CONFIG_DIR, "proxy.txt")
ACCOUNTS_FILE = os.path.join(CONFIG_DIR, "accounts.txt")
USERS_FILE = os.path.join(CONFIG_DIR, "users.txt")

# Proxy configuration
USE_PROXY = os.getenv('USE_PROXY', 'true').lower() == 'true'

# Set logging level
set_log_level("ERROR")

class ProxyManager:
    def __init__(self):
        self.current_proxy = None
        self.expiry_time = 0
        self.last_check_time = 0
        self.check_interval = 30  # Check proxy every 30 seconds
        if USE_PROXY:
            self.load_cached_proxy()
            print("Proxy is enabled")
        else:
            print("Proxy is disabled")

    def load_cached_proxy(self):
        if not USE_PROXY:
            return
            
        try:
            if os.path.exists(PROXY_CACHE_FILE):
                with open(PROXY_CACHE_FILE, 'r') as f:
                    data = json.load(f)
                    if data['expiry_time'] > time.time():
                        self.current_proxy = data['proxy']
                        self.expiry_time = data['expiry_time']
                        print(f"Loaded cached proxy, expires in {int(self.expiry_time - time.time())} seconds")
                    else:
                        print("Cached proxy expired")
                        self.current_proxy = None
        except Exception as e:
            print(f"Error loading cached proxy: {e}")
            self.current_proxy = None

    def save_proxy_cache(self, proxy_data):
        if not USE_PROXY:
            return
            
        try:
            with open(PROXY_CACHE_FILE, 'w') as f:
                json.dump(proxy_data, f)
        except Exception as e:
            print(f"Error saving proxy cache: {e}")

    def should_update_proxy(self):
        """Check if proxy needs to be updated"""
        if not USE_PROXY:
            return False
            
        current_time = time.time()
        
        # Check if we need to update based on time interval
        if current_time - self.last_check_time < self.check_interval:
            return False
            
        # Check if proxy is expired or about to expire (within 30 seconds)
        if not self.current_proxy or current_time >= self.expiry_time - 30:
            return True
            
        return False

    def get_proxy(self):
        """Get current proxy or fetch new one if needed"""
        if not USE_PROXY:
            return None
            
        if self.should_update_proxy():
            try:
                print("Fetching new proxy...")
                response = requests.get(PROXY_API_URL, timeout=10)
                data = response.json()
                
                if data['status'] == 100:
                    # Extract expiry time from message (format: "proxy nay se die sau Xs")
                    expiry_seconds = int(data['message'].split('sau')[1].split('s')[0].strip())
                    self.expiry_time = time.time() + expiry_seconds
                    self.current_proxy = data['proxyhttp']
                    self.last_check_time = time.time()
                    
                    # Cache the proxy
                    self.save_proxy_cache({
                        'proxy': self.current_proxy,
                        'expiry_time': self.expiry_time
                    })
                    
                    print(f"Got new proxy, expires in {expiry_seconds} seconds")
                    return self.current_proxy
                else:
                    print(f"Error response from proxy API: {data}")
                    return None
            except requests.exceptions.Timeout:
                print("Timeout while fetching proxy")
                return None
            except Exception as e:
                print(f"Error fetching proxy: {e}")
                return None
        
        return self.current_proxy

class TwitterScraper:
    def __init__(self):
        print("Initializing TwitterScraper...")
        self.proxy_manager = ProxyManager()
        print("ProxyManager initialized")
        
        self.tweet_limit = 200
        self.retry_count = 3
        self.retry_delay = 5
        self.running = True
        self.current_task = None
        self.max_concurrent_users = 5  # Số lượng user tối đa chạy đồng thời
        
        # Create event loop
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
        print("Initializing twscrape API...")
        # Get initial proxy
        proxy = self.proxy_manager.get_proxy()
        if proxy:
            try:
                host, port, proxy_user, proxy_pass = proxy.split(':')
                proxy_url = f"http://{proxy_user}:{proxy_pass}@{host}:{port}"
                self.api = API(proxy=proxy_url)
                print(f"API initialized with proxy: {proxy_url}")
            except Exception as e:
                print(f"Error setting proxy: {e}")
                self.api = API()
                print("API initialized without proxy")
        else:
            self.api = API()
            print("API initialized without proxy")
        
        print("Setting up accounts...")
        self.setup_accounts()
        print("Accounts setup completed")
        
        print("Logging in accounts...")
        self.loop.run_until_complete(self.login_accounts())
        print("Account login completed")

    def update_proxy(self):
        """Update proxy configuration for the API"""
        if not USE_PROXY:
            return True
            
        proxy = self.proxy_manager.get_proxy()
        if proxy:
            try:
                host, port, proxy_user, proxy_pass = proxy.split(':')
                proxy_url = f"http://{proxy_user}:{proxy_pass}@{host}:{port}"
                # Create new API instance with new proxy
                self.api = API(proxy=proxy_url)
                print(f"Updated API with new proxy: {proxy_url}")
                return True
            except Exception as e:
                print(f"Error setting proxy: {e}")
                return False
        else:
            print("No proxy available")
            return False

    def stop(self):
        """Stop the scraper"""
        print("\nStopping scraper...")
        self.running = False
        if self.current_task and not self.current_task.done():
            print("Cancelling current task...")
            self.current_task.cancel()
        if self.loop.is_running():
            self.loop.stop()
        print("Scraper stopped")

    def setup_accounts(self):
        """Setup Twitter accounts for scraping"""
        if not os.path.exists(ACCOUNTS_FILE):
            print(f"Please create {ACCOUNTS_FILE} with Twitter accounts in format: username:password:email:email_password:2fa_code")
            return

        print(f"Reading accounts from {ACCOUNTS_FILE}...")
        with open(ACCOUNTS_FILE, 'r') as f:
            for line_num, line in enumerate(f, 1):
                if line.strip() and not line.startswith('#'):
                    try:
                        # Try both ':' and '|' as separators
                        if '|' in line:
                            parts = line.strip().split('|')
                        else:
                            parts = line.strip().split(':')
                            
                        if len(parts) != 5:
                            print(f"Invalid account format at line {line_num}. Expected username:password:email:email_password:2fa_code or username|password|email|email_password|2fa_code, got: {line.strip()}")
                            continue
                            
                        username, password, code, email, email_password = parts
                        print(f"Adding account: {username}")
                        asyncio.run(self.api.pool.add_account(username, password, email, email_password, mfa_code=code))
                        print(f"Successfully added account: {username}")
                    except Exception as e:
                        print(f"Error adding account at line {line_num}: {str(e)}")
                        import traceback
                        print(f"Error details: {traceback.format_exc()}")

    async def login_accounts(self):
        """Login all accounts in the pool"""
        print("\nLogging in accounts...")
        try:
            # Login all accounts at once
            print("Attempting to login all accounts...")
            await self.api.pool.login_all()
            print("Successfully logged in all accounts")
            
            # Verify login status
            print("Verifying login status...")
            accounts = await self.api.pool.accounts_info()
            for acc in accounts:
                print(f"Account: {acc['username']}")
                print(f"Active: {acc['active']}")
                print(f"Login: {acc['logged_in']}")
                print(f"Last used: {acc['last_used']}")
                print("---")
        except Exception as e:
            print(f"Error during login process: {e}")
            import traceback
            print(f"Error details: {traceback.format_exc()}")
            # Try to get more detailed error information
            try:
                accounts = await self.api.pool.accounts_info()
                print("\nCurrent account status:")
                for acc in accounts:
                    print(f"Account: {acc['username']}")
                    print(f"Active: {acc['active']}")
                    print(f"Login: {acc['logged_in']}")
                    print(f"Last used: {acc['last_used']}")
                    print("---")
            except Exception as e2:
                print(f"Error getting account status: {e2}")

    async def check_account_status(self):
        """Check if accounts are properly authenticated"""
        try:
            # Get all accounts in pool
            accounts = await self.api.pool.accounts_info()
            print("\nAccount Status:")
            active_accounts = 0
            for acc in accounts:
                print(f"Username: {acc['username']}")
                print(f"Active: {acc['active']}")
                print(f"Login: {acc['logged_in']}")
                print(f"Last used: {acc['last_used']}")
                print(f"Total requests: {acc.get('total_req', 'N/A')}")
                print(f"Errors: {acc.get('error_msg', 'N/A')}")
                print("---")
                if acc['active'] and acc['logged_in']:
                    active_accounts += 1
            
            if active_accounts == 0:
                print("No active accounts found, attempting to relogin...")
                await self.login_accounts()
            else:
                print(f"Found {active_accounts} active accounts")
                
        except Exception as e:
            print(f"Error checking account status: {e}")
            import traceback
            print(f"Error details: {traceback.format_exc()}")
            # Try to get basic account info even if detailed info fails
            try:
                accounts = await self.api.pool.accounts_info()
                print("\nBasic Account Status:")
                for acc in accounts:
                    print(f"Username: {acc['username']}")
                    print(f"Active: {acc['active']}")
                    print(f"Login: {acc['logged_in']}")
                    print("---")
            except Exception as e2:
                print(f"Error getting basic account info: {e2}")

    async def get_tweets(self, username):
        """Get tweets for a user using twscrape"""
        try:
            # Update proxy before making requests
            if not self.update_proxy():
                print(f"Failed to update proxy for {username}, retrying...")
                return []
            
            # Check account status first with timeout
            try:
                async with asyncio.timeout(30):  # 30 seconds timeout
                    await self.check_account_status()
            except asyncio.TimeoutError:
                print("Timeout while checking account status")
                return []
            
            print(f"\nTrying to find user: {username}")
            # Search for the target user
            try:
                # Get current account info before search
                accounts = await self.api.pool.accounts_info()
                current_account = next((acc for acc in accounts if acc['active']), None)
                if current_account:
                    print(f"Using account: {current_account['username']}")
                
                users = await gather(self.api.search_user(username))
                
                # Get account info after search to check if it switched
                accounts_after = await self.api.pool.accounts_info()
                current_account_after = next((acc for acc in accounts_after if acc['active']), None)
                if current_account_after and current_account and current_account_after['username'] != current_account['username']:
                    print(f"Account switched from {current_account['username']} to {current_account_after['username']}")
                
                if not users:
                    print(f"Could not find user: {username}")
                    return []
                    
                target_user = users[0]
                print(f"Found target user: {target_user.username} (ID: {target_user.id})")
            except Exception as e:
                print(f"Error searching for user {username}: {e}")
                import traceback
                print(f"Error details: {traceback.format_exc()}")
                # Force proxy update on error
                self.proxy_manager.current_proxy = None
                return []
            
            # Get tweets using user_id with timeout
            tweets = []
            last_proxy_check = time.time()
            proxy_check_interval = 30  # Check proxy every 30 seconds during tweet fetching
            
            try:
                async with asyncio.timeout(60):  # 60 seconds timeout for getting tweets
                    # Get current account info before fetching tweets
                    accounts = await self.api.pool.accounts_info()
                    current_account = next((acc for acc in accounts if acc['active']), None)
                    if current_account:
                        print(f"Using account for tweets: {current_account['username']}")
                    
                    async for tweet in self.api.user_tweets(target_user.id, limit=self.tweet_limit):
                        if not self.running:  # Check if we should stop
                            print("Received stop signal, stopping tweet collection")
                            break
                            
                        # Check and update proxy if needed
                        current_time = time.time()
                        if current_time - last_proxy_check >= proxy_check_interval:
                            print(f"[{username}] Checking proxy status...")
                            if self.proxy_manager.should_update_proxy():
                                print(f"[{username}] Updating proxy during tweet fetching...")
                                if not self.update_proxy():
                                    print(f"[{username}] Failed to update proxy, stopping tweet collection")
                                    break
                            last_proxy_check = current_time
                            
                        # Print raw tweet data for debugging
                        print(f"[{username}] Raw tweet data: {tweet.id_str}")
                        
                        tweet_data = {
                            'user': username,
                            'post_id': tweet.id,
                            'post_link': f"https://twitter.com/{username}/status/{tweet.id}",
                            'text': tweet.rawContent,
                            'post_time': tweet.date,
                            'likes': tweet.likeCount,
                            'total_comments': tweet.replyCount,
                            'reposts': tweet.retweetCount,
                            'quotes': tweet.quoteCount,
                            'comments': []
                        }
                        tweets.append(tweet_data)
                        print(f"Processed tweet: {tweet_data['post_id']} - {tweet_data['text'][:100]}...")
                    
                    # Get account info after fetching tweets to check if it switched
                    accounts_after = await self.api.pool.accounts_info()
                    current_account_after = next((acc for acc in accounts_after if acc['active']), None)
                    if current_account_after and current_account and current_account_after['username'] != current_account['username']:
                        print(f"Account switched from {current_account['username']} to {current_account_after['username']} during tweet fetching")
                        
            except asyncio.TimeoutError:
                print("Timeout while getting tweets")
            except Exception as e:
                print(f"Error while getting tweets: {e}")
                import traceback
                print(f"Error details: {traceback.format_exc()}")
                # Force proxy update on error
                self.proxy_manager.current_proxy = None
                
            return tweets
        except Exception as e:
            print(f"Error getting tweets: {e}")
            import traceback
            print(f"Error details: {traceback.format_exc()}")
            # Force proxy update on error
            self.proxy_manager.current_proxy = None
            return []

    async def process_user_tweets(self, username):
        """Process tweets for a single user"""
        for attempt in range(self.retry_count):
            if not self.running:
                print(f"Received stop signal, stopping processing for {username}")
                return
                
            try:
                print(f"Attempt {attempt + 1}/{self.retry_count} for {username}")
                # Update proxy before each attempt
                self.update_proxy()
                
                # Get tweets using asyncio with timeout
                try:
                    tweets = await asyncio.wait_for(self.get_tweets(username), timeout=120)
                except asyncio.TimeoutError:
                    print(f"Timeout while scraping tweets for {username}")
                    continue
                except Exception as e:
                    print(f"Error in get_tweets for {username}: {e}")
                    continue

                # Save to MongoDB
                if tweets:
                    for tweet in tweets:
                        if not self.running:
                            print(f"Received stop signal, stopping save to MongoDB for {username}")
                            return
                            
                        try:
                            result = tweets_collection.update_one(
                                {'post_id': tweet['post_id']},
                                {'$set': tweet},
                                upsert=True
                            )
                            if result.upserted_id:
                                print(f"[{username}] Inserted new tweet: {tweet['post_id']}")
                            elif result.modified_count > 0:
                                print(f"[{username}] Updated existing tweet: {tweet['post_id']}")
                        except Exception as e:
                            print(f"[{username}] Error saving tweet {tweet['post_id']} to MongoDB: {e}")
                            continue
                            
                    print(f"Saved {len(tweets)} tweets for user {username}")
                    return  # Success, exit the retry loop
                else:
                    print(f"No tweets found for user {username}")
                    return

            except Exception as e:
                print(f"Attempt {attempt + 1}/{self.retry_count} failed for {username}: {e}")
                if attempt < self.retry_count - 1:
                    print(f"Retrying in {self.retry_delay} seconds...")
                    await asyncio.sleep(self.retry_delay)
                    # Force proxy update on retry
                    self.proxy_manager.current_proxy = None
                else:
                    print(f"All attempts failed for {username}")

    async def process_users_batch(self, usernames):
        """Process a batch of users concurrently"""
        tasks = []
        for username in usernames:
            if not self.running:
                break
            task = asyncio.create_task(self.process_user_tweets(username))
            tasks.append(task)
        
        if tasks:
            await asyncio.gather(*tasks)

    def scrape_user_tweets(self, usernames):
        """Scrape tweets for multiple users concurrently"""
        if not self.running:
            return

        # Process users in batches to control concurrency
        for i in range(0, len(usernames), self.max_concurrent_users):
            if not self.running:
                break
                
            batch = usernames[i:i + self.max_concurrent_users]
            print(f"\nProcessing batch of {len(batch)} users...")
            
            # Run the batch processing using the same event loop
            self.loop.run_until_complete(self.process_users_batch(batch))
            
            if not self.running:
                break
                
            # Add a small delay between batches
            time.sleep(2)

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    print(f"\nReceived signal {signum}")
    if 'scraper' in globals():
        scraper.stop()
    sys.exit(0)

# Register signal handlers
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    global scraper
    print("Starting Twitter scraper...")
    try:
        scraper = TwitterScraper()
        print("TwitterScraper initialized successfully")
    except Exception as e:
        print(f"Error initializing TwitterScraper: {e}")
        import traceback
        print(f"Error details: {traceback.format_exc()}")
        return
    
    def job():
        if not scraper.running:
            return
            
        try:
            print("\nStarting new scraping job...")
            if not os.path.exists(USERS_FILE):
                print(f"Please create {USERS_FILE} with Twitter usernames to scrape")
                return
                
            with open(USERS_FILE, 'r') as f:
                usernames = [line.strip() for line in f if line.strip()]
            
            print(f"Found {len(usernames)} users to process")
            scraper.scrape_user_tweets(usernames)
                
            print("Job completed successfully")
        except Exception as e:
            print(f"Error in job: {e}")
            import traceback
            print(f"Error details: {traceback.format_exc()}")

    # Schedule the job to run every 5 minutes
    schedule.every(5).minutes.do(job)
    
    print("Twitter scraper is running. Press Ctrl+C to stop.")
    print("First job will start immediately...")
    
    # Run immediately on start
    job()
    
    # Keep the script running
    while scraper.running:
        try:
            schedule.run_pending()
            time.sleep(1)
        except KeyboardInterrupt:
            print("\nReceived keyboard interrupt. Shutting down...")
            scraper.stop()
            break
        except Exception as e:
            print(f"Error in main loop: {e}")
            import traceback
            print(f"Error details: {traceback.format_exc()}")
            time.sleep(5)  # Wait before retrying
    
    # Cleanup before exit
    print("\nCleaning up resources...")
    try:
        # Close MongoDB connection
        client.close()
        print("MongoDB connection closed")
        
        # Close any open files
        if os.path.exists(PROXY_CACHE_FILE):
            os.remove(PROXY_CACHE_FILE)
            print("Proxy cache cleared")
            
        print("Cleanup completed. Goodbye!")
    except Exception as e:
        print(f"Error during cleanup: {e}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nReceived keyboard interrupt. Shutting down...")
        if 'scraper' in globals():
            scraper.stop()
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        print(f"Error details: {traceback.format_exc()}")
    finally:
        # Ensure cleanup happens even if there's an error
        if 'client' in locals():
            client.close()
        print("Script terminated.") 