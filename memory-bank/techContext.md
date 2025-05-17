# Tech Context: Impressox Agent

## Technologies Used

### Core Components
- **Python**: Core application, API server (FastAPI), backend service layer, bots, workers
- **Backend service layer**: Python (FastAPI or separate module), can integrate other services (REST, gRPC, WebSocket) to handle business logic, data retrieval, and external system integration
- **FastAPI**: Async API layer for core app
- **React**: Web client interface
- **Solidity**: Smart contract development

### Storage & Caching
- **Redis**: Caching, checkpointing, and rule storage
- **MongoDB**: Persistent data storage
- **ChromaDB**: Vector store for embeddings

### Configuration & DevOps
- **YAML/ENV**: Configuration management
- **Docker**: Container deployment and local development
- **ELK Stack**: Logging and monitoring

### Development Tools
- **Hardhat**: Smart contract deployment/testing
- **Node.js/NPM**: Web, Discord client, and X-scraper
- **pytest**: Python testing
- **Chai/Mocha**: Contract and JS client testing
- **Langfuse**: LLM observability

## Development Setup

### Core Requirements
- Python 3.9+ and pip for backend service layer, core app, bots, and workers
- Backend service layer can run independently or with the core app, configured via YAML/ENV
- Node.js 16+ and npm for web/discord clients, contracts, and X-scraper
- Redis server for caching and rule storage
- MongoDB for persistent storage
- ChromaDB for vector storage
- Environment config via `.env` and YAML files

### Environment Variables
- API keys and endpoints
- Database connections
- Worker configurations
- LLM settings
- Blockchain networks

### Local Development
- Virtual environments for Python components
- Docker containers for services
- Hardhat for contract development
- Hot reloading for web client

## Technical Constraints

- Async-first backend (FastAPI, async workers, backend service layer)
- Backend service layer separate from API, can be deployed as a module or microservice
- Stateless API endpoints; session/state managed via Redis
- Secure credential management (never hardcode secrets)
- Multi-platform support: Linux, macOS, Windows
- Modular, extensible codebase

## Dependencies

### Python Packages
- FastAPI, pydantic, redis-py, aioredis
- pymongo, motor (async MongoDB)
- requests, aiohttp
- PyYAML, python-dotenv
- pytest, pytest-asyncio
- langchain, chromadb
- python-telegram-bot

### Backend Service Layer
- Supporting libraries for backend service layer (REST/gRPC/WebSocket if needed)
- Database drivers and connection pools
- Task queue libraries

### JavaScript/Node.js
- React, react-router, axios
- socket.io, markdown, highlight.js
- puppeteer (X-scraper)
- discord.js
- hardhat, ethers.js
- chai, mocha

## Tool Usage Patterns

### Registration & Configuration
- Decorator-based registration for tools, tasks, event handlers
- YAML-driven configuration for services
- Unified API endpoints across clients
- Environment-specific configs

### Development Practices
- Test-driven development
- Async/await patterns
- Error handling standards
- Logging conventions
- Documentation requirements

### Deployment
- Docker containerization
- CI/CD pipeline integration
- Environment separation
- Monitoring and logging
- Backup strategies
