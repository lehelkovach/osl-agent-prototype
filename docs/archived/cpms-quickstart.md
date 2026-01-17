# CPMS Development Quick Start

## For Starting CPMS Work in a New Conversation

**Context**: This project needs CPMS (github.com/lehelkovach/cpms) integration for form pattern detection and matching. The agent-side integration points are ready; CPMS-specific implementation is needed.

## Immediate First Steps

### 1. Review CPMS Repository
- Clone/examine: `github.com/lehelkovach/cpms`
- Understand CPMS API endpoints, especially `match_pattern`
- Review CPMS client library (`cpms-client` package)

### 2. Review Integration Plan
- Read: `docs/cpms-integration-plan.md` (full task breakdown)
- Current integration points: `src/personal_assistant/cpms_adapter.py`
- Fallback implementation exists; needs full API integration

### 3. Start with Task 1: Pattern Matching API
**File**: `src/personal_assistant/cpms_adapter.py`
**Method**: `detect_form_pattern()`

**Current State**:
```python
def detect_form_pattern(self, html: str, screenshot_path: Optional[str] = None) -> Dict[str, Any]:
    # Has fallback simple detection
    # Needs full CPMS API call
```

**What to Do**:
1. Investigate CPMS `match_pattern` API signature
2. Implement observation building (HTML + screenshot → CPMS format)
3. Call CPMS API and parse response
4. Return structured pattern data (see integration plan for format)

**Test Command**:
```bash
# After implementation, test with:
pytest tests/test_cpms_adapter.py -k test_detect_form_pattern -v
```

## Key Files to Modify

1. **`src/personal_assistant/cpms_adapter.py`**
   - `detect_form_pattern()` - main integration point
   - Add observation building method
   - Add signal extraction method

2. **`tests/test_cpms_adapter.py`** (may need to create)
   - Test pattern detection with mock CPMS
   - Test with real CPMS (gated by env)

3. **`src/personal_assistant/agent.py`** (already integrated)
   - `cpms.detect_form` tool already wired
   - May need updates based on CPMS response format

## Environment Setup

```bash
# Required for CPMS integration
CPMS_BASE_URL=http://localhost:3000  # or your CPMS instance
CPMS_TOKEN=your_token_here
# or
CPMS_API_KEY=your_key_here

# Feature flag (already exists)
USE_CPMS_FOR_PROCS=1
```

## Expected Pattern Data Format

From `cpms-integration-plan.md`:
```python
{
    "form_type": "login",  # login, billing, card, etc.
    "fields": [
        {
            "type": "email",
            "selector": "input[type='email']",
            "xpath": "/html/body/form/input[1]",
            "confidence": 0.95,
            "signals": {...}  # CPMS signal data
        },
        # ... password, submit fields
    ],
    "confidence": 0.92,
    "cpms_pattern_id": "pattern-uuid"  # if CPMS returns pattern ID
}
```

## Integration Flow (Already Implemented)

1. Agent calls `web.get_dom()` and `web.screenshot()`
2. Agent calls `cpms.detect_form(html, screenshot_path)`
3. **YOU IMPLEMENT**: CPMS adapter builds observation, calls CPMS API
4. Agent receives pattern data with selectors
5. Agent uses pattern for `web.fill(selectors=pattern['fields'])`
6. Agent stores pattern via `ksg.store_cpms_pattern()` (already implemented)

## Questions to Answer

1. What is the exact CPMS `match_pattern` API signature?
2. What format does CPMS expect for observations?
3. What does CPMS return in pattern responses?
4. How are patterns stored/retrieved in CPMS?
5. Can CPMS match against stored patterns?

## Success Criteria

- [ ] `detect_form_pattern()` calls real CPMS API (not just fallback)
- [ ] Pattern data structure matches expected format
- [ ] Works with various form types (login, billing, card)
- [ ] Fallback still works when CPMS unavailable
- [ ] Tests pass (unit + integration)

## Next Steps After Task 1

See `docs/cpms-integration-plan.md` for:
- Task 2: Observation building from Playwright
- Task 3: Signal extraction
- Task 4: Pattern matching for adaptation
- Task 5: Pattern learning and generalization

## Reference

- Full plan: `docs/cpms-integration-plan.md`
- Current adapter: `src/personal_assistant/cpms_adapter.py`
- Agent integration: `src/personal_assistant/agent.py` (lines ~760-770)
- KnowShowGo pattern storage: `src/personal_assistant/knowshowgo.py` (`store_cpms_pattern`)

