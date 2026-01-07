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

# Start the process in the background using Start-Process for better output handling
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = "poetry"
$processInfo.Arguments = "run python -m src.personal_assistant.service $($args -join ' ')"
$processInfo.WorkingDirectory = $PWD
$processInfo.UseShellExecute = $false
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true
$processInfo.CreateNoWindow = $true

# Set environment variables
$processInfo.EnvironmentVariables["PYTHONUNBUFFERED"] = "1"
if ($env:USE_FAKE_OPENAI) { $processInfo.EnvironmentVariables["USE_FAKE_OPENAI"] = $env:USE_FAKE_OPENAI }
if ($env:EMBEDDING_BACKEND) { $processInfo.EnvironmentVariables["EMBEDDING_BACKEND"] = $env:EMBEDDING_BACKEND }
if ($env:DEBUG) { $processInfo.EnvironmentVariables["DEBUG"] = $env:DEBUG }
if ($env:ARANGO_URL) { $processInfo.EnvironmentVariables["ARANGO_URL"] = $env:ARANGO_URL }
if ($env:HOST) { $processInfo.EnvironmentVariables["HOST"] = $env:HOST }
if ($env:PORT) { $processInfo.EnvironmentVariables["PORT"] = $env:PORT }

$process = New-Object System.Diagnostics.Process
$process.StartInfo = $processInfo

# Redirect output to log file
$process.add_OutputDataReceived({
    param($sender, $e)
    if ($e.Data) {
        Add-Content -Path $LOGFILE -Value $e.Data -Encoding utf8
    }
})
$process.add_ErrorDataReceived({
    param($sender, $e)
    if ($e.Data) {
        Add-Content -Path $LOGFILE -Value $e.Data -Encoding utf8
    }
})

$process.Start() | Out-Null
$process.BeginOutputReadLine()
$process.BeginErrorReadLine()

# Save job ID to file
$jobId = $job.Id
$jobId | Out-File -FilePath "scripts\.debug_agent.jobid" -NoNewline
Write-Host "Agent daemon started (Job ID: $jobId)"
Write-Host "To stop: Stop-Job -Id $jobId; Remove-Job -Id $jobId"
Write-Host "To view logs: Get-Content $LOGFILE -Wait -Tail 50"


