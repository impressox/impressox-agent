# Product Context: ImpressoX

## Why This Project Exists

Managing DeFi assets is time-consuming, complex, and fragmented. Users miss trends, face security risks, and need multiple tools for swaps, analytics, and alerts. ImpressoX exists to unify and automate DeFi wallet management, providing a single AI agent that acts, alerts, and protects across chains—powered by Espresso Network for privacy, speed, and fair execution.

## Problems Solved

- Fragmented DeFi experience: multiple tools for swaps, portfolio, alerts, analytics.
- Missed market trends and poor risk decisions.
- Exposure to frontrunning and unfair execution.
- Manual, error-prone asset management.
- Lack of actionable, real-time insights and security guardrails.

## How It Should Work

- Users interact via a natural chat interface (web, Telegram, Discord).
- Backend service layer xử lý nghiệp vụ, truy xuất dữ liệu, tích hợp hệ thống ngoài, làm cầu nối giữa API, agent core, workers, blockchain, và các hệ thống lưu trữ.
- The agent monitors wallets, detects anomalies, and sends alerts.
- AI executes cross-chain swaps with fair ordering (Espresso fair sequencer).
- Trends and news are detected and summarized, with impact predictions on user portfolios.
- All actions are privacy-preserving, secure, and auditable.

## User Experience Goals

- One-stop DeFi wallet management: swap, monitor, alert, analyze.
- Real-time, actionable insights and security notifications.
- Backend đảm bảo trải nghiệm realtime, bảo mật, mở rộng tích hợp, và giảm tải cho API/agent.
- Seamless, privacy-first experience with no frontrunning.
- Always-on, intelligent assistant that understands and acts for the user.
- Extensible roadmap: trend detection, auto strategies, agent marketplace, SaaS APIs.

## Current Reality (May 2025)

- The codebase provides architecture, orchestrator, node structure, tool registry, and detailed AI prompts for all core features.
- Actual DeFi/AI features (swap, alert, trend/news, portfolio, security) are only implemented at the prompt/design level.
- No real blockchain, data, or Espresso Network integration yet.
- Security guardrails and automation logic are not implemented.
- Roadmap prioritizes implementing real integrations and automation in upcoming phases.
