# Project Brief: ImpressoX – AI Agent for DeFi Wallet Management

ImpressoX is your personal AI agent for DeFi, powered by Espresso Network.  
It aims to automate, secure, and simplify cross-chain wallet management with intelligent, always-on assistance.

## Core Objectives

- Provide a single AI agent to manage all DeFi wallet needs.
- Enable automated, cross-chain token swaps with fair ordering (Espresso fair sequencer).
- Deliver real-time wallet anomaly and risk alerts.
- Detect trends and market movements from social and market data.
- Summarize news and predict portfolio impact using AI.
- Offer a natural chat interface for user-agent interaction.
- Ensure wallet security and transaction guardrails.
- Integrate natively with Espresso Network for privacy, speed, and anti-frontrunning.

## Scope

- Architectural foundation: agent orchestrator, node structure, backend service layer, tool registry, prompt design.
- Backend service layer: handles business logic, data retrieval, external system integration, separate from the API layer, acts as a bridge between the API, agent core, workers, blockchain, and storage systems.
- Prompts for swap, alert, trend/news, portfolio analysis.
- (Planned) Cross-chain swap execution and portfolio management.
- (Planned) Wallet anomaly detection and alerting.
- (Planned) Trend and news monitoring (X/Twitter/Telegram).
- (Planned) AI-powered news summarization and impact analysis.
- (Planned) Secure, privacy-preserving transaction flows.
- (Planned) Multi-platform chat interface (web, Telegram, Discord).
- (Planned) Modular integration with Espresso Network and other rollups.

## Out of Scope

- Non-DeFi asset management.
- Centralized exchange integrations.
- Non-Espresso compatible blockchains.

## Success Criteria

- [Planned] Backend service layer functions as an intermediary bridge, ensuring efficient and secure business logic processing, data retrieval, and external system integration.
- [Planned] Users can manage DeFi assets, swap tokens, and receive alerts in one place.
- [Planned] No frontrunning or unfair execution due to Espresso integration.
- [Planned] Users receive actionable insights and security alerts in real time.
- [Planned] Seamless, secure, and privacy-preserving user experience.
- [Planned] Extensible roadmap: trend detection, auto strategies, agent marketplace, SaaS APIs.

## Current Status (May 2025)

- The codebase provides the architectural foundation, agent orchestrator, node structure, tool registry, and detailed AI prompts.
- Most DeFi/AI features are at the prompt and design level only.
- No real integration with blockchain, external data sources, or the Espresso Network yet.
- Security guardrails and automation logic are not implemented.
