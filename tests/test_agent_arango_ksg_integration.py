import json
import os
import uuid

import pytest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.mock_tools import (
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)


@pytest.mark.skipif(
    os.getenv("ARANGO_URL", "") == "",
    reason="ARANGO_URL not set; skipping Arango integration",
)
def test_agent_recalls_concept_from_arango(require_arango_connection):
    """
    Integration: Arango-backed memory + KnowShowGo concept creation, then agent recall.
    """
    from src.personal_assistant.arango_memory import ArangoMemoryTools

    db_name = os.getenv("ARANGO_DB", "agent_memory_integration_test")
    memory = ArangoMemoryTools(
        db_name=db_name,
        url=os.getenv("ARANGO_URL"),
        username=os.getenv("ARANGO_USER", "root"),
        password=os.getenv("ARANGO_PASSWORD", ""),
        verify=True,
    )

    ksg = KnowShowGoAPI(memory)
    unique = str(uuid.uuid4())[:8]
    proto_uuid = ksg.create_prototype(
        name=f"TestProto-{unique}",
        description="Integration proto",
        context="integration",
        labels=["Prototype", "Integration"],
        embedding=[1.0, 0.0],
    )
    note_text = f"Integration note {unique}"
    ksg.create_concept(
        prototype_uuid=proto_uuid,
        json_obj={"name": f"Concept-{unique}", "note": note_text},
        embedding=[0.5, 0.1],
    )

    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}', embedding=[0.1, 0.2]),
    )

    res = agent.execute_request(f"What note do you have about Concept-{unique}?")
    # Expect the note, not a name recall
    assert note_text in res["plan"]["raw_llm"]


@pytest.mark.skipif(
    os.getenv("ARANGO_URL", "") == "",
    reason="ARANGO_URL not set; skipping Arango integration",
)
def test_agent_procedure_persistence_and_run_of_edge(require_arango_connection):
    """
    Integration: create a procedure via agent (Arango backend), then reuse it and ensure a run_of edge is stored.
    """
    from src.personal_assistant.arango_memory import ArangoMemoryTools

    memory = ArangoMemoryTools(
        db_name=os.getenv("ARANGO_DB", "agent_memory_integration_test"),
        url=os.getenv("ARANGO_URL"),
        username=os.getenv("ARANGO_USER", "root"),
        password=os.getenv("ARANGO_PASSWORD", ""),
        verify=True,
    )
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    fake_create = FakeOpenAIClient(
        chat_response=json.dumps(
            {
                "intent": "web_io",
                "steps": [
                    {
                        "tool": "procedure.create",
                        "params": {
                            "title": "Arango MultiStep",
                            "description": "Store in Arango",
                            "steps": [
                                {"tool": "web.get", "params": {"url": "http://example.com"}},
                                {"tool": "web.post", "params": {"url": "httpbin.org/post", "payload": {"hello": "world"}}},
                            ],
                        },
                    },
                    {"tool": "web.get", "params": {"url": "http://example.com"}},
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
        openai_client=fake_create,
    )
    res = agent.execute_request("create arango procedure")
    assert res["execution_results"]["status"] == "completed"

    procs = memory.search("Arango MultiStep", top_k=1, filters={"kind": "Procedure"}, query_embedding=[0.1, 0.2])
    assert procs
    proc_uuid = procs[0].get("uuid") or procs[0].get("_key")

    agent.openai_client.chat_response = json.dumps({"intent": "inform", "steps": []})
    res2 = agent.execute_request("run arango multistep")
    assert res2["plan"].get("reuse") is True

    # Inspect run_of edges by querying the edge collection
    run_of_edges = []
    cursor = memory.edges.all()
    for edge in cursor:
        if edge.get("rel") == "run_of" and edge.get("_to", "").endswith(proc_uuid):
            run_of_edges.append(edge)
    assert run_of_edges, "Expected at least one run_of edge pointing to the procedure"


@pytest.mark.skipif(
    os.getenv("ARANGO_URL", "") == "",
    reason="ARANGO_URL not set; skipping Arango integration",
)
def test_arango_stored_procedure_can_be_reconstructed_to_command_json(require_arango_connection):
    """
    Store a procedure in Arango via ProcedureBuilder, then reconstruct a commandtype=procedure JSON from stored nodes/edges.
    """
    from src.personal_assistant.arango_memory import ArangoMemoryTools

    memory = ArangoMemoryTools(
        db_name=os.getenv("ARANGO_DB", "agent_memory_integration_test"),
        url=os.getenv("ARANGO_URL"),
        username=os.getenv("ARANGO_USER", "root"),
        password=os.getenv("ARANGO_PASSWORD", ""),
        verify=True,
    )
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    steps_def = [
        {"title": "web.get", "payload": {"url": "http://example.com"}},
        {"title": "web.post", "payload": {"url": "http://example.com/api"}},
    ]
    proc = builder.create_procedure(
        title="Arango DAG",
        description="Reconstructable procedure",
        steps=steps_def,
        provenance=None,
    )
    proc_uuid = proc["procedure_uuid"]

    # Fetch has_step edges and reconstruct ordered steps
    edges = list(memory.edges.all())
    has_step_edges = [
        e for e in edges if e.get("rel") == "has_step" and e.get("_from", "").endswith(proc_uuid)
    ]
    assert has_step_edges
    has_step_edges.sort(key=lambda e: e.get("props", {}).get("order", 0))
    reconstructed_steps = []
    for e in has_step_edges:
        step_uuid = e.get("_to").split("/")[-1]
        step_doc = memory.nodes.get(step_uuid)
        payload = (step_doc.get("props") or {}).get("payload") or {}
        reconstructed_steps.append(
            {
                "commandtype": (step_doc.get("props") or {}).get("title"),
                "metadata": payload,
            }
        )

    cmd = {"commandtype": "procedure", "metadata": {"steps": reconstructed_steps}}
    assert cmd["metadata"]["steps"][0]["commandtype"] == "web.get"
    assert cmd["metadata"]["steps"][1]["commandtype"] == "web.post"
