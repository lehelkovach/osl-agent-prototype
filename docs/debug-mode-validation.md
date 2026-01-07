# Debug Mode Validation

## Overview

This document describes how to validate that the agent achieves its ultimate goal when running in **debug/daemon mode** (live service), not just in unit tests.

## Debug Daemon Setup

### Starting the Debug Daemon

**Windows (PowerShell):**
```powershell
.\scripts\start_daemon.ps1
```

**Linux/Mac (Bash):**
```bash
./scripts/debug_daemon.sh start
```

The daemon runs on `http://localhost:8000` by default.

### Environment Variables

- `HOST` (default: `127.0.0.1`)
- `PORT` (default: `8000`)
- `AGENT_LOG_FILE` (default: `log_dump.txt`)
- `DEBUG=1` or `DEBUG=true` - Enable debug mode
- `OPENAI_API_KEY` - If set, uses real OpenAI; otherwise uses fake/local

## Testing Ultimate Goal in Debug Mode

### Automated Test Script

Run the automated test script:

```powershell
.\scripts\test_ultimate_goal_debug.ps1
```

Or with daemon management:

```powershell
# Start daemon and run test
.\scripts\test_ultimate_goal_debug.ps1 -StartDaemon

# Run test and stop daemon
.\scripts\test_ultimate_goal_debug.ps1 -StopDaemon
```

### Manual Testing via HTTP

You can also test manually by sending HTTP requests:

#### 1. LEARN - Teach a procedure
```powershell
$body = @{
    message = "Remember: to log into site1.com, go to https://site1.com/login, fill email field with #email selector and password field with #password selector, then click the submit button"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" -Method POST -ContentType "application/json" -Body $body
```

#### 2. RECALL - Request similar task
```powershell
$body = @{
    message = "Log into site2.com"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" -Method POST -ContentType "application/json" -Body $body
```

#### 3. EXECUTE - Verify execution
Check the response for `execution_results.status` and `plan.steps` containing web tool calls.

#### 4. ADAPT - Test adaptation
```powershell
$body = @{
    message = "Log into site3.com (this will fail initially to test adaptation)"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" -Method POST -ContentType "application/json" -Body $body
```

#### 5. AUTO-GENERALIZE - Multiple procedures
```powershell
$body = @{
    message = "Remember: to log into site4.com, go to https://site4.com/login, fill email and password, then click submit"
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/chat" -Method POST -ContentType "application/json" -Body $body
```

## Validation Checklist

When testing in debug mode, verify:

### ✅ LEARN
- [ ] Procedure stored in KnowShowGo
- [ ] Log shows `procedure.create` or `ksg.create_concept`
- [ ] Response status is `completed`

### ✅ RECALL
- [ ] Agent searches KnowShowGo (`ksg.search_concepts` in plan)
- [ ] Similar procedure found
- [ ] Plan adapts found procedure for new task

### ✅ EXECUTE
- [ ] Plan contains web tool steps (`web.fill`, `web.click_selector`, etc.)
- [ ] Execution status is `completed` or `ask_user`
- [ ] Log shows `execution_completed`

### ✅ ADAPT
- [ ] Initial execution fails (wrong selector/URL)
- [ ] Agent retries with adapted plan
- [ ] Log shows `adaptation_succeeded` or `execution_failed_attempting_adaptation`
- [ ] Adapted procedure stored

### ✅ AUTO-GENERALIZE
- [ ] Multiple similar procedures stored
- [ ] Log shows `learned_from_success`
- [ ] Generalization occurs when 2+ similar procedures succeed

## Log Analysis

Check the log file (`log_dump.txt` by default) for key indicators:

```powershell
# View last 100 lines
Get-Content log_dump.txt -Tail 100

# Search for key indicators
Select-String -Path log_dump.txt -Pattern "procedure.create|ksg.search_concepts|execution_completed|learned_from_success|adaptation_succeeded"
```

### Key Log Patterns

**LEARN:**
```
procedure.create
memory_upsert kind=node
```

**RECALL:**
```
ksg.search_concepts
memory_search
memory_retrieved
```

**EXECUTE:**
```
tool_start tool=web.fill
tool_result status=success
execution_completed status=completed
```

**ADAPT:**
```
execution_failed_attempting_adaptation
adapted_plan_generated
adaptation_succeeded
```

**AUTO-GENERALIZE:**
```
learned_from_success
auto_generalize_if_applicable
```

## Troubleshooting

### Daemon Not Running
```powershell
# Check status
.\scripts\start_daemon.ps1  # Will show if already running

# Or check health endpoint
Invoke-RestMethod -Uri "http://localhost:8000/health"
```

### Tests Failing
1. Check log file for errors
2. Verify daemon is running: `Invoke-RestMethod -Uri "http://localhost:8000/health"`
3. Check if OpenAI API key is set (or USE_FAKE_OPENAI=1)
4. Verify memory backend is accessible (ArangoDB/ChromaDB or Mock)

### No Procedures Stored
- Check if `procedure.create` tool is being called
- Verify KnowShowGo is initialized (prototypes seeded)
- Check log for `memory_upsert` entries

## Success Criteria

The ultimate goal is achieved in debug mode when:

1. ✅ **LEARN**: Procedures can be taught via chat and stored
2. ✅ **RECALL**: Similar procedures are found via semantic search
3. ✅ **EXECUTE**: Procedures execute via DAG execution
4. ✅ **ADAPT**: Failed procedures are adapted and retried
5. ✅ **AUTO-GENERALIZE**: Multiple successes lead to generalization

All phases should work when the agent runs as a live daemon service, not just in unit tests.

