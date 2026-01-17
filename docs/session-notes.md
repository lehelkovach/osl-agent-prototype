# Session Notes

Development log for OSL Agent Prototype.

---

## 2026-01-17: Docs Consolidation & Cleanup

### Changes
- Consolidated 51 docs into 5 essential files
- Updated README.md with current state
- Archived old/superseded documentation
- Cleaned up branches (archived `cursor/branch-merge-assessment-c4d7`)

### Current Docs Structure
```
docs/
├── MASTER-PLAN.md              # Roadmap and status
├── SETUP.md                    # Setup guide
├── KNOWSHOWGO-VISION.md        # Future and market
├── KNOWSHOWGO-SERVICE-HANDOFF.md # For standalone service
├── session-notes.md            # This file
└── archived/                   # Old docs (46 files)
```

---

## 2026-01-17: Pattern Evolution & Centroids

### KnowShowGo Additions
- `find_similar_patterns()` - Semantic search for transferable patterns
- `transfer_pattern()` - LLM-assisted field mapping
- `record_pattern_success()` - Track successful applications
- `auto_generalize()` - Auto-merge similar successful patterns
- `add_exemplar()` - Add exemplar, update centroid embedding
- `create_relationship()` - First-class edges with embeddings

### Agent Integration
- Pattern transfer when form autofill has missing fields
- Auto-generalization after successful fills
- `_llm_for_transfer()` helper for KnowShowGo operations

### Tests
- 25 pattern evolution tests
- 18 centroid/edge tests
- All passing

---

## 2026-01-16: Procedure Manager

### Changes
- Created `ProcedureManager` for LLM JSON → DAG conversion
- JSON schema for procedures with step dependencies
- Integrated into agent with auto-detection

### JSON Schema
```json
{
  "name": "Procedure Name",
  "steps": [
    {"id": "step_1", "tool": "web.get_dom", "params": {...}, "depends_on": []}
  ]
}
```

---

## Test Status

**592+ tests collected**
- Agent tests: 40+ files
- KnowShowGo tests: 8 files (83+ tests)
- Form/procedure tests: 10+ files
- Integration tests: Various

---

## Environment

```bash
# Required
OPENAI_API_KEY=sk-...

# Optional (persistent memory)
ARANGO_URL=https://...
ARANGO_DB=osl-agent
ARANGO_USER=...
ARANGO_PASSWORD=...

# Features
USE_PLAYWRIGHT=1
USE_CPMS_FOR_FORMS=1
```
