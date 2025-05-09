# System Patterns: Impressox Agent

## System Architecture Overview

- **Modular, multi-layered architecture**: Core app, backends, clients, workers, smart contracts.
- **Backend service layer**: Các backend service xử lý nghiệp vụ, truy xuất dữ liệu, tích hợp hệ thống ngoài, tách biệt với API layer. Có thể triển khai dạng module hoặc microservice, giao tiếp với API, workers, smart contracts và các hệ thống lưu trữ.
- **LLM-centric orchestration**: Agent orchestrator manages state, routing, and tool execution.
- **Node-based processing**: Specialized nodes inherit from a common base, enabling extensibility.
- **Tool registry pattern**: Tools are registered and invoked dynamically per node/task.
- **Caching and checkpointing**: Redis and persistent storage for state, performance, and recovery.
- **Multi-platform client abstraction**: Web, Telegram, Discord clients share unified API and session logic.
- **Worker subsystem**: Scheduled and event-driven workers for automation, decoupled from main app.
- **Smart contract integration**: Solidity contracts, deployment scripts, and blockchain interaction layer.

## Key Technical Decisions

- **FastAPI** for API layer and async processing.
- **Redis** for caching and checkpointing.
- **YAML/ENV** for configuration management.
- **React** for web client, Python for bots, Solidity for contracts.
- **Decorator-based registration** for tools, tasks, and event handlers.
- **Task queue and event queue** for background processing.
- **Proxy pattern** for upgradable smart contracts.

## Design Patterns

- **Factory pattern**: AgentFactory for dynamic agent instantiation.
- **Orchestrator pattern**: AgentOrchestrator for managing agent workflows.
- **Template method**: BaseNode defines processing contract for all nodes.
- **Registry pattern**: Tool registry, event/task handler registries.
- **Observer pattern**: Event-driven workers and contract event listeners.
- **Strategy pattern**: Pluggable cache and checkpoint strategies.

## Component Relationships

- **API Layer** ⇄ **Backend Services** ⇄ **Agent Orchestrator** ⇄ **Nodes** ⇄ **Tools**
- **Clients** ⇄ **API Layer**
- **Workers** ⇄ **Backend Services** ⇄ **App Core** (via API or direct integration)
- **Smart Contracts** ⇄ **Backend Services** ⇄ **App Core** (via blockchain clients)

## Critical Implementation Paths

- Request → API → Backend Service → Orchestrator → Node(s) → Tool(s) → Response/Stream
- Client → API → Backend Service → Session/State Management
- Worker → Task/Event Queue → Backend Service → Processor → App Core
- App Core → Backend Service → Blockchain → Smart Contract → Event/Transaction

## Extensibility

- Add new backend services/modules để mở rộng nghiệp vụ hoặc tích hợp hệ thống ngoài.
- Add new nodes/tools via inheritance and registration.
- Add new clients by implementing API integration.
- Add new workers by registering tasks/events.
- Add/upgrade contracts using proxy and deployment scripts.
