# ImpressoX Client Applications Documentation

The `clients/` directory contains the client applications that provide user interfaces to interact with the ImpressoX AI Agent. Currently, the primary implementation is the Telegram bot, with web and Discord clients planned for future development.

## Client Architecture Overview

```mermaid
graph TD
    subgraph "Client Layer"
        TelegramBot[Telegram Bot]
        WebClient[Web Client (Planned)]
        DiscordClient[Discord Client (Planned)]
    end

    subgraph "Shared Components"
        SessionManager[Session Manager]
        APIClient[Core API Client]
        ConfigManager[Configuration]
    end

    subgraph "ImpressoX Core"
        API[Core API]
        Backend[Backend Services]
    end

    TelegramBot --> SessionManager
    TelegramBot --> APIClient
    WebClient -.-> SessionManager
    WebClient -.-> APIClient
    DiscordClient -.-> SessionManager
    DiscordClient -.-> APIClient

    APIClient --> API
    API --> Backend
    
    SessionManager --> Redis[(Redis)]
```

## Current Implementation: Telegram Bot

### Directory Structure
```
clients/
├── config.py              # Shared configuration
├── session_manager.py     # Session management
└── telegram/
    ├── bot.py            # Main bot application
    ├── handlers/
    │   └── message_handler.py  # Message handling logic
    ├── services/
    │   ├── chat_history.py    # Chat history management
    │   └── core_api.py        # Core API interaction
    └── utils/
        ├── logger.py          # Logging utilities
        ├── permissions.py     # Access control
        └── redis_util.py      # Redis interaction
```

### Key Components

#### 1. Bot Application (`telegram/bot.py`)
-   Implementation using `python-telegram-bot`
-   Command and message handling setup
-   Integration with session management
-   Error handling and logging

#### 2. Message Handler (`telegram/handlers/message_handler.py`)
-   Processes incoming user messages
-   Routes requests to appropriate services
-   Manages conversation state
-   Implements command logic

#### 3. Services
-   **Core API Client** (`services/core_api.py`):
    ```python
    class CoreAPIClient:
        def __init__(self, base_url: str):
            self.base_url = base_url
            
        async def send_message(self, session_id: str, message: str) -> dict:
            # Implementation for sending messages to core API
    ```
-   **Chat History** (`services/chat_history.py`):
    -   Manages conversation history
    -   Integrates with Redis for storage
    -   Handles message pagination

#### 4. Utilities
-   **Logger** (`utils/logger.py`): Structured logging
-   **Permissions** (`utils/permissions.py`): User access control
-   **Redis Utilities** (`utils/redis_util.py`): Redis interactions

## Shared Components

### Session Management (`session_manager.py`)
```python
class SessionManager:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def create_session(self, user_id: str) -> str:
        # Creates new session
        pass

    async def get_session(self, session_id: str) -> dict:
        # Retrieves session data
        pass

    async def update_session(self, session_id: str, data: dict):
        # Updates session state
        pass
```

### Configuration Management (`config.py`)
-   Loads environment variables
-   Manages API endpoints
-   Configures client settings
-   Integration with central config system

## Setup & Deployment

### Telegram Bot Setup
1.  Configure environment:
    ```bash
    cd clients/telegram
    cp .env.example .env
    # Edit .env with your settings:
    # TELEGRAM_BOT_TOKEN=your_bot_token
    # CORE_API_URL=http://localhost:8000
    # REDIS_URL=redis://localhost:6379
    ```

2.  Install dependencies:
    ```bash
    python -m venv venv
    source venv/bin/activate  # or `venv\Scripts\activate` on Windows
    pip install -r requirements.txt
    ```

3.  Run the bot:
    ```bash
    python bot.py
    # Or use the script from project root:
    bash run_tele.sh
    ```

### Docker Deployment
```bash
cd clients/telegram
docker build -t impressox-telegram-bot .
# Or use the build script:
./build.sh
```

## Planned Client Implementations

### Web Client
-   React-based web interface
-   Real-time chat functionality
-   User authentication
-   Profile management
-   Advanced visualization features

### Discord Bot
-   Discord.js implementation
-   Slash command support
-   Role-based permissions
-   Server management features

## Development Guidelines

### Security Considerations
-   Secure storage of bot tokens
-   Input validation and sanitization
-   Rate limiting and flood control
-   User authentication and authorization

### Error Handling
```python
async def handle_message(message: Message):
    try:
        # Process message
        response = await process_message(message)
        await send_response(message.chat_id, response)
    except APIError as e:
        # Handle API errors
        await send_error_message(message.chat_id, "Service temporarily unavailable")
        logger.error(f"API Error: {e}")
    except Exception as e:
        # Handle unexpected errors
        await send_error_message(message.chat_id, "An unexpected error occurred")
        logger.exception(f"Unexpected error: {e}")
```

### Logging Best Practices
-   Log all important events
-   Include relevant context
-   Use appropriate log levels
-   Implement log rotation

### Testing
-   Unit tests for handlers and services
-   Integration tests for API interaction
-   Mock external dependencies
-   Test different conversation flows

## Monitoring & Maintenance

### Health Checks
-   Bot connectivity status
-   API connection health
-   Redis connection status
-   Message processing metrics

### Performance Monitoring
-   Response times
-   Message queue length
-   Error rates
-   Resource usage

### Maintenance Tasks
-   Log rotation
-   Session cleanup
-   Cache management
-   Configuration updates

## Future Enhancements

### Short Term
-   Enhanced error handling
-   Better conversation management
-   More command options
-   Improved logging

### Long Term
-   Web client implementation
-   Discord bot development
-   Multi-language support
-   Advanced analytics
