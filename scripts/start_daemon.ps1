# PowerShell script to start the agent daemon on Windows
# Usage: .\scripts\start_daemon.ps1

$env:PYTHONUNBUFFERED = "1"
$HOST = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$PORT = if ($env:PORT) { $env:PORT } else { "8000" }
$LOG_LEVEL = if ($env:LOG_LEVEL) { $env:LOG_LEVEL } else { "info" }
$LOGFILE = if ($env:AGENT_LOG_FILE) { $env:AGENT_LOG_FILE } else { "log_dump.txt" }

$args = @("--host", $HOST, "--port", $PORT, "--log-level", $LOG_LEVEL)
if ($env:DEBUG -eq "1" -or $env:DEBUG -eq "true") {
    $args += "--debug"
}
if ($env:AGENT_CONFIG) {
    $args += "--config"
    $args += $env:AGENT_CONFIG
}

Write-Host "Starting agent daemon on ${HOST}:${PORT}"
Write-Host "Logging to ${LOGFILE}"
Write-Host "Command: poetry run python -m src.personal_assistant.service $($args -join ' ')"

# Start the process in the background
$job = Start-Job -ScriptBlock {
    param($args)
    Set-Location $using:PWD
    $env:PYTHONUNBUFFERED = "1"
    poetry run python -m src.personal_assistant.service $args 2>&1 | Tee-Object -FilePath $using:LOGFILE -Append
} -ArgumentList $args

Write-Host "Agent daemon started (Job ID: $($job.Id))"
Write-Host "To stop: Stop-Job -Id $($job.Id); Remove-Job -Id $($job.Id)"
Write-Host "To view logs: Get-Content $LOGFILE -Wait -Tail 50"

# Save job ID to file for later reference
$job.Id | Out-File -FilePath "scripts\.debug_agent.jobid" -NoNewline


