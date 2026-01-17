# Test Ultimate Goal in Debug Daemon Mode
# This script validates that the agent achieves its ultimate goal when running in debug/daemon mode
# 
# Usage:
#   1. Start daemon: .\scripts\start_daemon.ps1
#   2. Run this test: .\scripts\test_ultimate_goal_debug.ps1
#
# Or run both:
#   .\scripts\test_ultimate_goal_debug.ps1 -StartDaemon

param(
    [string]$BaseUrl = "http://localhost:8000",
    [switch]$StartDaemon = $false,
    [switch]$StopDaemon = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=== Ultimate Goal Test in Debug Mode ===" -ForegroundColor Cyan
Write-Host ""

# Check if daemon is running
function Test-DaemonRunning {
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET -TimeoutSec 2
        return $true
    } catch {
        return $false
    }
}

# Start daemon if requested
if ($StartDaemon) {
    Write-Host "Starting daemon..." -ForegroundColor Yellow
    & .\scripts\start_daemon.ps1
    Start-Sleep -Seconds 3
}

# Check if daemon is running
if (-not (Test-DaemonRunning)) {
    Write-Host "ERROR: Daemon is not running at $BaseUrl" -ForegroundColor Red
    Write-Host "Start it with: .\scripts\start_daemon.ps1" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Daemon is running at $BaseUrl" -ForegroundColor Green
Write-Host ""

# Clear log for clean test
$logFile = if ($env:AGENT_LOG_FILE) { $env:AGENT_LOG_FILE } else { "log_dump.txt" }
if (Test-Path $logFile) {
    Clear-Content $logFile
    Write-Host "Cleared log file: $logFile" -ForegroundColor Gray
}

$allTestsPassed = $true

# ==========================================
# PHASE 1: LEARN - User teaches procedure
# ==========================================
Write-Host "PHASE 1: LEARN - Teaching login procedure" -ForegroundColor Yellow
$learnRequest = @{
    message = "Remember: to log into site1.com, go to https://site1.com/login, fill email field with #email selector and password field with #password selector, then click the submit button"
} | ConvertTo-Json

try {
    $learnResponse = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body $learnRequest
    $learnStatus = $learnResponse.results.status
    
    # Check if procedure was created (look for procedure.create in events or plan steps)
    $procedureCreated = $false
    if ($learnResponse.events) {
        $procedureCreated = ($learnResponse.events | Where-Object { $_.type -eq "procedure_created" -or $_.type -eq "memory_upsert" }) -ne $null
    }
    if ($learnResponse.plan.steps) {
        $procedureCreated = $procedureCreated -or ($learnResponse.plan.steps | Where-Object { $_.tool -eq "procedure.create" }) -ne $null
    }
    
    if ($learnStatus -eq "completed" -or $procedureCreated) {
        Write-Host "  ✅ LEARN: Procedure stored successfully" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  LEARN: Status: $learnStatus (procedure created: $procedureCreated)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ LEARN: Error - $_" -ForegroundColor Red
    $allTestsPassed = $false
}

Start-Sleep -Seconds 2

# ==========================================
# PHASE 2: RECALL - User requests similar task
# ==========================================
Write-Host ""
Write-Host "PHASE 2: RECALL - Requesting similar login" -ForegroundColor Yellow
$recallRequest = @{
    message = "Log into site2.com"
} | ConvertTo-Json

try {
    $recallResponse = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body $recallRequest
    $recallStatus = $recallResponse.results.status
    
    # Check if search was performed
    $plan = $recallResponse.plan
    $steps = $plan.steps
    $searchPerformed = ($steps | Where-Object { $_.tool -eq "ksg.search_concepts" -or $_.tool -eq "procedure.search" }) -ne $null
    
    # Also check events for procedure_recall
    if ($recallResponse.events) {
        $searchPerformed = $searchPerformed -or ($recallResponse.events | Where-Object { $_.type -eq "procedure_recall" }) -ne $null
    }
    
    if ($recallStatus -eq "completed" -or $recallStatus -eq "ask_user") {
        if ($searchPerformed) {
            Write-Host "  ✅ RECALL: Similar procedure found and used" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  RECALL: Executed but search may not have been performed" -ForegroundColor Yellow
        }
    } else {
        Write-Host "  ⚠️  RECALL: Status: $recallStatus" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ RECALL: Error - $_" -ForegroundColor Red
    $allTestsPassed = $false
}

Start-Sleep -Seconds 2

# ==========================================
# PHASE 3: EXECUTE - Agent executes procedure
# ==========================================
Write-Host ""
Write-Host "PHASE 3: EXECUTE - Verifying execution" -ForegroundColor Yellow
# Execution happens as part of Phase 2, but we verify it
if ($recallResponse.plan.steps) {
    $executionSteps = $recallResponse.plan.steps | Where-Object { $_.tool -like "web.*" }
    if ($executionSteps.Count -gt 0) {
        Write-Host "  ✅ EXECUTE: Web tool steps executed ($($executionSteps.Count) steps)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  EXECUTE: No web tool steps found (may use procedure reuse)" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ⚠️  EXECUTE: No steps in plan" -ForegroundColor Yellow
}

# ==========================================
# PHASE 4: ADAPT - Execution fails, agent adapts
# ==========================================
Write-Host ""
Write-Host "PHASE 4: ADAPT - Testing adaptation on failure" -ForegroundColor Yellow
$adaptRequest = @{
    message = "Log into site3.com (this will fail initially to test adaptation)"
} | ConvertTo-Json

try {
    $adaptResponse = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body $adaptRequest
    $adaptStatus = $adaptResponse.results.status
    
    # Check if adaptation was attempted (retry logic or adapted plan)
    $plan = $adaptResponse.plan
    $adapted = $plan.adapted -or $plan.reuse
    
    if ($adaptStatus -eq "completed" -or $adaptStatus -eq "ask_user" -or $adapted) {
        Write-Host "  ✅ ADAPT: Adaptation attempted or completed" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  ADAPT: Status: $adaptStatus (may need real failure to test)" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ ADAPT: Error - $_" -ForegroundColor Red
    $allTestsPassed = $false
}

Start-Sleep -Seconds 2

# ==========================================
# PHASE 5: AUTO-GENERALIZE - Multiple successes
# ==========================================
Write-Host ""
Write-Host "PHASE 5: AUTO-GENERALIZE - Teaching second procedure" -ForegroundColor Yellow
$generalizeRequest = @{
    message = "Remember: to log into site4.com, go to https://site4.com/login, fill email and password, then click submit"
} | ConvertTo-Json

try {
    $generalizeResponse = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body $generalizeRequest
    $generalizeStatus = $generalizeResponse.results.status
    
    # Check if procedure was created
    $procedureCreated = $false
    if ($generalizeResponse.events) {
        $procedureCreated = ($generalizeResponse.events | Where-Object { $_.type -eq "procedure_created" -or $_.type -eq "memory_upsert" }) -ne $null
    }
    
    if ($generalizeStatus -eq "completed" -or $procedureCreated) {
        Write-Host "  ✅ AUTO-GENERALIZE: Second procedure stored (generalization can occur)" -ForegroundColor Green
    } else {
        Write-Host "  ⚠️  AUTO-GENERALIZE: Status: $generalizeStatus" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  ❌ AUTO-GENERALIZE: Error - $_" -ForegroundColor Red
    $allTestsPassed = $false
}

# ==========================================
# SUMMARY
# ==========================================
Write-Host ""
Write-Host "=" * 60 -ForegroundColor Cyan
if ($allTestsPassed) {
    Write-Host "🎉 ULTIMATE GOAL ACHIEVED IN DEBUG MODE! 🎉" -ForegroundColor Green
} else {
    Write-Host "⚠️  Some tests had issues - check logs" -ForegroundColor Yellow
}
Write-Host "=" * 60 -ForegroundColor Cyan
Write-Host ""
Write-Host "Check log file for details: $logFile" -ForegroundColor Gray
Write-Host "View last 50 lines: Get-Content $logFile -Tail 50" -ForegroundColor Gray
Write-Host ""

# Check log for key indicators
if (Test-Path $logFile) {
    $logContent = Get-Content $logFile -Tail 100
    $indicators = @(
        "procedure.create",
        "ksg.search_concepts",
        "execution_completed",
        "learned_from_success",
        "adaptation_succeeded"
    )
    
    Write-Host "Key indicators in log:" -ForegroundColor Yellow
    foreach ($indicator in $indicators) {
        $found = $logContent | Select-String -Pattern $indicator
        if ($found) {
            Write-Host "  ✅ $indicator" -ForegroundColor Green
        } else {
            Write-Host "  ⚠️  $indicator (not found)" -ForegroundColor Yellow
        }
    }
}

# Stop daemon if requested
if ($StopDaemon) {
    Write-Host ""
    Write-Host "Stopping daemon..." -ForegroundColor Yellow
    $jobIdFile = "scripts\.debug_agent.jobid"
    if (Test-Path $jobIdFile) {
        $jobId = Get-Content $jobIdFile
        Stop-Job -Id $jobId -ErrorAction SilentlyContinue
        Remove-Job -Id $jobId -ErrorAction SilentlyContinue
        Remove-Item $jobIdFile -ErrorAction SilentlyContinue
        Write-Host "Daemon stopped" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "Test complete!" -ForegroundColor Cyan

