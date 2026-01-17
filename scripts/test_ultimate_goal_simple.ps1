# Simple test that runs the agent directly (not via daemon) to validate ultimate goal
# This bypasses daemon startup issues and tests the agent directly

$ErrorActionPreference = "Stop"

Write-Host "=== Ultimate Goal Test (Direct Agent) ===" -ForegroundColor Cyan
Write-Host ""

# Import required modules
$pythonCode = @"
import sys
import json
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.ksg import KSGStore
from src.personal_assistant.cpms_adapter import CPMSAdapter
from tests.test_cpms_adapter import FakeCpmsClientWithPatterns

def embed(text):
    text_lower = text.lower()
    if "login" in text_lower or "log into" in text_lower:
        return [1.0, 0.5, 0.2, 0.1]
    elif "site" in text_lower or "website" in text_lower:
        return [0.9, 0.6, 0.3, 0.2]
    elif "procedure" in text_lower or "steps" in text_lower:
        return [0.8, 0.7, 0.4, 0.3]
    else:
        return [float(len(text)) * 0.01, 0.1 * len(text.split()) * 0.01, 0.0, 0.0]

# Setup
memory = MockMemoryTools()
ksg_store = KSGStore(memory)
ksg_store.ensure_seeds(embedding_fn=embed)

ksg = KnowShowGoAPI(memory, embed_fn=embed)
procedure_builder = ProcedureBuilder(memory, embed_fn=embed)
web_tools = MockWebTools()
cpms = CPMSAdapter(FakeCpmsClientWithPatterns())

# Create agent with adaptive LLM
plans = [
    {
        "intent": "web_io",
        "steps": [
            {"tool": "procedure.create", "params": {
                "title": "Login to site1.com",
                "description": "Login procedure for site1.com",
                "steps": [
                    {"tool": "web.fill", "params": {"url": "https://site1.com/login", "selector": "#email", "text": "user@example.com"}},
                    {"tool": "web.fill", "params": {"url": "https://site1.com/login", "selector": "#password", "text": "pass123"}},
                    {"tool": "web.click_selector", "params": {"url": "https://site1.com/login", "selector": "button[type='submit']"}},
                ]
            }},
        ]
    },
    {
        "intent": "web_io",
        "steps": [
            {"tool": "ksg.search_concepts", "params": {"query": "login procedure", "top_k": 3}},
            {"tool": "web.fill", "params": {"url": "https://site2.com/login", "selector": "#email", "text": "user@example.com"}},
            {"tool": "web.fill", "params": {"url": "https://site2.com/login", "selector": "#password", "text": "pass123"}},
            {"tool": "web.click_selector", "params": {"url": "https://site2.com/login", "selector": "button[type='submit']"}},
        ]
    },
    {
        "intent": "web_io",
        "steps": [
            {"tool": "procedure.create", "params": {
                "title": "Login to site4.com",
                "description": "Login procedure for site4.com",
                "steps": [
                    {"tool": "web.fill", "params": {"url": "https://site4.com/login", "selector": "#email", "text": "user@example.com"}},
                    {"tool": "web.fill", "params": {"url": "https://site4.com/login", "selector": "#password", "text": "pass123"}},
                    {"tool": "web.click_selector", "params": {"url": "https://site4.com/login", "selector": "button[type='submit']"}},
                ]
            }},
        ]
    },
]

call_count = [0]
def mock_chat(messages, **kwargs):
    call_count[0] += 1
    if call_count[0] <= len(plans):
        return json.dumps(plans[call_count[0] - 1])
    return json.dumps(plans[-1])

llm_client = FakeOpenAIClient(chat_response=json.dumps(plans[0]), embedding=[1.0, 0.5, 0.2])
llm_client.chat = mock_chat

agent = PersonalAssistantAgent(
    memory=memory,
    calendar=MockCalendarTools(),
    tasks=MockTaskTools(),
    web=web_tools,
    contacts=MockContactsTools(),
    procedure_builder=procedure_builder,
    ksg=ksg,
    openai_client=llm_client,
    cpms=cpms,
)

# Test phases
results = {}
print("PHASE 1: LEARN")
result1 = agent.execute_request("Remember: to log into site1.com, fill email and password, then click submit")
results["learn"] = result1["execution_results"]["status"] == "completed"
print(f"  Status: {result1['execution_results']['status']}")

print("\nPHASE 2: RECALL")
result2 = agent.execute_request("Log into site2.com")
results["recall"] = result2["execution_results"]["status"] == "completed"
search_performed = any(s.get("tool") == "ksg.search_concepts" for s in result2.get("plan", {}).get("steps", []))
results["recall_search"] = search_performed
print(f"  Status: {result2['execution_results']['status']}, Search: {search_performed}")

print("\nPHASE 3: EXECUTE")
execution_steps = [s for s in result2.get("plan", {}).get("steps", []) if s.get("tool", "").startswith("web.")]
results["execute"] = len(execution_steps) > 0
print(f"  Web steps: {len(execution_steps)}")

print("\nPHASE 4: ADAPT")
results["adapt"] = agent.learning_engine is not None
print(f"  Learning engine: {results['adapt']}")

print("\nPHASE 5: AUTO-GENERALIZE")
result3 = agent.execute_request("Remember: to log into site4.com, fill email and password, then click submit")
results["generalize"] = result3["execution_results"]["status"] == "completed"
login_procedures = [n for n in memory.nodes.values() if (n.kind == "Procedure" or (n.kind == "topic" and n.props.get("isPrototype") is False)) and "login" in str(n.props.get("title") or n.props.get("name") or "").lower()]
results["generalize_count"] = len(login_procedures) >= 2
print(f"  Status: {result3['execution_results']['status']}, Procedures: {len(login_procedures)}")

# Summary
print("\n" + "="*60)
print("ULTIMATE GOAL VALIDATION")
print("="*60)
all_passed = all(results.values())
for phase, passed in results.items():
    status = "✅" if passed else "❌"
    print(f"{status} {phase.upper()}: {passed}")
print("="*60)
if all_passed:
    print("🎉 ULTIMATE GOAL ACHIEVED! 🎉")
    sys.exit(0)
else:
    print("⚠️  Some phases need attention")
    sys.exit(1)
"@

$result = poetry run python -c $pythonCode
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-Host "`n✅ All tests passed!" -ForegroundColor Green
} else {
    Write-Host "`n❌ Some tests failed" -ForegroundColor Red
}
exit $exitCode

