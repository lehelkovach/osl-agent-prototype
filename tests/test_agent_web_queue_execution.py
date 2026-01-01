import json

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
    MockWebTools,
    MockShellTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient


def test_web_plan_executes_and_records():
    # Fake LLM returns a concrete web plan
    plan = {
        "intent": "web_io",
        "steps": [
            {"tool": "web.get_dom", "params": {"url": "https://example.com"}, "comment": "Fetch DOM"},
            {"tool": "web.screenshot", "params": {"url": "https://example.com"}, "comment": "Capture page"},
        ],
    }
    fake_llm = FakeOpenAIClient(chat_response=json.dumps(plan), embedding=[0.1, 0.2, 0.3])
    web = MockWebTools()
    agent = PersonalAssistantAgent(
        memory=MockMemoryTools(),
        calendar=MockCalendarTools(),
        tasks=MockTaskTools(),
        contacts=MockContactsTools(),
        web=web,
        shell=MockShellTools(),
        procedure_builder=None,
        openai_client=fake_llm,
    )

    result = agent.execute_request("open example and capture it")

    # Plan should come from fake LLM, not fallback
    assert result["plan"]["intent"] == "web_io"
    assert result["plan"].get("fallback") is False or result["plan"].get("fallback") is None

    # Both web calls should have executed
    methods = [h["method"] for h in web.history]
    assert "GET_DOM" in methods
    assert "SCREENSHOT" in methods

    # Execution results should carry trace_id and success
    exec_res = result["execution_results"]
    assert exec_res["status"] == "completed"
    steps = exec_res.get("steps", [])
    assert len(steps) == 2
    assert any(step.get("url") == "https://example.com" for step in steps)
