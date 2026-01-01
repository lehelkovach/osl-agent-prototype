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
    return f"test_db_{uuid.uuid4().hex[:8]}"


def _create_memory_or_skip(db_name: str):
    try:
        return ArangoMemoryTools(
            db_name=db_name,
            nodes_collection="nodes",
            edges_collection="edges",
        )
    except Exception as exc:
        pytest.skip(f"Arango unavailable: {exc}")


def test_aql_query_person_by_name(require_arango_connection):
    load_dotenv(".env.local")
    load_dotenv()
    if not _required_env():
        pytest.skip("Arango connection env not set")

    db_name = _unique_db()
    memory = _create_memory_or_skip(db_name)
    prov = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace-aql-person")
    person = Node(
        kind="Person",
        labels=["fact", "person"],
        props={"name": "AQL Tester"},
        llm_embedding=[0.9, 0.1],
    )
    memory.upsert(person, prov)

    query = f"""
    FOR n IN {memory.nodes_collection_name}
      FILTER n.kind == @kind AND n.props.name == @name
      RETURN n
    """
    cursor = memory.db.aql.execute(
        query,
        bind_vars={"kind": "Person", "name": "AQL Tester"},
    )
    docs = list(cursor)
    assert len(docs) == 1
    assert docs[0]["uuid"] == person.uuid

    sys_db = memory.client.db("_system", username=memory.username, password=memory.password)
    sys_db.delete_database(db_name)


def test_aql_traversal_edges(require_arango_connection):
    load_dotenv(".env.local")
    load_dotenv()
    if not _required_env():
        pytest.skip("Arango connection env not set")

    db_name = _unique_db()
    memory = _create_memory_or_skip(db_name)
    prov = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace-aql-edge")
    node_a = Node(kind="Concept", labels=["a"], props={"name": "A"}, llm_embedding=[1, 0, 0])
    node_b = Node(kind="Concept", labels=["b"], props={"name": "B"}, llm_embedding=[0, 1, 0])
    memory.upsert(node_a, prov)
    memory.upsert(node_b, prov)
    edge = Edge(from_node=node_a.uuid, to_node=node_b.uuid, rel="linked_to", props={"w": 1.0})
    memory.upsert(edge, prov)

    query = f"""
    WITH {memory.nodes_collection_name}
    FOR v, e IN 1..1 OUTBOUND @start {memory.edges_collection_name}
      FILTER e.rel == @rel
      RETURN {{vertex: v, edge: e}}
    """
    cursor = memory.db.aql.execute(
        query,
        bind_vars={"start": f"{memory.nodes_collection_name}/{node_a.uuid}", "rel": "linked_to"},
    )
    items = list(cursor)
    assert len(items) == 1
    assert items[0]["vertex"]["uuid"] == node_b.uuid
    assert items[0]["edge"]["_from"].endswith(node_a.uuid)
    assert items[0]["edge"]["_to"].endswith(node_b.uuid)

    sys_db = memory.client.db("_system", username=memory.username, password=memory.password)
    sys_db.delete_database(db_name)
