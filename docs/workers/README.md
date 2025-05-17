# ImpressoX Workers Documentation

The `workers/` directory contains various background worker processes that handle automated tasks, data processing, and event-driven actions for the ImpressoX AI Agent.

## Worker Architecture Overview

ImpressoX workers operate independently but are coordinated with the core application, often through the Backend Service Layer, message queues (like Redis Streams or a dedicated task queue), and shared data stores (Redis, MongoDB).

```mermaid
graph TD
    subgraph "ImpressoX Core System"
        APIServer[API Layer]
        BackendServices[Backend Service Layer]
        AgentCore[Agent Core Logic]
        Databases[Databases - Redis, MongoDB]
    end

    subgraph "Worker Subsystem (workers/)"
        MarketMonitor[Market Monitor Worker]
        XScraper[X-Scraper Worker]
        NotifyWorker[Notify Worker]
        RAGProcessor[RAG Processor (Planned)]
        ScheduledTasks[Scheduled Tasks (General Framework)]
        EventListeners[Event Listeners (General Framework)]
    end
    
    subgraph "External Services & Data Sources"
        BlockchainData[Blockchain Data Providers]
        SocialMedia[Social Media Platforms - X/Twitter]
        PriceFeeds[Price Data Feeds]
        NotificationChannels[Notification Channels - Telegram, Email, etc.]
    end

    BackendServices <--> Databases
    BackendServices <--> AgentCore
    
    MarketMonitor <--> PriceFeeds
    MarketMonitor <--> Databases % For rules and price data
    MarketMonitor --> BackendServices % To trigger notifications or actions

    XScraper <--> SocialMedia
    XScraper --> Databases % To store scraped data (MongoDB)

    NotifyWorker <--> BackendServices % Receives notification requests
    NotifyWorker <--> NotificationChannels % Dispatches notifications

    RAGProcessor <--> Databases % For vector store (ChromaDB) and source data
    RAGProcessor <--> AgentCore % Provides context for LLM

    ScheduledTasks --> BackendServices
    EventListeners --> BackendServices
```

## Implemented Workers

### 1. Market Monitor Worker (`workers/market-monitor/`)

-   **Purpose**: Monitors cryptocurrency market prices and triggers alerts or actions based on predefined rules.
-   **Technology**: Python, Redis (for rule storage and price caching), MongoDB (for persistent data if needed).
-   **Key Components**:
    -   `monitor.py`: Main script to run the worker.
    -   `watchers/token_watcher.py`: Watches token prices from various sources.
    -   `processors/rule_processor.py`: Processes incoming price data against stored rules.
    -   `processors/rule_matcher.py`: Matches rules with current market conditions.
    -   `processors/notify_dispatcher.py`: Dispatches notifications when rules are triggered.
    -   `shared/redis_utils.py`: Utilities for Redis interaction (rule storage, price streams).
    -   `shared/models.py`: Data models for rules, prices, etc.
-   **Functionality**:
    -   Users can define rules (e.g., "alert if BTC price > $70,000") via an API (interfaced by `app/tools/general/watch_market.py`).
    -   Rules are stored in Redis.
    -   The worker continuously fetches price data.
    -   Matches current prices against rules and triggers notifications through the Notify Worker or directly.
-   **Setup & Running**:
    1.  Navigate to `workers/market-monitor/`.
    2.  Create and activate a Python virtual environment.
    3.  Install dependencies: `pip install -r requirements.txt`.
    4.  Configure `.env` with Redis, MongoDB connection details, and any API keys for price feeds.
    5.  Run the worker: `python monitor.py` (or use `run_monitor.sh` from the project root).

### 2. X-Scraper Worker (`workers/x-scraper/`)

-   **Purpose**: Scrapes data (tweets, user profiles) from X (formerly Twitter) for trend analysis and social signal processing.
-   **Technology**: Node.js, Puppeteer (for browser automation).
-   **Key Components**:
    -   `index.js`: Main application script.
    -   `utils/login.js`: Handles X login.
    -   `utils/proxyManager.js`: Manages proxies for scraping.
    -   `utils/mongo.js`: MongoDB interaction for storing scraped data.
    -   `Dockerfile` & `docker-compose.yml`: For containerized deployment.
-   **Functionality**:
    -   Logs into X using provided accounts.
    -   Scrapes tweets from a list of specified users or based on search queries.
    -   Stores scraped data in MongoDB.
    -   Handles rate limiting and proxy rotation to avoid detection.
-   **Setup & Running**:
    1.  Navigate to `workers/x-scraper/`.
    2.  Install Node.js dependencies: `npm install`.
    3.  Configure `.env` with X account credentials, MongoDB URI, and proxy settings.
    4.  Provide X accounts in `accounts/x-accounts.txt` and target users in `user_list.txt`.
    5.  Run the scraper: `node index.js` or using Docker: `docker-compose up --build`.
    (Refer to `workers/x-scraper/README.md` if available for more detailed instructions).

### 3. Notify Worker (Conceptual, integrated within Market Monitor or as a separate service)

-   **Purpose**: Handles the dispatch of notifications to users through various channels (Telegram, email, web push, etc.).
-   **Technology**: Python (can be part of other workers or a standalone FastAPI/Celery service).
-   **Functionality**:
    -   Receives notification requests from other components (e.g., Market Monitor, Agent Core).
    -   Formats messages for specific channels.
    -   Manages user notification preferences.
    -   Handles retries and error reporting for notification delivery.
-   **Current Implementation**: The `workers/market-monitor/processors/notify_dispatcher.py` handles some of this logic for market alerts, primarily targeting Telegram. A more generalized Notify Worker is a future enhancement.
-   **Setup & Running**: If part of Market Monitor, it runs with it. A standalone worker would have its own setup (e.g., `run_notify_worker.sh`).

## Planned Workers

### RAG Processor
-   **Purpose**: To process and embed documents into a vector store (e.g., ChromaDB) for Retrieval Augmented Generation (RAG) with the LLM.
-   **Functionality**:
    -   Ingests data from various sources (text files, web pages, database records).
    -   Chunks and embeds the data.
    -   Stores embeddings in ChromaDB.
    -   Provides an interface for the Agent Core to retrieve relevant context.

### General Scheduled Task Worker
-   **Purpose**: A framework for running various scheduled tasks (e.g., daily data cleanup, report generation).
-   **Technology**: Python with libraries like APScheduler or Celery Beat.

### General Event Listener Worker
-   **Purpose**: A framework for listening to and processing events from message queues or other event sources.
-   **Technology**: Python with libraries for message queue interaction (e.g., Redis-py for Redis Streams, Pika for RabbitMQ).

## Worker Management & Best Practices

### Configuration
-   Workers should be configurable via environment variables and/or YAML files (e.g., `workers/market-monitor/.env`, `workers/x-scraper/.env`).
-   Centralized configuration management (e.g., in `/configs/`) can be used for shared settings.

### Logging & Monitoring
-   Implement comprehensive logging for all worker activities, errors, and important events.
-   Integrate with a monitoring system (e.g., ELK Stack, Prometheus/Grafana) to track worker health, performance, and queue lengths.
-   Langfuse can be used for tracing if workers involve LLM calls.

### Error Handling & Resilience
-   **Retry Mechanisms**: Implement retry logic (e.g., exponential backoff) for transient errors when interacting with external services or databases.
-   **Dead Letter Queues (DLQs)**: For message-driven workers, use DLQs to handle messages that repeatedly fail processing.
-   **Idempotency**: Design tasks to be idempotent where possible, so running them multiple times has the same effect as running them once.
-   **Graceful Shutdown**: Ensure workers can shut down gracefully, finishing current tasks or saving state if possible.

### Deployment
-   **Containerization**: Use Docker for consistent deployment environments (Dockerfiles are provided for X-Scraper and Market Monitor).
-   **Process Management**: Use a process manager (e.g., Supervisor, systemd) or container orchestrator (e.g., Docker Compose, Kubernetes) to keep workers running.
-   **Scalability**: Design workers to be scalable, potentially by running multiple instances that consume tasks from a shared queue.

### Security
-   Securely manage API keys, database credentials, and other secrets used by workers (e.g., using environment variables, HashiCorp Vault).
-   If workers expose any APIs, secure them appropriately.
-   Be mindful of rate limits and terms of service when interacting with external APIs (especially for scrapers).
