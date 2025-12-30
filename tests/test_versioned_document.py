import unittest
from datetime import datetime, timezone

from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.versioned_document import VersionedDocumentStore


class TestVersionedDocument(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemoryTools()
        self.store = VersionedDocumentStore(self.memory)
        self.provenance = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "trace-docs")

    def test_create_and_versioning(self):
        doc = self.store.create("doc-1", {"title": "v1"}, [1.0, 0.0], self.provenance, concept_uuid="concept-1")
        self.assertEqual(doc.version, 1)
        self.assertIn(doc.node_uuid, self.memory.nodes)

        doc2 = doc.save({"title": "v2"}, [0.0, 1.0], self.provenance)
        self.assertEqual(doc2.version, 2)
        self.assertEqual(doc2.data["title"], "v2")
        # Edges: describes v1->concept, next_version v1->v2, describes v2->concept
        self.assertEqual(len(self.memory.edges), 3)

        latest = self.store.load("doc-1")
        self.assertEqual(latest.version, 2)

    def test_similarity_lookup(self):
        self.store.create("doc-emb-a", {"title": "A"}, [1.0, 0.0], self.provenance)
        self.store.create("doc-emb-b", {"title": "B"}, [0.0, 1.0], self.provenance)
        found = self.store.from_similarity([0.0, 1.0])
        self.assertIsNotNone(found)
        self.assertEqual(found.doc_id, "doc-emb-b")


if __name__ == "__main__":
    unittest.main()
