## Development Plan (minimal + parsimonious)

This file captures the current, shortest path to the prototype goals:
- learn web procedures from chat
- reuse/adapt/generalize procedures over time
- use CPMS to detect form patterns and store them in KnowShowGo
- reuse stored patterns to autofill login/billing forms using stored datasets

### Current status (as of 2026-01-06)
- **CPMS v0.1.2 `detect_form()` integrated** in `src/personal_assistant/cpms_adapter.py` with normalization + fallback.
- **CPMS pattern storage**: `KnowShowGoAPI.store_cpms_pattern()` stores patterns as `Concept` nodes (`source="cpms"`) and links via `has_pattern`.
- **Form fingerprinting**: `src/personal_assistant/form_fingerprint.py` computes deterministic fingerprints from `url+html`.
- **Pattern retrieval**: `KnowShowGoAPI.find_best_cpms_pattern(url, html, form_type?)` ranks stored patterns (domain + token overlap).
- **Reuse-first**: `cpms.detect_form` tool path in `agent.py` can now reuse a stored pattern before calling CPMS (when enabled).

### Flags / knobs
- **`USE_CPMS_FOR_FORMS=1`**: enable storing patterns and reuse-first behavior in `cpms.detect_form`.
- **`KSG_PATTERN_REUSE_MIN_SCORE`**: reuse threshold (default currently `2.0`). Higher = more conservative reuse.
- **`USE_PLAYWRIGHT=1`**: enables Playwright-backed tools in runtime (tests still use fixtures/mocks unless explicitly live).
- **`USE_FAKE_OPENAI=0`**: required for real OpenAI calls; set real `OPENAI_API_KEY`.

### Milestone 1 — Reuse stored patterns in actual web flows (next)
Goal: for login/billing tasks, prefer stored patterns before re-detecting.

- **Implementation**
  - Add an agent helper that, given `url`, calls:
    - `web.get_dom(url)` → `html`
    - `ksg.find_best_cpms_pattern(url, html, form_type)` to get selectors
  - If no strong stored match:
    - call `cpms.detect_form` and store the new exemplar (`has_pattern`)

- **Tests (TDD)**
  - Unit tests: reuse short-circuits CPMS call; weak match triggers CPMS.
  - Fixture tests: login HTML variations still match.

### Milestone 2 — Dataset learning and selection (next)
Goal: map detected fields → values stored from chat (no prompt when confidence is high).

- **Minimal datasets**
  - `Credential`: username/email/password (+ domain/url)
  - `Identity`: name/address/phone
  - `PaymentMethod`: cardNumber/cardExpiry/cardCvv/billingAddress
  - `FormData`: site-specific extras (escape hatch)

- **Selection policy (minimal)**
  - Prefer same-domain datasets.
  - Prompt only for missing required fields; store immediately after user provides.

### Milestone 3 — Trial/adapt loop for selectors (next)
Goal: when a fill fails, retry with alternative selectors and persist the winning selector.

- Store successful selector updates back into stored patterns (exemplar update or new exemplar).
- Record run outcomes (simple `Concept` “Run” nodes) for later weighting.

### Milestone 4 — Generalization across exemplars (later)
Goal: merge exemplars into generalized patterns once enough successful runs exist.

### Post-prototype refactors (after milestones above)
- **Graph-native properties**: migrate “object with properties” to nodes+edges only, and add Arango flattening query/view.
- **Weight/evidence overlay**: store edge weights as append-only evidence records and aggregate.
- **KnowShowGo extraction**: split into its own repo/package once API stabilizes.

### Live testing / debug loop (daemon-style)
Use this sequence when you have real env vars set (OpenAI/Arango/Playwright):

1) Run the service locally:
   - `poetry run agent-service`
2) Send a request:
   - `curl -sS http://localhost:8000/chat -H 'content-type: application/json' -d '{"message":"Log into example.com"}'`
3) Inspect logs:
   - `log_dump.txt` (clear between runs to isolate)

