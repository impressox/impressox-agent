# Tech Context: Impressox Agent

## Technologies Used

- **Python**: Core application, API server (FastAPI), backend service layer, bots, workers.
- **Backend service layer**: Python (FastAPI hoặc module riêng), có thể tích hợp thêm các service khác (REST, gRPC, WebSocket) để xử lý nghiệp vụ, truy xuất dữ liệu, tích hợp hệ thống ngoài.
- **FastAPI**: Async API layer for core app.
- **React**: Web client interface.
- **Solidity**: Smart contract development.
- **Redis**: Caching and checkpointing.
- **YAML/ENV**: Configuration management.
- **Docker**: (if used, for deployment and local dev).
- **Hardhat**: Smart contract deployment/testing.
- **Node.js/NPM**: Web and Discord client tooling.
- **pytest**: Python testing.
- **Chai/Mocha**: Contract and JS client testing.

## Development Setup

- Python 3.9+ and pip cho backend service layer, core app, bots, và workers.
- Backend service layer có thể chạy độc lập hoặc cùng core app, cấu hình qua YAML/ENV.
- Node.js 16+ and npm for web/discord clients and contracts.
- Redis server for caching and background processing.
- Environment variables managed via `.env` and YAML config files.
- Virtual environments recommended for Python components.
- Hardhat for contract deployment and testing.

## Technical Constraints

- Async-first backend (FastAPI, async workers, backend service layer).
- Backend service layer tách biệt với API, có thể triển khai dạng module hoặc microservice.
- Stateless API endpoints; session/state managed via cache.
- Secure credential management (never hardcode secrets).
- Multi-platform support: Linux, macOS, Windows (with Docker or venv).
- Modular, extensible codebase for easy feature addition.

## Dependencies

- FastAPI, pydantic, redis-py, aioredis, requests, PyYAML, pytest.
- Các thư viện bổ trợ cho backend service layer (REST/gRPC/WebSocket nếu cần).
- React, react-router, axios, socket.io, markdown, highlight.js.
- python-telegram-bot, discord.py.
- hardhat, ethers.js, chai, mocha.

## Tool Usage Patterns

- Decorator-based registration for tools, tasks, event handlers.
- YAML-driven configuration for models, services, and workers.
- Unified API endpoints for all clients.
- Test-driven development for all subsystems.
- CI/CD pipeline recommended for deployment.
