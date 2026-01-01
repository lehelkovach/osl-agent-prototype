import json
from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.openai_client import FakeOpenAIClient


def _prov():
    return Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "trace-assoc")


def test_association_edge_created_and_retrieved():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    a = Node(kind="Concept", labels=["a"], props={"title": "Source"})
    b = Node(kind="Concept", labels=["b"], props={"title": "Target"})
    memory.upsert(a, _prov(), embedding_request=True)
    memory.upsert(b, _prov(), embedding_request=True)

    edge = Edge(from_node=a.uuid, to_node=b.uuid, rel="associated_with", props={"strength": 1})
    memory.upsert(edge, _prov(), embedding_request=False)

    # Verify stored
    assert edge.uuid in memory.edges
    stored = memory.edges[edge.uuid]
    assert stored.from_node == a.uuid
    assert stored.to_node == b.uuid
    assert stored.rel == "associated_with"


def test_recall_strength_counter_increments():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    concept = Node(kind="Concept", labels=["fact"], props={"note": "hello"})
    memory.upsert(concept, _prov(), embedding_request=True)

    # Simulate a recall by updating props
    node = memory.nodes[concept.uuid]
    node.props["recall_count"] = node.props.get("recall_count", 0) + 1
    memory.upsert(node, _prov(), embedding_request=False)
    node = memory.nodes[concept.uuid]
    node.props["recall_count"] = node.props.get("recall_count", 0) + 1
    memory.upsert(node, _prov(), embedding_request=False)

    assert memory.nodes[concept.uuid].props["recall_count"] == 2


def test_procedure_to_credential_association_and_recall():
    memory = MockMemoryTools()
    builder = ProcedureBuilder(memory, embed_fn=lambda text: [len(text), 0.1])
    proc = builder.create_procedure(
        title="Login Flow",
        description="Login procedure",
        steps=[{"title": "web.get", "payload": {"url": "http://example.com/login"}}],
        provenance=_prov(),
    )
    cred = Node(kind="Credential", labels=["vault"], props={"username": "u", "password": "p"})
    memory.upsert(cred, _prov(), embedding_request=True)
    edge = Edge(from_node=proc["procedure_uuid"], to_node=cred.uuid, rel="uses_credential", props={})
    memory.upsert(edge, _prov(), embedding_request=False)

    # Recall query should surface procedure reuse path and not ignore the association
    fake_plan = json.dumps({"intent": "inform", "steps": []})
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        procedure_builder=builder,
        openai_client=FakeOpenAIClient(chat_response=fake_plan, embedding=[0.1, 0.2]),
    )
    res = agent.execute_request("Run the login flow")
    assert res["plan"].get("reuse") is True
    assert res["plan"]["steps"][0]["tool"] == "procedure.search"
