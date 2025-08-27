# Refactor Phase Plan

This document tracks the phased refactor plan (Phase 0 – Phase 6) described in analysis.

## Phase 0 (Quick Wins)
- Introduce timezone-aware `utc_now()` helper & replace `datetime.utcnow()` usages.
- Precompile regex patterns.
- Add DB indexes migration for high-frequency lookups.
- Introduce structured logging scaffold.

## Phase 1 (Structural Extraction)
- Create `utils/`, `domain/`, `repositories/`, `services/` packages.
- Extract intent detection into `services/intent_service.py` (Strategy pattern scaffolding).
- Extract conversation update logic into `services/conversation_service.py`.
- Split `intelligent_coordinator.py` into submodules (core, prompts, tool_runner, context) preserving public shim.

## Phase 2 (Command & Strategy Patterns)
- Implement Command handlers for schedule, confirm, cancel, query.
- Register strategies in IntentService.
- Wire command dispatch prior to LLM where deterministic.

## Phase 3 (Security & Validation)
- Add Pydantic webhook request model & optional HMAC verification.
- Rate limiting (simple in-memory; pluggable Redis).
- Tool allowlist enforcement.
- Input sanitization and log redaction.

## Phase 4 (Performance & Scalability)
- Async DB or threadpool offload.
- Conversation snapshot optimization (dataclass slice).
- Caching of team member roster & prompt scaffolds.
- Background task queue for heavy operations.

## Phase 5 (Tooling & SDLC)
- `pyproject.toml` with ruff, black, mypy config.
- GitHub Actions CI (lint, typecheck, tests, coverage gate).
- Alembic migration setup.
- Pre-commit hooks.

## Phase 6 (Enhancements & Observability)
- Event bus abstraction.
- Metrics (Prometheus) & tracing.
- Rolling conversation summarization.
- Advanced ML intent classifier (optional).

## Acceptance Criteria Snapshot
- All legacy tests green throughout.
- Webhook route < 40 LoC after extraction.
- Zero naive `datetime.utcnow()` calls.
- Structured logs with correlation id.
- Coverage >= 70% initial, ratcheting upward.

## Risk / Mitigation
- Feature flags for new command engine.
- Legacy coordinator retained until parity tests pass.
- Incremental PRs per phase.
