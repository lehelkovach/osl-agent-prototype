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
from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.openai_client import FakeOpenAIClient


def _prov():
    return Provenance(source="user", ts="now", confidence=1.0, trace_id="test-trace")


def test_recall_prefers_procedure_over_person_note():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    # Seed a name/person
    name = Node(kind="Name", labels=["fact"], props={"name": "Lehel"})
    memory.upsert(name, _prov(), embedding_request=True)
    # Seed a procedure
    builder.create_procedure(
        title="MultiStep Demo",
        description="Procedure to GET and screenshot example.com",
        steps=[{"title": "web.get", "payload": {"url": "http://example.com"}}],
        provenance=_prov(),
    )

    # Fake plan to avoid LLM: agent will take the memory answer path if intent=inform
    fake_client = FakeOpenAIClient(chat_response=json.dumps({"intent": "inform", "steps": []}), embedding=[0.1, 0.2])
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=fake_client,
    )

    res = agent.execute_request("Recall the steps of MultiStep Demo and execute them.")
    # Should route to procedure reuse (procedure.search) instead of answering with the name
    assert res["plan"].get("reuse") is True
    assert res["plan"]["steps"][0]["tool"] == "procedure.search"
    assert res["execution_results"]["status"] == "completed"


def test_store_and_recall_note_memory_remember():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    fake_remember = FakeOpenAIClient(
        chat_response=json.dumps(
            {
                "intent": "remember",
                "steps": [
                    {
                        "tool": "memory.remember",
                        "params": {
                            "text": "Credentials for page=1 are user test@example.com / carrot123",
                            "kind": "Concept",
                            "props": {"note": "Credentials for page=1 are user test@example.com / carrot123"},
                        },
                    }
                ],
            }
        ),
        embedding=[0.1, 0.2],
    )
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=fake_remember,
    )
    res = agent.execute_request("Remember page=1 credentials")
    assert res["execution_results"]["status"] == "completed"
    # Now query recall and expect the note, not the name
    fake_recall = FakeOpenAIClient(chat_response=json.dumps({"intent": "inform", "steps": []}), embedding=[0.1, 0.2])
    agent.openai_client = fake_recall
    res2 = agent.execute_request("What note do you have about page=1 credentials?")
    assert "page=1" in res2["plan"]["raw_llm"]
