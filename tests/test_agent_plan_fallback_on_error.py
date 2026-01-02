import json
import pytest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient


class FailingOpenAIClient(FakeOpenAIClient):
    def chat(self, *args, **kwargs):
        raise RuntimeError("LLM chat failure")


def make_agent(fake_client):
    mem = MockMemoryTools()
    return PersonalAssistantAgent(
        mem,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=ProcedureBuilder(mem, embed_fn=lambda text: [0.1, 0.2]),
        openai_client=fake_client,
    )


def test_plan_falls_back_when_llm_errors():
    agent = make_agent(FailingOpenAIClient())
    result = agent.execute_request("please do something")
    assert result["plan"].get("fallback") is True or result["plan"].get("reuse") is True
    assert result["execution_results"]["status"] in {"no action taken", "completed", "ask_user"}
