import unittest
import uuid
from datetime import datetime, timezone
from src.personal_assistant.models import Provenance, Node, Edge

class TestModels(unittest.TestCase):

    def test_provenance_creation(self):
        """Test the creation of a Provenance object."""
        now = datetime.now(timezone.utc).isoformat()
        provenance = Provenance(
            source="user",
            ts=now,
            confidence=0.95,
            trace_id="trace-123"
        )
        self.assertEqual(provenance.source, "user")
        self.assertEqual(provenance.ts, now)
        self.assertEqual(provenance.confidence, 0.95)
        self.assertEqual(provenance.trace_id, "trace-123")

    def test_node_creation_with_defaults(self):
        """Test that a Node is created with a default UUID."""
        node = Node(
            kind="Person",
            labels=["user", "admin"],
            props={"name": "John Doe"}
        )
        self.assertIsInstance(uuid.UUID(node.uuid), uuid.UUID)
        self.assertEqual(node.kind, "Person")
        self.assertEqual(node.labels, ["user", "admin"])
        self.assertEqual(node.props, {"name": "John Doe"})
        self.assertIsNone(node.llm_embedding)
        self.assertIsNone(node.status)

    def test_edge_creation_with_defaults(self):
        """Test that an Edge is created with default UUID and kind."""
        node1_uuid = str(uuid.uuid4())
        node2_uuid = str(uuid.uuid4())
        edge = Edge(
            from_node=node1_uuid,
            to_node=node2_uuid,
            rel="knows",
            props={"since": "2023"}
        )
        self.assertIsInstance(uuid.UUID(edge.uuid), uuid.UUID)
        self.assertEqual(edge.kind, "edge")
        self.assertEqual(edge.from_node, node1_uuid)
        self.assertEqual(edge.to_node, node2_uuid)
        self.assertEqual(edge.rel, "knows")
        self.assertEqual(edge.props, {"since": "2023"})

if __name__ == '__main__':
    unittest.main()
