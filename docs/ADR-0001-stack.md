# ADR-0001: Technology Stack

## Status
Accepted

## Context
CSR Call Assistant requires low-latency session handling, deterministic replay, and pragmatic delivery speed for an internal V1.

## Decision
- Use an event-sourced approach for deterministic replay and audit trail.
- Use a rules-first architecture for speed and safety, with no LLM dependency for critical alerts.
- Use FastAPI + Next.js for an async, typed, modern developer experience.
- Use PostgreSQL for strong consistency and JSONB payload flexibility.
- Use OpenRouter for model flexibility and fallback support.

## Consequences
- Core alerting remains available even if model providers are degraded.
- Event history supports debugging and future analytics.
- Teams can iterate quickly across API/web with strongly typed interfaces.
