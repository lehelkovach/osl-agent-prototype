# End-to-end live test script for continual learning
# Demonstrates the agent learning through continual input, LLM reasoning, and transfer learning

param(
    [string]$BaseUrl = "http://localhost:8000",
    [switch]$UseLiveServices = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=== E2E Continual Learning Test ===" -ForegroundColor Cyan
Write-Host ""

# Test 1: Learn from failure with LLM reasoning
Write-Host "Test 1: Learning from failure with LLM reasoning" -ForegroundColor Yellow
$response1 = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body (@{
    message = "Login to example.com (use wrong selector first to trigger learning)"
} | ConvertTo-Json)

Write-Host "Response 1 Status: $($response1.execution_results.status)" -ForegroundColor $(if ($response1.execution_results.status -eq "completed") { "Green" } else { "Yellow" })
Write-Host "Trace ID: $($response1.plan.trace_id)" -ForegroundColor Gray
$traceId1 = $response1.plan.trace_id

Start-Sleep -Seconds 2

# Test 2: Transfer learning
Write-Host ""
Write-Host "Test 2: Transfer learning to similar site" -ForegroundColor Yellow
$response2 = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body (@{
    message = "Login to newsite.com (should use knowledge from example.com)"
} | ConvertTo-Json)

Write-Host "Response 2 Status: $($response2.execution_results.status)" -ForegroundColor $(if ($response2.execution_results.status -eq "completed") { "Green" } else { "Yellow" })

Start-Sleep -Seconds 2

# Test 3: User feedback
Write-Host ""
Write-Host "Test 3: Learning from user feedback" -ForegroundColor Yellow
$response3 = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body (@{
    message = "The selector should be #username"
    feedback = "The email field selector should be #username, not #email"
    trace_id = $traceId1
} | ConvertTo-Json)

Write-Host "Response 3 Status: $($response3.execution_results.status)" -ForegroundColor $(if ($response3.execution_results.status -eq "completed") { "Green" } else { "Yellow" })

Start-Sleep -Seconds 2

# Test 4: Survey answer reuse
Write-Host ""
Write-Host "Test 4: Survey answer reuse" -ForegroundColor Yellow
$response4 = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body (@{
    message = "Fill out this survey at https://example.com/survey1 - favorite language is Python, 5 years experience"
} | ConvertTo-Json)

Write-Host "Response 4 Status: $($response4.execution_results.status)" -ForegroundColor $(if ($response4.execution_results.status -eq "completed") { "Green" } else { "Yellow" })

Start-Sleep -Seconds 2

# Test 5: Reuse survey answers
Write-Host ""
Write-Host "Test 5: Reusing survey answers for similar survey" -ForegroundColor Yellow
$response5 = Invoke-RestMethod -Uri "$BaseUrl/chat" -Method POST -ContentType "application/json" -Body (@{
    message = "Fill out this similar survey at https://example.com/survey2 (should remember Python and 5 years)"
} | ConvertTo-Json)

Write-Host "Response 5 Status: $($response5.execution_results.status)" -ForegroundColor $(if ($response5.execution_results.status -eq "completed") { "Green" } else { "Yellow" })

Write-Host ""
Write-Host "=== E2E Test Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Check the agent logs to see:" -ForegroundColor Yellow
Write-Host "  - LLM reasoning about failures" -ForegroundColor Gray
Write-Host "  - Transfer learning from similar cases" -ForegroundColor Gray
Write-Host "  - Knowledge accumulation" -ForegroundColor Gray
Write-Host "  - User feedback integration" -ForegroundColor Gray
Write-Host "  - Survey answer reuse" -ForegroundColor Gray

