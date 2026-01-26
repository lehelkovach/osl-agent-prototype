# Development Plan: Temporal Graph Agent (TGA) Pivot

Status: draft
Last updated: 2026-01-26

## Purpose
Define a concrete plan to pivot toward the Temporal Graph Agent (TGA) while
preserving the current OSL Agent Prototype. This plan focuses on building a
graph-first task system with deterministic execution, plus optional semantic
and multimodal memory.

## Branch Strategy
- All TGA development will occur in a new branch.
- Keep the existing agent stable; do not refactor core behavior in place.
- Recommended branch name: tga/pivot-foundation (or similar).

## Architecture Decisions (Confirmed)
- KSG is retained as a structured graph memory layer but not used as the
  primary task retrieval engine.
- Add a deterministic GraphCache (NetworkX) as the primary working memory for
  tasks, events, rules, and dependencies.
- Add a separate Vault store for secrets. KSG stores metadata and references
  only, never raw secrets.
- Add a multimodal/vector store for unstructured memory (docs, screenshots,
  audio, notes). Link artifacts back to KSG or GraphCache nodes.
- LLM outputs structured actions validated by Pydantic; execution is fully
  deterministic.

## Workstreams

### 1) Foundation and Packaging
- Create a new package: src/tga/
- Shared utilities can be imported from src/personal_assistant if stable.
- Add Pydantic v2 models for:
  - Item, Relation, Trigger, AvailabilityWindow, SchedulingRule, AgentAction
- Define serialized schemas for persistence.

### 2) GraphCache + Persistence
- Implement GraphCache using NetworkX DiGraph.
- Read/write API:
  - get_item, get_blockers, get_actionable_tasks, events_in_range
  - save_item, save_relation, save_trigger
- Write-behind queue for async persistence.
- Adapter for ArangoDB (reuse patterns from arango_memory.py).
- Optional KSG adapter for storing structured nodes (strict mode).

### 3) LLM Interface + Action Execution
- Implement ActionExecutor with Pydantic-validated action schemas.
- Implement ContextBuilder that pulls deterministic context (no RAG).
- Implement LLM interface with structured output (LangChain or Instructor).

### 4) Rules and Scheduling
- Implement Trigger model and RuleEvaluator (no LLM).
- Integrate APScheduler for time-based triggers.
- Implement SchedulingEngine with portion + dateutil.
- Add AvailabilityWindow + SchedulingRule support.

### 5) API + Interfaces
- FastAPI endpoints:
  - /chat, /tasks, /schedule, /rules, /availability
- Optional CLI/REPL for local workflows.

### 6) Vault + Multimodal Memory
- Vault service for secrets (encrypted storage, policy-driven access).
- Multimodal store for unstructured data (vector search).
- Memory router to select deterministic graph vs vector search.
- Bidirectional linking:
  - Graph node -> artifact IDs
  - Artifact metadata -> graph node UUID

### 7) Testing and Hardening
- Unit tests for:
  - GraphCache queries
  - Rule evaluation
  - Scheduling engine
  - Action validation
- Integration tests for:
  - Persistence adapters
  - Trigger execution
  - End-to-end chat flow

## Milestones

### M1: TGA Core Skeleton (1-2 weeks)
- src/tga/ package created
- Pydantic models complete
- GraphCache working with unit tests

### M2: Deterministic Actions (1-2 weeks)
- ActionExecutor + ContextBuilder
- Structured LLM interface

### M3: Rules + Scheduler (2-3 weeks)
- Trigger evaluation + APScheduler
- Scheduling engine with availability rules

### M4: API + Persistence (1-2 weeks)
- FastAPI endpoints
- Arango persistence + write-behind

### M5: Vault + Multimodal (2-3 weeks)
- Vault adapter + secret refs in graph
- Multimodal store + linking

## Risks and Mitigations
- Risk: KSG embedding-first design conflicts with graph-first TGA.
  - Mitigation: Use KSG for persistence/metadata only; rely on GraphCache for
    task queries.
- Risk: Overlap with existing agent code causes regressions.
  - Mitigation: Keep TGA in a separate package and branch.

## Next Action
- Create the new TGA branch.
- Add src/tga/ skeleton and the core Pydantic models.
