import json

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient


class FailingWeb:
    def get(self, **kwargs):
        raise RuntimeError("boom")


def test_execution_error_prompts_user():
    fake_plan = FakeOpenAIClient(
        chat_response=json.dumps({"intent": "inform", "steps": [{"tool": "web.get", "params": {"url": "http://x"}}]}),
        embedding=[0.1, 0.2],
    )
    mem = MockMemoryTools()
    agent = PersonalAssistantAgent(
        mem,
        MockCalendarTools(),
        MockTaskTools(),
        web=FailingWeb(),
        contacts=MockContactsTools(),
        procedure_builder=ProcedureBuilder(mem, embed_fn=lambda text: [0.1, 0.2]),
        openai_client=fake_plan,
    )

    res = agent.execute_request("try to get a page")

    assert res["execution_results"]["status"] == "ask_user"
    assert "error" in res["plan"]["raw_llm"]
