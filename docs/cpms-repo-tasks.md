# CPMS Repository Development Tasks

## For Working on github.com/lehelkovach/cpms

**Context**: The osl-agent-prototype needs CPMS integration for form pattern detection. This document outlines what needs to be implemented/updated in the CPMS repository to support the agent integration.

## Integration Requirements from Agent Side

The agent expects CPMS to provide:

1. **Pattern Matching API** - Match HTML forms against stored patterns
2. **Pattern Storage** - Store and retrieve form patterns
3. **Signal Extraction** - Extract field patterns (email, password, submit) from HTML
4. **Observation Format** - Accept HTML + screenshots for pattern matching

## CPMS Repository Tasks

### Task 1: Pattern Matching API Endpoint

**Required Endpoint**: `POST /api/patterns/match` or similar

**Request Format** (expected by agent):
```json
{
  "html": "<html>...</html>",
  "screenshot": "base64_encoded_image" or "file_path",
  "observation": {
    "html": "...",
    "screenshot": "...",
    "dom_snapshot": {...},  // Optional Playwright snapshot
    "metadata": {
      "url": "https://example.com",
      "timestamp": "2024-01-01T00:00:00Z"
    }
  }
}
```

**Response Format** (expected by agent):
```json
{
  "form_type": "login",  // login, billing, card, etc.
  "fields": [
    {
      "type": "email",
      "selector": "input[type='email']",
      "xpath": "/html/body/form/input[1]",
      "confidence": 0.95,
      "signals": {
        "visual_cues": ["email icon", "placeholder text"],
        "position": {"x": 100, "y": 200},
        "attributes": {"type": "email", "name": "email"}
      }
    },
    {
      "type": "password",
      "selector": "input[type='password']",
      "confidence": 0.98,
      "signals": {...}
    },
    {
      "type": "submit",
      "selector": "button[type='submit']",
      "confidence": 0.90,
      "signals": {...}
    }
  ],
  "confidence": 0.92,
  "pattern_id": "pattern-uuid",  // If matching against stored pattern
  "matched_pattern": "pattern-name"  // Name of matched pattern if found
}
```

**Implementation Notes**:
- Should detect common form types: login, billing, card payment, survey
- Extract field selectors (CSS, XPath)
- Provide confidence scores
- Support matching against stored patterns if available
- Return signal data for pattern learning

---

### Task 2: Pattern Storage API

**Required Endpoints**:
- `POST /api/patterns` - Store a new pattern
- `GET /api/patterns/:id` - Retrieve a pattern
- `GET /api/patterns` - List patterns (with optional filtering)
- `PUT /api/patterns/:id` - Update a pattern
- `DELETE /api/patterns/:id` - Delete a pattern

**Pattern Storage Format**:
```json
{
  "id": "pattern-uuid",
  "name": "login_form_standard",
  "form_type": "login",
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
  "generalization_level": "high",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z",
  "usage_count": 5,
  "success_rate": 0.95
}
```

**Implementation Notes**:
- Patterns should be searchable by form_type, signals, selectors
- Support pattern versioning
- Track usage statistics (usage_count, success_rate)
- Enable pattern matching against stored patterns

---

### Task 3: Signal Extraction Engine

**Required**: Extract signal patterns from HTML/DOM

**Signal Types to Detect**:
1. **Field Type Signals**:
   - Email: `type="email"`, `name*="email"`, `name*="username"`, email icon, placeholder text
   - Password: `type="password"`, password icon
   - Submit: `type="submit"`, button text ("login", "sign in", "submit")
   - Card Number: `autocomplete="cc-number"`, `name*="card"`
   - Expiry: `autocomplete="cc-exp"`, `name*="exp"`
   - CVV: `autocomplete="cc-csc"`, `name*="cvv"`

2. **Visual Signals**:
   - Field position/layout
   - Icons near fields
   - Placeholder text patterns
   - Label text patterns

3. **Structural Signals**:
   - Form structure (number of fields, field order)
   - Field relationships (email before password)
   - Form container patterns

**Implementation Notes**:
- Use ML/pattern matching to identify field types
- Extract CSS selectors and XPath
- Calculate confidence scores
- Support both HTML parsing and visual analysis (from screenshots)

---

### Task 4: Pattern Matching Algorithm

**Required**: Match new forms against stored patterns

**Matching Criteria**:
1. **Field Type Matching**: Compare detected fields with pattern fields
2. **Selector Similarity**: Compare CSS selectors/XPath
3. **Layout Similarity**: Compare field positions/layout
4. **Signal Similarity**: Compare visual/structural signals

**Scoring**:
- Return confidence score (0.0 - 1.0)
- Return best match if confidence > threshold (e.g., 0.7)
- Return multiple candidates if close matches exist

**Implementation Notes**:
- Should be fast (real-time matching)
- Support fuzzy matching (similar but not identical forms)
- Enable pattern adaptation suggestions

---

### Task 5: Pattern Learning and Evolution

**Required**: Learn from successful/failed pattern matches

**Learning Features**:
1. **Success Tracking**: Track when patterns successfully match forms
2. **Failure Analysis**: Analyze why patterns fail
3. **Pattern Updates**: Update patterns based on new observations
4. **Pattern Generalization**: Merge similar patterns into generalized patterns

**Implementation Notes**:
- Store pattern usage history
- Calculate success rates
- Suggest pattern updates when success rate drops
- Support pattern versioning

---

### Task 6: Observation Building Utilities

**Required**: Helper functions to build observations from various inputs

**Input Formats**:
- Raw HTML string
- Playwright DOM snapshot
- Screenshot (image file or base64)
- Selenium/Playwright page objects

**Output Format**: Standardized observation format for CPMS API

**Implementation Notes**:
- Should normalize different input formats
- Extract relevant metadata
- Support both browser automation frameworks

---

## API Client Updates

**Package**: `cpms-client` (Python package)

**Required Methods**:
```python
class Client:
    def match_pattern(self, html: str, screenshot_path: Optional[str] = None, observation: Optional[Dict] = None) -> Dict[str, Any]:
        """Match form pattern from HTML/screenshot"""
        
    def create_pattern(self, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Store a new pattern"""
        
    def get_pattern(self, pattern_id: str) -> Dict[str, Any]:
        """Retrieve a pattern by ID"""
        
    def list_patterns(self, form_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """List patterns, optionally filtered by form_type"""
        
    def update_pattern(self, pattern_id: str, pattern_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing pattern"""
        
    def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a pattern"""
```

**Current State**: Check what methods already exist in `cpms-client`

**Updates Needed**:
- Ensure `match_pattern` method exists and matches expected signature
- Add observation parameter support
- Ensure response format matches agent expectations

---

## Testing Requirements

### Unit Tests
- Signal extraction from various HTML structures
- Pattern matching algorithm accuracy
- Pattern storage/retrieval
- Observation building from different inputs

### Integration Tests
- End-to-end pattern matching flow
- Pattern storage and retrieval
- Pattern matching against stored patterns
- API endpoint testing

### Test Data
- Various form types (login, billing, card, survey)
- Different HTML structures
- Screenshots for visual analysis
- Edge cases (nested forms, dynamic forms, etc.)

---

## Environment/Configuration

**Required Environment Variables** (for CPMS service):
```bash
# Database/Storage
CPMS_DB_URL=...
CPMS_DB_NAME=...

# API Configuration
CPMS_PORT=3000
CPMS_HOST=0.0.0.0

# Authentication (if needed)
CPMS_API_KEY=...
CPMS_JWT_SECRET=...

# ML/Pattern Matching
CPMS_MODEL_PATH=...  # If using ML models
CPMS_CONFIDENCE_THRESHOLD=0.7
```

---

## Integration Points with Agent

### Agent → CPMS Flow
1. Agent gets HTML + screenshot from web tools
2. Agent calls `cpms_client.match_pattern(html, screenshot_path)`
3. CPMS returns pattern data with field selectors
4. Agent uses pattern for form filling

### CPMS → Agent Flow
1. CPMS stores patterns via API
2. Agent stores pattern metadata in KnowShowGo via `ksg.store_cpms_pattern()`
3. Agent queries patterns when needed
4. Agent can update patterns based on execution results

---

## Priority Order

1. **High Priority**: Pattern Matching API (`match_pattern`)
   - Core functionality needed by agent
   - Must return expected format

2. **Medium Priority**: Pattern Storage API
   - Enables pattern reuse
   - Supports pattern learning

3. **Medium Priority**: Signal Extraction
   - Improves pattern matching accuracy
   - Enables better field detection

4. **Low Priority**: Pattern Learning
   - Nice to have for long-term improvement
   - Can be added incrementally

---

## Questions to Resolve

1. What is the current CPMS API structure?
2. Does `match_pattern` endpoint already exist?
3. What format does CPMS currently use for patterns?
4. Does CPMS support visual analysis (screenshots)?
5. What ML/models does CPMS use for pattern detection?
6. How are patterns currently stored in CPMS?

---

## Success Criteria

- [ ] `match_pattern` API returns expected format
- [ ] Can detect login forms with email/password/submit fields
- [ ] Returns confidence scores and selectors
- [ ] Supports pattern storage and retrieval
- [ ] `cpms-client` package updated with new methods
- [ ] Documentation updated
- [ ] Tests pass

---

## Reference

- Agent integration plan: `docs/cpms-integration-plan.md` (in osl-agent-prototype)
- Agent expects: Pattern data format as defined in integration plan
- Agent adapter: `src/personal_assistant/cpms_adapter.py` (shows what agent needs)

