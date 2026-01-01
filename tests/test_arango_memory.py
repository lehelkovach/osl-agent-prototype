import os
import uuid

import pytest
from dotenv import load_dotenv

arango = pytest.importorskip("arango")

from src.personal_assistant.arango_memory import ArangoMemoryTools
from src.personal_assistant.models import Node, Edge, Provenance


def _required_env():
    return all(
        [
            os.getenv("ARANGO_URL"),
            os.getenv("ARANGO_USER"),
            os.getenv("ARANGO_PASSWORD"),
        ]
    )


def _unique_db():
    return f"test_db_{uuid.uuid4().hex[:6]}"


def _create_memory_or_skip(db_name: str):
    try:
        return ArangoMemoryTools(
            db_name=db_name,
            nodes_collection="nodes",
            edges_collection="edges",
        )
    except Exception as exc:
        pytest.skip(f"Arango unavailable: {exc}")


def test_arango_memory_upsert_and_search(require_arango_connection):
    load_dotenv(".env.local")
    load_dotenv()
    if not _required_env():
        pytest.skip("Arango connection env not set")

    memory = _create_memory_or_skip(_unique_db())

    provenance = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace-arango")
    node = Node(
        kind="Person",
        labels=["tester"],
        props={"name": "Arango Tester"},
        llm_embedding=[1.0, 0.0, 0.0],
    )
    upsert = memory.upsert(node, provenance)
    assert upsert["status"] == "success"

    results = memory.search("tester", top_k=1, query_embedding=[1.0, 0.0, 0.0])
    assert len(results) == 1
    assert results[0]["uuid"] == node.uuid


def test_arango_edge_persistence_and_reload(require_arango_connection):
    load_dotenv(".env.local")
    load_dotenv()
    if not _required_env():
        pytest.skip("Arango connection env not set")

    db_name = _unique_db()
    memory = _create_memory_or_skip(db_name)
    prov = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace-arango-edge")
    node_a = Node(kind="Concept", labels=["a"], props={"name": "A"}, llm_embedding=[1, 0, 0])
    node_b = Node(kind="Concept", labels=["b"], props={"name": "B"}, llm_embedding=[0, 1, 0])
    memory.upsert(node_a, prov)
    memory.upsert(node_b, prov)
    edge = Edge(from_node=node_a.uuid, to_node=node_b.uuid, rel="linked_to", props={"w": 1.0})
    memory.upsert(edge, prov)

    edge_doc = memory.edges.get(edge.uuid)
    assert edge_doc["_from"].endswith(node_a.uuid)
    assert edge_doc["_to"].endswith(node_b.uuid)

    memory_reloaded = _create_memory_or_skip(db_name)
    results = memory_reloaded.search("A", top_k=1, query_embedding=[1, 0, 0])
    assert len(results) == 1
    assert results[0]["uuid"] == node_a.uuid

    sys_db = memory.client.db("_system", username=memory.username, password=memory.password)
    sys_db.delete_database(db_name)
