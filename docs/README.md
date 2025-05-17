# 🧠 ImpressoX – AI Agent for DeFi Wallet Management

**ImpressoX** is your personal AI agent for DeFi, powered by Espresso Network.  
*Automated. Intelligent. Cross-Chain.*

---

## Project Status (May 2025)

> **Current State:**
> ImpressoX has a solid architectural foundation, including an agent orchestrator, node-based processing, a tool registry, and a backend service layer concept. Core prompts for DeFi tasks (swap, alerts, trend/news analysis, portfolio strategy) are designed.
>
> **Implemented Components:**
> -   Market monitoring system with rule-based price tracking (Redis-based).
> -   X-Scraper worker for collecting social media data (Node.js/Puppeteer, stores to MongoDB).
> -   Basic notification dispatch (integrated with Market Monitor).
> -   Telegram bot client for interaction.
> -   Next.js landing page for project promotion.
>
> **Development Focus / To Be Implemented:**
> -   **Full Backend Service Layer Implementation**: Formalizing the backend service layer to handle all business logic, data operations, and external integrations is a key ongoing task.
> -   **Real DeFi/AI Feature Logic**: Most core DeFi features (e.g., actual swap execution, comprehensive wallet anomaly detection, AI-driven news impact analysis) are currently at the prompt/design stage and require full implementation.
> -   **Blockchain & Espresso Network Integration**: No real integration with blockchain networks or the Espresso Network has been implemented yet. This is a critical next step.
> -   **Security Guardrails & Automation**: Robust security measures and full automation logic are pending.
> -   **Other Clients**: Web and Discord clients are planned.

---

## Why ImpressoX?

Managing DeFi assets is time-consuming, complex, and fragmented. Users often miss market trends, face security risks like frontrunning, and juggle multiple tools for swaps, portfolio tracking, and alerts. ImpressoX aims to unify and automate DeFi wallet management by providing a single, intelligent AI agent. This agent will act, alert, and protect across multiple chains, leveraging the Espresso Network for enhanced privacy, speed, and fair transaction ordering.

---

## Core Features (Vision)

-   🔁 **Automated Cross-Chain Swaps**: Execute token swaps across different blockchains with fair ordering and frontrunning protection via the Espresso Network's fair sequencer.
-   🧠 **Intelligent Wallet Monitoring & Alerts**: Real-time detection of wallet anomalies, potential security risks, and significant balance changes.
-   📈 **Social Trend Detection**: Identify emerging trends and sentiment from social media platforms (e.g., X/Twitter, Telegram) relevant to user assets or interests.
-   🌍 **AI-Powered News Analysis**: Summarize relevant news articles and predict their potential impact on a user's portfolio.
-   🔒 **Enhanced Wallet Security**: Implement transaction guardrails and security checks before execution.
-   💬 **Natural Language Interface**: Interact with the agent through intuitive chat interfaces on multiple platforms (Web, Telegram, Discord).
-   ⚡ **Espresso Native**: Utilize Espresso Network for its privacy features, fast confirmations, and modularity, ensuring secure and efficient operations.
-   💼 **Unified Portfolio Management**: View and manage DeFi assets across multiple chains from a single interface.

---

## Project Structure Overview

ImpressoX is composed of several key modules that work together:

-   **`/app`**: The heart of the AI agent. Contains the API (FastAPI), the Backend Service Layer (handling business logic), the Agent Orchestrator, processing Nodes, and Tools. See [`app/README.md`](app/README.md).
-   **`/clients`**: User-facing applications. Currently includes a Telegram bot, with Web and Discord clients planned. See [`clients/README.md`](clients/README.md).
-   **`/workers`**: Background processes for tasks like market monitoring (`market-monitor`), social media scraping (`x-scraper`), and notifications. See [`workers/README.md`](workers/README.md).
-   **`/landing-page`**: A Next.js application for the project's promotional website. See [`../landing-page/README.md`](../landing-page/README.md).
-   **`/contracts`**: (Planned) Solidity smart contracts for on-chain operations and Espresso Network integration. See [`contracts/README.md`](contracts/README.md).
-   **`/configs`**: Centralized YAML configuration files for all services and components.
-   **`/docs`**: This directory, containing detailed project documentation.
-   **`/memory-bank`**: Internal knowledge base for the AI assistant developing this project.

A simplified view:
```mermaid
graph LR
    subgraph "User Facing"
        LandingPage["/landing-page (Next.js Website)"]
        Clients["/clients (Telegram, Web, Discord)"]
    end

    subgraph "Core System"
        App["/app (API, Backend Services, Agent Core)"]
        Configs["/configs"]
    end

    subgraph "Supporting Systems"
        Workers["/workers (Market Monitor, X-Scraper, etc.)"]
        Contracts["/contracts (Planned Solidity Contracts)"]
        Databases["Databases (Redis, MongoDB, ChromaDB)"]
    end
    
    subgraph "Development & Meta"
        Docs["/docs (Project Documentation)"]
        MemoryBank["/memory-bank (AI Dev Context)"]
    end

    Clients --> App
    App <--> Workers
    App <--> Databases
    App <--> Contracts
    Workers <--> Databases
    LandingPage -.-> App % (Indirectly, e.g. for waitlist signups)
```

---

## Solution & Vision

ImpressoX aims to be the single, indispensable AI agent for all DeFi wallet management needs. It will provide:
-   Smart wallet tracking with proactive risk alerts.
-   AI-assisted and automated swap execution.
-   Detection of market trends and significant movements from diverse data sources.
-   Summarization of news with predictions of its impact on user portfolios.
-   Secure, privacy-preserving, and fair transaction execution, primarily through the Espresso Network.
-   An always-on, intelligent assistant for personal Web3 finance, accessible via natural language.

---

## Getting Started

For comprehensive setup instructions for all components (core agent, workers, landing page), please refer to the main [Project README](../README.md).

A quick overview for setting up the core application:
1.  Clone the repository.
2.  Navigate to the project root.
3.  Set up environment variables by copying `.env.example` to `.env` and filling in the required values.
4.  Install Python dependencies: `pip install -r requirements.txt`.
5.  Run the API server: `bash run_api.sh`.
6.  Run desired client interfaces (e.g., Telegram bot: `bash run_tele.sh`) and workers (e.g., Market Monitor: `bash run_monitor.sh`).

---

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines on how to contribute to the project, our code of conduct, and the process for submitting pull requests.

---

## Contact

-   **Website (Landing Page)**: (Link to be added when deployed, e.g., impressox.ai)
-   **Email**: [contact@impressox.ai](mailto:contact@impressox.ai) (Example)
-   **Twitter/X**: [@impressox](https://twitter.com/impressox) (Example)
