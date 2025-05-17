# ImpressoX Clients Documentation

The `clients/` directory contains applications that allow users to interact with the ImpressoX AI Agent. The goal is to provide multi-platform access through various interfaces.

## Client Architecture Overview

All client applications interact with the core ImpressoX system via a unified API layer, which is then processed by the Backend Service Layer. This ensures consistent behavior and allows for shared session management and business logic.

```mermaid
graph TD
    subgraph "User Interfaces"
        WebClient[Web Application (Planned)]
        TelegramBot[Telegram Bot (Active)]
        DiscordBot[Discord Bot (Planned)]
    end

    subgraph "Interaction Layer"
        APIClient[HTTP API Client Logic]
    end
    
    subgraph "ImpressoX Core"
        APIServer[API Layer (FastAPI)]
        BackendServices[Backend Service Layer]
        AgentCore[Agent Core Logic]
    end

    WebClient --> APIClient
    TelegramBot --> APIClient
    DiscordBot --> APIClient
    APIClient --> APIServer
    APIServer <--> BackendServices
    BackendServices <--> AgentCore

    %% Note: The landing-page is a separate Next.js project for promotional purposes
    %% and is not a direct client for agent interaction in this context.
    %% LandingPage[Landing Page (Next.js)] -.-> Info
```

**Note**: The project also includes a `landing-page` directory which houses a Next.js application for promotional and informational purposes. This is separate from the interactive client applications described here.

## Current Client Implementations

### 1. Telegram Bot (`clients/telegram/`)

The Telegram bot is currently the most developed client interface.

-   **Technology**: Python (`python-telegram-bot` library).
-   **Structure**:
    ```
    clients/telegram/
    ├── handlers/         # Message and command handlers (e.g., message_handler.py)
    ├── services/         # Services interacting with the core API (e.g., core_api.py)
    ├── utils/            # Utility functions
    ├── .env              # Environment variables for the bot (token, API endpoint)
    ├── bot.py            # Main bot application script
    └── requirements.txt  # Python dependencies
    ```
-   **Key Features**:
    -   Handles user messages and commands.
    -   Manages conversation sessions with users.
    -   Interacts with the ImpressoX core API to send requests and receive responses.
    -   Supports streaming responses for a more interactive experience.
    -   Session management is handled by `clients/session_manager.py` which can be shared across different bot clients.
-   **Setup & Running**:
    1.  Navigate to `clients/telegram/`.
    2.  Create a virtual environment: `python -m venv venv`
    3.  Activate it: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows).
    4.  Install dependencies: `pip install -r requirements.txt`.
    5.  Configure `.env` with your `TELEGRAM_BOT_TOKEN` and `CORE_API_URL`.
    6.  Run the bot: `python bot.py` (or use `run_tele.sh` from the project root).

### 2. Web Application (Planned, `clients/web/`)

A React-based web interface is planned for a rich, interactive chat experience.

-   **Technology**: React (planned).
-   **Structure (Anticipated)**:
    ```
    clients/web/
    ├── src/
    │   ├── components/    # React components
    │   ├── hooks/         # Custom React hooks
    │   ├── services/      # API interaction services
    │   ├── contexts/      # React contexts for state management
    │   └── utils/         # Utility functions
    ├── public/            # Static assets
    └── package.json
    ```
-   **Planned Features**:
    -   Real-time chat interface.
    -   Support for streaming responses from the agent.
    -   Markdown rendering and code highlighting for rich content display.
    -   User authentication and session management.

### 3. Discord Bot (Planned, `clients/discord/`)

A Discord bot is planned to extend ImpressoX accessibility to Discord communities.

-   **Technology**: Node.js (`discord.js` library planned).
-   **Structure (Anticipated)**:
    ```
    clients/discord/
    ├── commands/        # Slash command handlers
    ├── events/          # Discord event handlers
    ├── services/        # Services for API interaction
    └── utils/           # Utility functions
    ```
-   **Planned Features**:
    -   Slash command integration.
    -   Conversation threading.
    -   Role-based access control.
    -   Rich embed support for displaying information.

## Common Client-Side Components & Considerations

### Session Management (`clients/session_manager.py`)
-   A shared `SessionManager` class is available for Python-based clients (like the Telegram bot).
-   It handles creating unique session IDs for conversations.
-   Manages session state, history, and context, often interacting with Redis via the core API or backend services for persistence.

### API Interaction
-   All clients communicate with the ImpressoX agent via the core API endpoints (e.g., `/threads/{session_id}/runs/stream`).
-   Clients need to handle HTTP requests, manage API tokens (if authentication is implemented), and process responses (including streaming data).
-   The `clients/telegram/services/core_api.py` provides an example of how a client can interact with the core API.

### Authentication & Authorization (Planned)
-   Future development will include robust authentication mechanisms (e.g., OAuth2 for web clients).
-   Role-based access control might be implemented to manage feature access.

### Message Processing
-   Input validation should be performed client-side where appropriate, with further validation server-side.
-   Clients should handle potential rate limiting from the API.
-   Error handling is crucial for a good user experience; clients should display user-friendly error messages.

## Development Best Practices for Clients

-   **Error Handling**: Implement comprehensive error handling and provide clear feedback to the user. Log errors for debugging.
-   **Performance**: Optimize client performance, especially for web clients (e.g., lazy loading, efficient state management). For bots, ensure quick response times.
-   **Security**:
    -   Sanitize user inputs before sending them to the API.
    -   Securely store any client-specific tokens or credentials.
    -   Be mindful of platform-specific security guidelines (e.g., for Telegram or Discord bots).
-   **User Experience (UX)**:
    -   Provide clear loading states and feedback during API calls.
    -   Ensure intuitive navigation and interaction flows.
    -   Maintain consistency in how information is presented across different clients.
-   **Testing**:
    -   Unit test individual components and utility functions.
    -   Integration test interactions with the core API.
    -   Perform end-to-end testing to simulate user scenarios.

## Future Development

-   Full implementation of the Web and Discord clients.
-   Standardized authentication and authorization across all clients.
-   Enhanced UI/UX features based on user feedback.
-   Client-side caching strategies to improve perceived performance.
