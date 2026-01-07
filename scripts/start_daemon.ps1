# PowerShell script to start the agent daemon on Windows
# Usage: .\scripts\start_daemon.ps1

$env:PYTHONUNBUFFERED = "1"
$DAEMON_HOST = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$DAEMON_PORT = if ($env:PORT) { $env:PORT } else { "8000" }
$LOG_LEVEL = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { "info" }
$LOGFILE = if ($env:AGENT_LOG_FILE) { $env:AGENT_LOG_FILE } else { "log_dump.txt" }

$args = @("--host", $DAEMON_HOST, "--port", $DAEMON_PORT, "--log-level", $LOG_LEVEL)
if ($env:DEBUG -eq "1" -or $env:DEBUG -eq "true") {
    $args += "--debug"
}
if ($env:AGENT_CONFIG) {
    $args += "--config"
    $args += $env:AGENT_CONFIG
}

Write-Host "Starting agent daemon on ${DAEMON_HOST}:${DAEMON_PORT}"
Write-Host "Logging to ${LOGFILE}"
Write-Host "Command: poetry run python -m src.personal_assistant.service $($args -join ' ')"

# Create a script block that redirects both stdout and stderr to the log file
$scriptBlock = {
    param($argsList, $logPath, $workingDir, $envVars)
    Set-Location $workingDir
    foreach ($key in $envVars.Keys) {
        [Environment]::SetEnvironmentVariable($key, $envVars[$key], "Process")
    }
    $env:PYTHONUNBUFFERED = "1"
    
    & poetry run python -m src.personal_assistant.service @argsList *>&1 | Tee-Object -FilePath $logPath -Append
}

# Prepare environment variables
$envVars = @{
    "PYTHONUNBUFFERED" = "1"
}
if ($env:USE_FAKE_OPENAI) { $envVars["USE_FAKE_OPENAI"] = $env:USE_FAKE_OPENAI }
if ($env:EMBEDDING_BACKEND) { $envVars["EMBEDDING_BACKEND"] = $env:EMBEDDING_BACKEND }
if ($env:DEBUG) { $envVars["DEBUG"] = $env:DEBUG }
if ($env:ARANGO_URL) { $envVars["ARANGO_URL"] = $env:ARANGO_URL }
if ($env:HOST) { $envVars["HOST"] = $env:HOST }
if ($env:PORT) { $envVars["PORT"] = $env:PORT }

# Start the process in a background job
$job = Start-Job -ScriptBlock $scriptBlock -ArgumentList (,$args), $LOGFILE, $PWD, $envVars

# Save job ID to file
$jobId = $job.Id
$jobId | Out-File -FilePath "scripts\.debug_agent.jobid" -NoNewline
Write-Host "Agent daemon started (Job ID: $jobId)"
Write-Host "To stop: Stop-Job -Id $jobId; Remove-Job -Id $jobId"
Write-Host "To view logs: Get-Content $LOGFILE -Wait -Tail 50"


