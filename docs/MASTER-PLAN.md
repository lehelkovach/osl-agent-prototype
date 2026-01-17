# Master Plan: OSL Agent Prototype

**Version**: v1.5.0  
**Updated**: January 2026

---

## Current State: ✅ MVP Complete

| Component | Status |
|-----------|--------|
| Core Learning Loop | ✅ Learn → Recall → Execute → Adapt → Generalize |
| KnowShowGo | ✅ Pattern evolution, centroids, first-class edges |
| Form Pattern Learning | ✅ Learn, transfer, auto-generalize |
| Procedure DAGs | ✅ JSON → DAG, execution, reuse |
| Web Automation | ✅ Playwright integration |
| Safe Shell | ✅ Sandbox + rollback |
| Tests | ✅ 592+ passing |

---

## What Works

### 1. Agent Learning Loop
```
User: "Log into LinkedIn"
  ↓
Agent learns procedure → stores in KnowShowGo
  ↓
User: "Log into GitHub" (similar)
  ↓
Agent finds similar pattern → transfers → adapts
  ↓
After 2+ successes → auto-generalizes to "Login Pattern"
```

### 2. KnowShowGo Features
- **Pattern Evolution**: find_similar → transfer → auto_generalize
- **Centroid Embeddings**: Concepts drift toward usage
- **First-Class Edges**: Relationships are searchable
- **Procedure DAGs**: Multi-step procedures with dependencies

### 3. Form Automation
- Detect form types (login, checkout, survey)
- Learn field patterns and selectors
- Transfer patterns between similar forms
- Adapt when selectors fail

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              PersonalAssistantAgent          │
│  Intent → Memory Search → LLM Plan → Execute │
└─────────────────────────────────────────────┘
        ↓                    ↓
┌─────────────┐    ┌─────────────────────────┐
│   Memory    │    │      KnowShowGo         │
│ Arango/Chroma│    │  - Pattern Evolution   │
│ NetworkX    │    │  - Centroid Embeddings  │
└─────────────┘    │  - Procedure DAGs       │
                   └─────────────────────────┘
        ↓
┌─────────────────────────────────────────────┐
│                   Tools                      │
│  Web (Playwright) | Shell (Safe) | Tasks    │
└─────────────────────────────────────────────┘
```

---

## Key Files

| File | Purpose |
|------|---------|
| `agent.py` | Core agent loop |
| `knowshowgo.py` | Fuzzy ontology + pattern evolution |
| `procedure_manager.py` | JSON → DAG procedures |
| `form_filler.py` | Form pattern learning |
| `safe_shell.py` | Sandboxed shell |

---

## Branches

| Branch | Purpose |
|--------|---------|
| `main` | Active development |
| `knowshowgo-service-ready` | For when KnowShowGo becomes separate service |

---

## Next Steps

1. **Ship a product** - Browser extension or API
2. **Get users** - Validate the tech works for others
3. **KnowShowGo service** - Deploy standalone when ready

---

## Valuation

| Metric | Value |
|--------|-------|
| Code value | $200K-$500K |
| Pre-seed valuation | $2-3M |
| 5-year ceiling | $50-100M company |

See [KNOWSHOWGO-VISION.md](KNOWSHOWGO-VISION.md) for market analysis.
