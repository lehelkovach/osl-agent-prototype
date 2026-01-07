## Project Handoff (current)

This repo already has a comprehensive handoff doc at `docs/AGENT-HANDOFF.md`.
This file is the **current, high-signal handoff** for quickly continuing work.

### What this project is
An agent prototype that:
- learns procedures from chat (web/tool steps),
- recalls/reuses/adapts/generalizes procedures over time,
- uses CPMS to detect form patterns (login/billing),
- stores patterns + datasets in KnowShowGo semantic memory for reuse/autofill.

### Current state (as of 2026-01-06)
- **Core learning loop** (Learn/Recall/Execute/Adapt/Auto-Generalize): ✅ implemented and tested.
- **CPMS**:
  - `cpms-client` v0.1.2 `detect_form()` integrated in `src/personal_assistant/cpms_adapter.py` with normalization + fallback.
  - Patterns can be stored in KnowShowGo (`KnowShowGoAPI.store_cpms_pattern`) linked via `has_pattern`.
- **Pattern reuse**:
  - Deterministic form fingerprint: `src/personal_assistant/form_fingerprint.py` (from `url+html`).
  - Best-match retrieval: `KnowShowGoAPI.find_best_cpms_pattern(url, html, form_type?)`.
  - Agent tool path `cpms.detect_form` is reuse-first (can short-circuit CPMS).
- **Autofill flow**:
  - `form.autofill` now supports: `web.get_dom(url)` → reuse stored pattern (or CPMS detect+store) → fill using stored dataset values.
  - Minimal login synonyms supported (`email↔username`, `password`).
- **Tests**: `poetry run pytest` passes in this repo’s default (mock/fake) configuration.

### Most important docs
- `docs/development-plan.md` (**canonical next steps + flags + live test checklist**)
- `docs/AGENT-HANDOFF.md` (full background/context)
- `docs/session-notes.md` (running history, debug notes, recent changes)

### Local setup (recommended for live tests)
Cloud/dev agents are great for unit tests and coding, but **live OpenAI + Arango Cloud + real Playwright**
is generally best done **locally** so you can safely inject secrets and have stable network/browser behavior.

1) Install deps
- `poetry install`
- `poetry run playwright install --with-deps chromium`

2) Set `.env.local` (do not commit)
- `USE_FAKE_OPENAI=0`
- `OPENAI_API_KEY=...`
- `ARANGO_URL=...`
- `ARANGO_DB=knowshowgo`
- `ARANGO_USER=root`
- `ARANGO_PASSWORD=...`
- `USE_PLAYWRIGHT=1`

3) Run tests
- `poetry run pytest`

4) Run service + quick smoke
- `poetry run agent-service`
- `curl -sS http://localhost:8000/chat -H 'content-type: application/json' -d '{"message":"autofill login"}'`
- Inspect `log_dump.txt` (clear between runs)

### Next work (minimal prototype path)
1) Tighten dataset selection (Credential vs Identity/PaymentMethod/FormData) and required-field prompting.
2) Add minimal success verification for login/billing (DOM markers / URL change / form disappearance).
3) Add “trial/adapt” loop: if fill fails, re-detect selectors and persist a new exemplar or updated selectors.
4) Only after the prototype works end-to-end: refactor KnowShowGo toward pure node/edge properties + Arango flattening, then add weight/evidence overlays.

### Security note
Do **not** paste API keys/tokens into chat. Rotate any secrets that were previously pasted.

