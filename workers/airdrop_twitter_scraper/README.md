# Twitter Scraper Worker

This worker periodically scrapes tweets from a list of Twitter users using snscrape with rotating proxies.

## Features

- Scrapes tweets every 5 minutes
- Uses rotating proxies from proxyxoay.org
- Caches proxy information to avoid unnecessary API calls
- Stores data in MongoDB with the specified schema
- Handles tweet comments and engagement metrics
- Configurable tweet limit (default: 200 tweets per user)

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
Create a `.env` file with:
```
MONGO_URI=mongodb://cpxdb:cpxDbUser1@185.192.97.148:4200/cpx-data?authSource=admin
```

3. Configure users:
Edit `users.txt` to add the Twitter usernames you want to scrape (one per line)

## Usage

Run the scraper:
```bash
python twitter_scraper.py
```

The script will:
- Run immediately on start
- Continue running and scrape every 5 minutes
- Use cached proxy if available and not expired
- Fetch new proxy when needed
- Save tweets to MongoDB collection 'tweets'

## Data Schema

Tweets are stored in MongoDB with the following schema:
```json
{
    "user": String,
    "post_id": Number,
    "post_link": String,
    "text": String,
    "post_time": Date,
    "likes": Number,
    "total_comments": Number,
    "reposts": Number,
    "quotes": Number,
    "comments": [
        {
            "comment_id": Number,
            "original_comment_id": String,
            "user": String,
            "text": String,
            "timestamp": Date,
            "likes": Number,
            "reposts": Number,
            "quotes": Number
        }
    ]
}
``` 