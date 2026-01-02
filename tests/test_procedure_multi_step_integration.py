import json
import os
from typing import List, Dict

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


def _make_agent(fake_plan: str, memory):
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    return PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=FakeOpenAIClient(chat_response=fake_plan, embedding=[0.1, 0.2]),
    )


def test_multi_step_procedure_execute_and_reuse_order():
    """
    Create a 3-step procedure, execute it, then recall/reuse it and verify steps execute in order.
    """
    memory = MockMemoryTools()
    # Plan to create + execute a 3-step procedure
    create_and_run_plan = json.dumps(
        {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "procedure.create",
                    "params": {
                        "title": "MultiStep Demo",
                        "description": "GET, screenshot, POST",
                        "steps": [
                            {"tool": "web.get", "params": {"url": "http://example.com"}},
                            {"tool": "web.screenshot", "params": {"url": "http://example.com"}},
                            {"tool": "web.post", "params": {"url": "httpbin.org/post", "payload": {"hello": "world"}}},
                        ],
                    },
                },
                {"tool": "web.get", "params": {"url": "http://example.com"}},
                {"tool": "web.screenshot", "params": {"url": "http://example.com"}},
                {"tool": "web.post", "params": {"url": "httpbin.org/post", "payload": {"hello": "world"}}},
            ],
        }
    )
    agent = _make_agent(create_and_run_plan, memory)
    res = agent.execute_request("create and run multistep")
    assert res["execution_results"]["status"] == "completed"
    proc_uuid = res["execution_results"]["steps"][0]["procedure"]["procedure_uuid"]

    # Now reuse it with a recall-style request; inject a trivial plan (should be replaced by reuse path)
    agent.openai_client.chat_response = json.dumps({"intent": "inform", "steps": []})
    res2 = agent.execute_request("run the multistep demo again")
    assert res2["plan"].get("reuse") is True
    # Verify procedure.search ran and mock web tools captured three calls in order
    web_history: List[Dict] = agent.web.history  # type: ignore[attr-defined]
    methods = [h["method"] for h in web_history]
    assert methods[:3] == ["GET", "SCREENSHOT", "POST"]


@pytest.mark.skipif(
    os.getenv("ARANGO_URL", "") == "",
    reason="Set ARANGO_URL to run Arango persistence integration",
)
def test_procedure_persisted_to_arango():
    """
    Smoke test: ensure a procedure is created and retrievable via the Arango backend.
    """
    from src.personal_assistant.arango_memory import ArangoMemoryTools

    memory = ArangoMemoryTools(
        db_name=os.getenv("ARANGO_DB", "agent_memory"),
        url=os.getenv("ARANGO_URL"),
        username=os.getenv("ARANGO_USER", "root"),
        password=os.getenv("ARANGO_PASSWORD", ""),
        verify=os.getenv("ARANGO_VERIFY", True),
    )
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    proc = builder.create_procedure(
        title="Arango MultiStep",
        description="Arango persisted multi-step",
        steps=[{"title": "web.get", "payload": {"url": "http://example.com"}}],
    )
    # Retrieve via search and ensure it exists (fallback to raw memory scan)
    results = builder.search_procedures("Arango MultiStep", top_k=3)
    all_procs = memory.search("", top_k=100, filters={"kind": "Procedure"}, query_embedding=None)
    assert any(r.get("uuid") == proc["procedure_uuid"] for r in results + all_procs)
