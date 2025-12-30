import os
import uuid

import pytest

arango = pytest.importorskip("arango")

from src.personal_assistant.arango_memory import ArangoMemoryTools
from src.personal_assistant.models import Node, Provenance


def _required_env():
    return all(
        [
            os.getenv("ARANGO_URL"),
            os.getenv("ARANGO_USER"),
            os.getenv("ARANGO_PASSWORD"),
        ]
    )


@pytest.mark.skipif(not _required_env(), reason="Arango connection env not set")
def test_arango_memory_upsert_and_search():
    memory = ArangoMemoryTools(
        db_name=f"test_db_{uuid.uuid4().hex[:6]}",
        nodes_collection="nodes",
        edges_collection="edges",
    )
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
