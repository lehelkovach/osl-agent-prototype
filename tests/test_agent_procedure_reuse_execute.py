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
from src.personal_assistant.models import Provenance


def test_reuse_executes_stored_steps_without_llm_plan():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [0.1, 0.2])
    prov = Provenance(source="user", ts="now", confidence=1.0, trace_id="reuse-test")
    url = "http://local.test/login"
    builder.create_procedure(
        title="Stored Login",
        description="Stored login procedure",
        steps=[
            {"title": "web.get_dom", "tool": "web.get_dom", "payload": {"tool": "web.get_dom", "params": {"url": url}}},
            {
                "title": "web.fill",
                "tool": "web.fill",
                "payload": {
                    "tool": "web.fill",
                    "params": {"url": url, "selectors": {"username": "#user", "password": "#pass"}, "values": {"username": "alice", "password": "secret"}},
                },
            },
            {"title": "web.click_selector", "tool": "web.click_selector", "payload": {"tool": "web.click_selector", "params": {"url": url, "selector": "#submit"}}},
        ],
        provenance=prov,
    )
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=FakeOpenAIClient(chat_response=json.dumps({"intent": "inform", "steps": []}), embedding=[0.1, 0.2]),
    )

    res = agent.execute_request("Execute the stored login procedure")

    assert res["plan"].get("reuse") is True
    assert res["execution_results"]["status"] == "completed"
    methods = [h["method"] for h in agent.web.history]
    assert "GET_DOM" in methods and "FILL" in methods and "CLICK_SELECTOR" in methods
