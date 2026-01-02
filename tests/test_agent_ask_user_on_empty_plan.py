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


def test_empty_plan_prompts_user():
    # Return an empty plan to force ask-user path
    fake = FakeOpenAIClient(chat_response=json.dumps({"intent": "inform", "steps": []}), embedding=[0.1, 0.2])
    agent = PersonalAssistantAgent(
        MockMemoryTools(),
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=ProcedureBuilder(MockMemoryTools(), embed_fn=lambda text: [0.1, 0.2]),
        openai_client=fake,
    )

    res = agent.execute_request("help")

    assert res["execution_results"]["status"] == "ask_user"
    assert "instructions" in res["plan"]["raw_llm"]
