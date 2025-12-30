import tempfile
import uuid

import pytest

chromadb = pytest.importorskip("chromadb")

from src.personal_assistant.chroma_memory import ChromaMemoryTools
from src.personal_assistant.models import Node, Provenance


def test_chroma_memory_upsert_and_search_by_embedding():
    """Ensure Chroma-backed memory stores and retrieves by embedding."""
    with tempfile.TemporaryDirectory() as tmpdir:
        memory = ChromaMemoryTools(
            path=tmpdir, collection_name=f"test-{uuid.uuid4()}", embedding_dim=4
        )
        provenance = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace-test")

        node_a = Node(kind="Concept", labels=["a"], props={"title": "A"}, llm_embedding=[1, 0, 0, 0])
        node_b = Node(kind="Concept", labels=["b"], props={"title": "B"}, llm_embedding=[0, 1, 0, 0])

        upsert_a = memory.upsert(node_a, provenance)
        upsert_b = memory.upsert(node_b, provenance)

        assert upsert_a["status"] == "success"
        assert upsert_b["status"] == "success"

        results = memory.search("anything", top_k=1, query_embedding=[1, 0, 0, 0])
        assert len(results) == 1
        assert results[0]["uuid"] == node_a.uuid
