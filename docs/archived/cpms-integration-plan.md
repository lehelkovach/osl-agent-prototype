# CPMS Integration Development Plan

## Current State

### What's Already Implemented

1. **Basic CPMS Adapter** (`src/personal_assistant/cpms_adapter.py`)
   - `CPMSAdapter` class with basic procedure/task operations
   - `detect_form_pattern()` method with fallback simple detection
   - Environment-based initialization via `CPMSAdapter.from_env()`

2. **Agent Integration Points**
   - `cpms.detect_form` tool available to LLM
   - `cpms.create_procedure`, `cpms.list_procedures`, `cpms.get_procedure` tools
   - `cpms.create_task`, `cpms.list_tasks` tools
   - CPMS routing toggle via `USE_CPMS_FOR_PROCS` env flag

3. **KnowShowGo Pattern Storage**
   - `ksg.store_cpms_pattern()` method to store CPMS patterns as concepts
   - Pattern concepts linked to parent concepts via `has_pattern` edges
   - Embeddings stored for pattern similarity matching

4. **Fallback Form Detection**
   - Simple regex-based detection for email/password/submit patterns
   - Works independently of CPMS API availability

## CPMS Development Tasks

### Task 1: Enhanced CPMS Pattern Matching API Integration

**Location**: `src/personal_assistant/cpms_adapter.py`

**Current State**: 
- `detect_form_pattern()` has basic fallback
- Needs full CPMS API integration

**Required Work**:
1. **Investigate CPMS API** (github.com/lehelkovach/cpms)
   - Review `match_pattern` API endpoint
   - Understand request/response format
   - Document pattern data structure

2. **Implement Full API Integration**
   ```python
   def detect_form_pattern(self, html: str, screenshot_path: Optional[str] = None) -> Dict[str, Any]:
       """
       Full CPMS integration:
       - Build observation from HTML + screenshot
       - Call cpms_client.match_pattern() or similar
       - Parse response for field patterns (email, password, submit)
       - Return structured pattern data
       """
   ```

3. **Pattern Data Structure** (to be confirmed with CPMS API):
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
           {
               "type": "password",
               "selector": "input[type='password']",
               "confidence": 0.98
           },
           {
               "type": "submit",
               "selector": "button[type='submit']",
               "confidence": 0.90
           }
       ],
       "confidence": 0.92,
       "cpms_pattern_id": "pattern-uuid"  # if CPMS returns pattern ID
   }
   ```

**Testing Requirements**:
- Unit tests with mock CPMS client
- Integration tests with real CPMS instance (gated by env flag)
- Test fallback behavior when CPMS unavailable
- Test various form types (login, billing, card, survey)

---

### Task 2: CPMS Observation Building from Playwright

**Location**: New method in `cpms_adapter.py` or `web_tools.py`

**Required Work**:
1. **Build Observations from Playwright Snapshots**
   ```python
   def build_cpms_observation(
       self, 
       html: str, 
       screenshot_path: str,
       dom_snapshot: Optional[Dict] = None
   ) -> Dict[str, Any]:
       """
       Build CPMS observation format from:
       - HTML DOM
       - Screenshot image
       - Optional Playwright DOM snapshot
       
       Returns observation dict in CPMS expected format
       """
   ```

2. **Observation Structure** (to be confirmed):
   ```python
   {
       "html": "<html>...</html>",
       "screenshot": "base64_encoded_image" or "file_path",
       "dom_snapshot": {...},  # Playwright snapshot if available
       "metadata": {
           "url": "https://example.com",
           "timestamp": "2024-01-01T00:00:00Z"
       }
   }
   ```

3. **Integration Points**:
   - Call from `web.get_dom()` or `web.screenshot()` results
   - Pass to `cpms.detect_form()` tool
   - Store observations with patterns in KnowShowGo

**Testing Requirements**:
- Test observation building from various HTML structures
- Test with/without Playwright snapshots
- Test screenshot encoding/upload

---

### Task 3: Advanced Pattern Signal Extraction

**Location**: `src/personal_assistant/cpms_adapter.py` or new `cpms_signals.py`

**Required Work**:
1. **Extract Signal Patterns from CPMS Response**
   ```python
   def extract_pattern_signals(self, cpms_response: Dict[str, Any]) -> Dict[str, Any]:
       """
       Extract signal patterns from CPMS match_pattern response.
       Signals include:
       - Field type indicators (email, password, etc.)
       - Selector patterns
       - Confidence scores
       - Visual/layout signals
       """
   ```

2. **Signal Storage Format**:
   ```python
   {
       "pattern_name": "login_form_standard",
       "signals": {
           "email_field": {
               "selectors": ["input[type='email']", "input[name*='email']"],
               "confidence": 0.95,
               "visual_cues": ["email icon", "placeholder text"],
               "position": {"x": 100, "y": 200}
           },
           "password_field": {...},
           "submit_button": {...}
       },
       "generalization_level": "high"  # how generalizable this pattern is
   }
   ```

3. **Store in KnowShowGo**:
   - Use existing `ksg.store_cpms_pattern()` method
   - Link patterns to concepts (login procedures, form concepts)
   - Enable pattern reuse across similar forms

**Testing Requirements**:
- Test signal extraction from various CPMS responses
- Test pattern storage and retrieval
- Test pattern matching against new forms

---

### Task 4: CPMS Pattern Matching for Form Adaptation

**Location**: `src/personal_assistant/agent.py` or new `form_matcher.py`

**Required Work**:
1. **Match Stored Patterns to New Forms**
   ```python
   def match_form_to_pattern(
       self, 
       html: str, 
       concept_uuid: Optional[str] = None
   ) -> Optional[Dict[str, Any]]:
       """
       Match a new form HTML to stored CPMS patterns.
       - Query KnowShowGo for patterns associated with concept
       - Use CPMS to match against stored patterns
       - Return best match with confidence score
       """
   ```

2. **Adaptation Logic**:
   - Find closest matching pattern
   - Extract differences (new selectors, layout changes)
   - Suggest adaptations for form filling
   - Update pattern if adaptation successful

3. **Integration with Form Filling**:
   - Use matched patterns to auto-detect selectors
   - Fall back to manual selector specification if no match
   - Learn from successful fills to improve patterns

**Testing Requirements**:
- Test pattern matching accuracy
- Test adaptation for similar but different forms
- Test fallback behavior when no match found

---

### Task 5: CPMS Pattern Learning and Generalization

**Location**: `src/personal_assistant/knowshowgo.py` (extend existing generalization)

**Required Work**:
1. **Merge CPMS Patterns into Generalized Concepts**
   - When multiple login forms detected, merge their patterns
   - Create generalized pattern with common signals
   - Link specific patterns as exemplars

2. **Pattern Evolution**:
   - Track pattern success/failure rates
   - Update patterns based on execution results
   - Version patterns when significant changes detected

3. **Taxonomy Building**:
   - Build hierarchy: General Login Pattern → Site-Specific Patterns
   - Enable pattern inheritance and override
   - Support pattern composition (combine multiple patterns)

**Testing Requirements**:
- Test pattern merging logic
- Test pattern versioning
- Test taxonomy hierarchy building

---

## Integration Points Summary

### Agent → CPMS Flow

1. **User Request**: "Log into X.com"
2. **Agent**: Calls `web.get_dom()` and `web.screenshot()`
3. **Agent**: Calls `cpms.detect_form(html, screenshot_path)`
4. **CPMS Adapter**: 
   - Builds observation from HTML + screenshot
   - Calls CPMS `match_pattern` API
   - Returns pattern data with field selectors
5. **Agent**: Uses pattern to fill form with `web.fill(selectors=pattern['fields'])`
6. **Agent**: Stores pattern via `ksg.store_cpms_pattern()` for future reuse

### KnowShowGo → CPMS Flow

1. **Concept Search**: Agent searches for "logging into X" concept
2. **Pattern Retrieval**: If concept found, retrieve associated CPMS patterns
3. **Pattern Matching**: Match new form HTML against stored patterns
4. **Adaptation**: Adapt pattern selectors if needed
5. **Execution**: Use adapted pattern for form filling
6. **Learning**: Update pattern based on success/failure

## Environment Variables

```bash
# CPMS Connection
CPMS_BASE_URL=http://localhost:3000
CPMS_TOKEN=your_token_here
CPMS_API_KEY=alternative_key

# Feature Flags
USE_CPMS_FOR_PROCS=1  # Route procedure.create to CPMS
USE_CPMS_FOR_FORMS=1  # Enable CPMS form detection (to be added)
```

## Testing Strategy

### Unit Tests
- Mock CPMS client responses
- Test pattern extraction and storage
- Test fallback behavior

### Integration Tests
- Real CPMS instance (gated by env)
- Test with various form types
- Test pattern matching and adaptation

### E2E Tests
- Full flow: detect form → store pattern → reuse pattern
- Test pattern generalization
- Test adaptation on similar forms

## Dependencies

- `cpms-client` package (already in requirements.txt)
- CPMS service running (github.com/lehelkovach/cpms)
- Playwright for screenshots (optional but recommended)

## Notes

- Current fallback form detection works independently
- Agent can function without full CPMS integration
- CPMS work can proceed in parallel without blocking agent development
- All integration points are defined and ready for implementation

## Quick Start

**For Agent-Side CPMS Work** (this repo):
- See `docs/cpms-quickstart.md` for immediate first steps and starter checklist
- Use `docs/cpms-starter-message.txt` to begin a new conversation

**For CPMS Repository Work** (github.com/lehelkovach/cpms):
- See `docs/cpms-repo-tasks.md` for CPMS repository development tasks
- Use `docs/cpms-repo-starter.txt` to begin a new conversation on CPMS repo

