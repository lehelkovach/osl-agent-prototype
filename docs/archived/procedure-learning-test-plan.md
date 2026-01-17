# Procedure Learning Test Plan

**Goal**: Test the agent's ability to learn, remember, and adapt login procedures across different form variations.

---

## Test Scenario

### Phase 1: Initial Learning
1. **User Instruction**: "Go to the login form test page and login"
   - Agent should:
     - Navigate to `tests/fixtures/login_generate.html?page=1`
     - Detect the form using CPMS
     - Infer steps to fill email/password and click submit
     - Store the procedure in KnowShowGo
     - Execute the procedure

2. **Expected Behavior**:
   - Agent creates a procedure concept with steps
   - Procedure stored with embedding for later recall
   - Execution succeeds (or asks for credentials if needed)

### Phase 2: Recall and Adaptation
3. **User Instruction**: "This is a similar login page, login here" (pointing to `?page=2`)
   - Agent should:
     - Navigate to `tests/fixtures/login_generate.html?page=2`
     - Search KnowShowGo for similar procedures
     - Find the previously learned login procedure
     - Adapt it for the new form (different field names/selectors)
     - Execute the adapted procedure

4. **Expected Behavior**:
   - Agent recalls the previous login procedure
   - Adapts selectors/field names for the new form
   - Stores adapted version or updates existing procedure
   - Execution succeeds

### Phase 3: Generalization
5. **User Instruction**: "Login to another similar page" (pointing to `?page=3`)
   - Agent should:
     - Navigate to `tests/fixtures/login_generate.html?page=3`
     - Recall and adapt procedure again
     - After multiple successful adaptations, potentially generalize

6. **Expected Behavior**:
   - Agent successfully adapts procedure again
   - If 2+ similar procedures work, agent may auto-generalize
   - Creates generalized "login form" pattern

---

## Test Execution Steps

1. Start the daemon: `./scripts/debug_daemon.sh start` (or Windows equivalent)
2. Send chat messages via curl/HTTP
3. Monitor `log_dump.txt` for agent behavior
4. Check ArangoDB for stored procedures/concepts

---

## Success Criteria

- ✅ Agent learns procedure from first instruction
- ✅ Agent recalls procedure when similar task requested
- ✅ Agent adapts procedure for different form variations
- ✅ Agent stores adapted versions
- ✅ Agent can execute adapted procedures successfully
- ✅ Agent may auto-generalize after multiple exemplars

---

## Files Needed

- `tests/fixtures/login_generate.html` - Dynamic form generator (✅ created)
- Test credentials (can be mock/test values)
- Daemon running with real services enabled


