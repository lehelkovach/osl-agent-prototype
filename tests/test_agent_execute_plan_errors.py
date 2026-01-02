import json
from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import MockCalendarTools, MockMemoryTools, MockTaskTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.openai_client import FakeOpenAIClient


class FailingWebTools:
    def get(self, **kwargs):
        raise RuntimeError("boom")


class SequentialFakeOpenAIClient(FakeOpenAIClient):
    def __init__(self, responses):
        super().__init__(chat_response=responses[0])
        self.responses = list(responses)

    def chat(self, messages, temperature: float = 0.0, response_format=None):
        # Pop through the provided responses; reuse last if exhausted
        if self.responses:
            return self.responses.pop(0)
        return super().chat(messages, temperature=temperature, response_format=response_format)


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


def test_execute_request_adapts_after_tool_error():
    # First plan will fail on web.get, second plan will create a task successfully.
    first_plan = {"intent": "test", "steps": [{"tool": "web.get", "params": {"url": "http://bad"}}]}
    second_plan = {
        "intent": "test",
        "steps": [
            {
                "tool": "tasks.create",
                "params": {"title": "fixed", "due": None, "priority": 3, "notes": "", "links": []},
            }
        ],
    }
    openai = SequentialFakeOpenAIClient(
        responses=[json.dumps(first_plan), json.dumps(second_plan)]
    )
    agent = PersonalAssistantAgent(
        MockMemoryTools(),
        MockCalendarTools(),
        MockTaskTools(),
        web=FailingWebTools(),
        openai_client=openai,
    )

    result = agent.execute_request("please do the thing")

    assert result["plan"].get("adapted") is True
    assert result["execution_results"]["status"] == "completed"
    # The second plan should have been executed (tasks.create), not the failing web.get.
    steps = result["execution_results"].get("steps", [])
    assert steps and steps[0].get("status") == "success"
