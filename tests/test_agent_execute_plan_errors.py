from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import MockCalendarTools, MockMemoryTools, MockTaskTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.openai_client import FakeOpenAIClient


class FailingWebTools:
    def get(self, **kwargs):
        raise RuntimeError("boom")


def _make_agent(web=None):
    return PersonalAssistantAgent(
        MockMemoryTools(),
        MockCalendarTools(),
        MockTaskTools(),
        web=web,
        openai_client=FakeOpenAIClient(chat_response="{}"),
    )


def _provenance() -> Provenance:
    return Provenance(
        source="user",
        ts=datetime.now(timezone.utc).isoformat(),
        confidence=1.0,
        trace_id="test-trace",
    )


def test_execute_plan_surfaces_tool_errors():
    agent = _make_agent(web=FailingWebTools())
    plan = {"intent": "test", "steps": [{"tool": "web.get", "params": {"url": "http://example.com"}}]}

    res = agent._execute_plan(plan, _provenance())

    assert res["status"] == "error"
    assert res["tool"] == "web.get"
    assert "boom" in res["error"]


def test_execute_plan_with_no_steps_returns_no_action():
    agent = _make_agent()
    plan = {"intent": "test", "steps": []}

    res = agent._execute_plan(plan, _provenance())

    assert res == {"status": "no action taken"}
