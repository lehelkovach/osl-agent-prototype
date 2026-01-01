import pytest
from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.models import Provenance


def _make_agent():
    mem = MockMemoryTools()
    proc = ProcedureBuilder(mem, embed_fn=lambda text: [0.1, 0.2])
    agent = PersonalAssistantAgent(
        memory=mem,
        calendar=MockCalendarTools(),
        tasks=MockTaskTools(),
        contacts=MockContactsTools(),
        procedure_builder=proc,
        openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}', embedding=[0.1, 0.2]),
    )
    return agent, mem


def test_person_name_roundtrip_recall():
    agent, mem = _make_agent()
    prov = Provenance(
        source="user",
        ts=datetime.now(timezone.utc).isoformat(),
        confidence=1.0,
        trace_id="test-trace",
    )
    # Store the fact
    res = agent._remember_fact(
        {"text": "remember my name is Lehel", "kind": "Concept", "props": {"note": "remember my name is Lehel"}},
        prov,
    )
    assert res["status"] == "success"
    # Ensure a Name concept was created alongside Person
    kinds = {n.kind for n in mem.nodes.values()}
    assert "Person" in kinds
    assert "Name" in kinds
    # Recall
    recall_results = mem.search("what is my name", top_k=10, query_embedding=[0.1, 0.2])
    answer = agent._answer_from_memory("inform", recall_results)
    assert answer == "Your name is Lehel."
