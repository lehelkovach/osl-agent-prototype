import json

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


def test_low_confidence_triggers_ask_user():
    # Simulate a plan with explicit low confidence metadata
    plan_json = {
        "intent": "inform",
        "confidence": 0.5,
        "steps": [{"tool": "web.get", "params": {"url": "http://example.com"}}],
    }
    fake = FakeOpenAIClient(chat_response=json.dumps(plan_json), embedding=[0.1, 0.2])
    agent = PersonalAssistantAgent(
        MockMemoryTools(),
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=ProcedureBuilder(MockMemoryTools(), embed_fn=lambda text: [0.1, 0.2]),
        openai_client=fake,
    )

    res = agent.execute_request("Do something low confidence")

    assert res["execution_results"]["status"] == "ask_user"
    assert "approval" in res["plan"]["raw_llm"]
