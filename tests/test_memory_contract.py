import os
from datetime import datetime, timezone

import pytest

from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.networkx_memory import NetworkXMemoryTools


def _backend_factories():
    """
    Returns (name, factory) pairs for available MemoryTools implementations.
    Only MockMemoryTools is enabled by default; others opt-in via env flags.
    """
    backends = [
        ("mock", lambda: MockMemoryTools()),
        ("networkx", lambda: NetworkXMemoryTools()),
    ]

    if os.getenv("TEST_CHROMA", "0").lower() in ("1", "true", "yes"):
        try:
            from src.personal_assistant.chroma_memory import ChromaMemoryTools

            backends.append(
                (
                    "chroma",
                    lambda: ChromaMemoryTools(
                        path=".chroma-contract",
                        collection_name="memory_contract",
                        embedding_dim=2,
                    ),
                )
            )
        except Exception:
            pass

    if os.getenv("TEST_ARANGO", "0").lower() in ("1", "true", "yes"):
        try:
            from src.personal_assistant.arango_memory import ArangoMemoryTools

            backends.append(
                (
                    "arango",
                    lambda: ArangoMemoryTools(
                        db_name="agent_memory_contract",
                        verify=os.getenv("ARANGO_VERIFY", True),
                    ),
                )
            )
        except Exception:
            pass

    return backends


def _to_dict(item):
    return item if isinstance(item, dict) else item.__dict__


def _uuid_of(item):
    data = _to_dict(item)
    return data.get("uuid") or data.get("_key")


@pytest.fixture(params=_backend_factories(), ids=lambda p: p[0])
def memory_backend(request):
    name, factory = request.param
    return name, factory()


def _prov():
    return Provenance(
        source="test",
        ts=datetime.now(timezone.utc).isoformat(),
        confidence=1.0,
        trace_id="memory-contract",
    )


def test_upsert_and_filter_by_kind(memory_backend):
    _, memory = memory_backend
    prov = _prov()
    concept = Node(kind="Concept", labels=["contract"], props={"text": "hello world"})
    concept.llm_embedding = [0.5, 0.0]
    other = Node(kind="Step", labels=["other"], props={"text": "skip me"})

    memory.upsert(concept, prov, embedding_request=True)
    memory.upsert(other, prov, embedding_request=False)

    results = memory.search(
        "hello",
        top_k=5,
        filters={"kind": "Concept"},
        query_embedding=None,
    )
    ids = {_uuid_of(r) for r in results}
    assert concept.uuid in ids
    assert other.uuid not in ids


def test_embedding_ranking_prefers_closer_vector(memory_backend):
    _, memory = memory_backend
    prov = _prov()
    strong = Node(kind="Concept", labels=["rank"], props={"text": "strong"})
    weak = Node(kind="Concept", labels=["rank"], props={"text": "weak"})
    strong.llm_embedding = [1.0, 0.0]
    weak.llm_embedding = [0.1, 0.0]

    memory.upsert(strong, prov, embedding_request=True)
    memory.upsert(weak, prov, embedding_request=True)

    results = memory.search(
        "",
        top_k=2,
        filters={"kind": "Concept"},
        query_embedding=[1.0, 0.0],
    )
    ids = [_uuid_of(r) for r in results]
    assert ids[0] == strong.uuid
    assert set(ids) >= {strong.uuid, weak.uuid}
