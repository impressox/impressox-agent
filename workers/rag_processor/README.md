# RAG Processor Worker

This worker implements a semantic-aware chunking and embedding pipeline for processing data from multiple sources (Twitter and Telegram) to support Retrieval-Augmented Generation (RAG).

## Features

- Scheduled data processing every 5 minutes
- Semantic-aware text chunking using sentence splitting and similarity
- Jina Embeddings V3 for high-quality embeddings
- ChromaDB vector store for efficient storage and retrieval
- Support for multiple data sources (Twitter and Telegram)
- Rich metadata tracking for each chunk

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables:
```bash
# Twitter API credentials
export TWITTER_API_KEY="your_api_key"
export TWITTER_API_SECRET="your_api_secret"
export TWITTER_ACCESS_TOKEN="your_access_token"
export TWITTER_ACCESS_TOKEN_SECRET="your_access_token_secret"

# MongoDB connection
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB="telegram_db"

# Jina API key
export JINA_API_KEY="your_jina_api_key"
```

3. Run the worker:
```bash
python scheduler.py
```

## Architecture

- `scheduler.py`: Main scheduler that runs jobs every 5 minutes
- `jobs/`: Source-specific data processors
  - `twitter_job.py`: Twitter data processor
  - `telegram_job.py`: Telegram data processor
- `common/`: Shared utilities
  - `chunker.py`: Semantic-aware text chunker
  - `embedder.py`: Jina embeddings wrapper
  - `vector_store.py`: ChromaDB vector store interface

## Data Flow

1. Scheduler triggers data processing every 5 minutes
2. Each source processor fetches new data since last run
3. Text is split into sentences and embedded
4. Similar sentences are merged into semantic chunks
5. Chunks are embedded and stored in ChromaDB with metadata
6. Last run timestamps are updated

## Usage

The processed data can be queried from ChromaDB using the VectorStore class:

```python
from common.vector_store import VectorStore

store = VectorStore()

# Search across all sources
results = store.search("your query", n_results=5)

# Search specific source
results = store.search(
    "your query",
    where={"source": "twitter"},
    n_results=5
)
```

## Metadata

Each chunk includes the following metadata:
- source: "twitter" or "telegram"
- sender: username/handle of the sender
- timestamp: ISO format timestamp
- chat_type: type of conversation
- post_id/message_id: unique identifier
- Additional source-specific metadata 