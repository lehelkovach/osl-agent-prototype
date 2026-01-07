# Live test script for comprehensive learning workflow
# Tests agent learning, recall, adaptation, and generalization with real services

param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$LogFile = "learning_workflow.log",
    [switch]$UseRealServices = $false
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] $Message"
    Add-Content -Path $LogFile -Value "[$timestamp] $Message"
}

function Send-ChatMessage {
    param(
        [string]$Message,
        [int]$TimeoutSeconds = 60
    )
    
    Write-Log "Sending: $Message"
    
    $body = @{
        message = $Message
    } | ConvertTo-Json
    
    try {
        $response = Invoke-RestMethod -Uri "$BaseUrl/chat" `
            -Method POST `
            -Body $body `
            -ContentType "application/json" `
            -TimeoutSec $TimeoutSeconds
        
        $status = $response.results.status
        Write-Log "Response status: $status"
        
        if ($response.plan) {
            $stepsCount = $response.plan.steps.Count
            $reuse = $response.plan.reuse
            Write-Log "Plan: $stepsCount steps, reuse=$reuse"
        }
        
        return $response
    }
    catch {
        Write-Log "Error: $_"
        return $null
    }
}

function Wait-ForDaemon {
    param([int]$MaxWaitSeconds = 30)
    
    $waited = 0
    while ($waited -lt $MaxWaitSeconds) {
        try {
            $response = Invoke-RestMethod -Uri "$BaseUrl/health" -Method GET -TimeoutSec 2
            if ($response.status -eq "ok") {
                Write-Log "Daemon is ready"
                return $true
            }
        }
        catch {
            Start-Sleep -Seconds 2
            $waited += 2
        }
    }
    
    Write-Log "Daemon not ready after $MaxWaitSeconds seconds"
    return $false
}

function Test-LearningWorkflow {
    Write-Log "=== Starting Comprehensive Learning Workflow Test ==="
    
    # Check daemon
    if (-not (Wait-ForDaemon)) {
        Write-Log "ERROR: Daemon not available"
        return $false
    }
    
    $testResults = @{
        Phase1_Learn = $false
        Phase2_Recall = $false
        Phase3_Adapt = $false
        Phase4_Generalize = $false
    }
    
    # Phase 1: Learn procedure from chat
    Write-Log "--- Phase 1: Learning Procedure ---"
    $testUrl = "file:///C:/Users/lehel/OneDrive/development/source/osl-agent-prototype/tests/fixtures/login_generate.html?page=1"
    $msg1 = "Go to the login form test page at $testUrl and login with email test@example.com and password testpass123"
    
    $result1 = Send-ChatMessage -Message $msg1 -TimeoutSeconds 90
    if ($result1 -and $result1.results.status -eq "completed") {
        $testResults.Phase1_Learn = $true
        Write-Log "✓ Phase 1 PASSED: Procedure learned"
    }
    else {
        Write-Log "✗ Phase 1 FAILED: Status = $($result1.results.status)"
    }
    
    Start-Sleep -Seconds 3
    
    # Phase 2: Recall and adapt for similar page
    Write-Log "--- Phase 2: Recall and Adapt ---"
    $testUrl2 = "file:///C:/Users/lehel/OneDrive/development/source/osl-agent-prototype/tests/fixtures/login_generate.html?page=2"
    $msg2 = "This is a similar login page at $testUrl2, login here with the same credentials"
    
    $result2 = Send-ChatMessage -Message $msg2 -TimeoutSeconds 90
    if ($result2) {
        $status2 = $result2.results.status
        if ($status2 -eq "completed") {
            $testResults.Phase2_Recall = $true
            Write-Log "✓ Phase 2 PASSED: Procedure recalled and adapted"
        }
        elseif ($status2 -eq "ask_user") {
            Write-Log "→ Phase 2: Agent asked for help (expected for adaptation)"
            # Provide guidance
            $guidance = "The email field selector is #username, password is #pass, and submit button is #login-btn"
            $result2b = Send-ChatMessage -Message $guidance -TimeoutSeconds 90
            if ($result2b -and $result2b.results.status -eq "completed") {
                $testResults.Phase2_Recall = $true
                Write-Log "✓ Phase 2 PASSED: Adapted with user guidance"
            }
        }
        else {
            Write-Log "✗ Phase 2 FAILED: Status = $status2"
        }
    }
    
    Start-Sleep -Seconds 3
    
    # Phase 3: Test adaptation after failure (multiple tries)
    Write-Log "--- Phase 3: Adaptation After Failure ---"
    $testUrl3 = "file:///C:/Users/lehel/OneDrive/development/source/osl-agent-prototype/tests/fixtures/login_generate.html?page=3"
    $msg3 = "Login to $testUrl3 with the same credentials"
    
    $maxTries = 3
    $tryCount = 0
    $success = $false
    
    while ($tryCount -lt $maxTries -and -not $success) {
        $tryCount++
        Write-Log "Attempt $tryCount of $maxTries"
        
        $result3 = Send-ChatMessage -Message $msg3 -TimeoutSeconds 90
        if ($result3) {
            $status3 = $result3.results.status
            if ($status3 -eq "completed") {
                $success = $true
                $testResults.Phase3_Adapt = $true
                Write-Log "✓ Phase 3 PASSED: Adapted after $tryCount attempt(s)"
            }
            elseif ($status3 -eq "ask_user" -and $tryCount -lt $maxTries) {
                Write-Log "→ Agent asked for help, providing guidance..."
                $guidance3 = "For page 3, the email field is input[name='user_email'], password is input[name='user_pass'], and submit is input[value='Sign In']"
                $result3b = Send-ChatMessage -Message $guidance3 -TimeoutSeconds 90
                if ($result3b -and $result3b.results.status -eq "completed") {
                    $success = $true
                    $testResults.Phase3_Adapt = $true
                    Write-Log "✓ Phase 3 PASSED: Adapted with guidance after $tryCount attempt(s)"
                }
            }
        }
        
        if (-not $success) {
            Start-Sleep -Seconds 2
        }
    }
    
    if (-not $success) {
        Write-Log "✗ Phase 3 FAILED: Could not adapt after $maxTries attempts"
    }
    
    # Phase 4: Check for generalization
    Write-Log "--- Phase 4: Generalization Check ---"
    # After multiple successful adaptations, check if agent can generalize
    $msg4 = "Login to another similar login form page"
    $result4 = Send-ChatMessage -Message $msg4 -TimeoutSeconds 90
    if ($result4 -and $result4.results.status -eq "completed") {
        $testResults.Phase4_Generalize = $true
        Write-Log "✓ Phase 4 PASSED: Agent can handle similar forms"
    }
    else {
        Write-Log "→ Phase 4: Generalization not yet triggered (may need more exemplars)"
    }
    
    # Summary
    Write-Log "=== Test Results Summary ==="
    foreach ($phase in $testResults.Keys) {
        $status = if ($testResults[$phase]) { "PASS" } else { "FAIL" }
        Write-Log "$phase : $status"
    }
    
    $allPassed = ($testResults.Values | Where-Object { $_ -eq $true }).Count -eq $testResults.Count
    return $allPassed
}

# Main execution
try {
    $success = Test-LearningWorkflow
    if ($success) {
        Write-Log "=== All tests PASSED ==="
        exit 0
    }
    else {
        Write-Log "=== Some tests FAILED ==="
        exit 1
    }
}
catch {
    Write-Log "ERROR: $_"
    exit 1
}

