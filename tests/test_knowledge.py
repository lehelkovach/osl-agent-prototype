import unittest
from datetime import datetime

from src.personal_assistant.knowledge import KnowledgeGraphInterface
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance


class TestKnowledgeInterface(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemoryTools()
        self.kg = KnowledgeGraphInterface(self.memory)
        self.provenance = Provenance("user", datetime.utcnow().isoformat(), 1.0, "trace-kg")

    def test_create_prototype_and_concept(self):
        proto = self.kg.create_prototype(
            name="PersonPrototype",
            description="Prototype for person concepts",
            context="people",
            embedding=[0.1, 0.2, 0.3],
            provenance=self.provenance,
        )
        concept = self.kg.instantiate_concept(
            prototype_uuid=proto.uuid,
            phrase="Ada Lovelace",
            context="Mathematician and programmer",
            embedding=[0.3, 0.2, 0.1],
            provenance=self.provenance,
        )

        # Prototype stored
        self.assertIn(proto.uuid, self.memory.nodes)
        self.assertEqual(self.memory.nodes[proto.uuid].kind, "Prototype")
        self.assertEqual(self.memory.nodes[proto.uuid].llm_embedding, [0.1, 0.2, 0.3])

        # Concept stored with prototype reference
        self.assertIn(concept.uuid, self.memory.nodes)
        self.assertEqual(self.memory.nodes[concept.uuid].props["prototype_uuid"], proto.uuid)
        self.assertEqual(self.memory.nodes[concept.uuid].llm_embedding, [0.3, 0.2, 0.1])

        # Edge stored linking prototype -> concept
        edges = list(self.memory.edges.values())
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].from_node, proto.uuid)
        self.assertEqual(edges[0].to_node, concept.uuid)
        self.assertEqual(edges[0].rel, "instantiates")

        # Retrieval helpers
        self.assertEqual(self.kg.get_prototype(proto.uuid).uuid, proto.uuid)
        self.assertEqual(self.kg.get_concept(concept.uuid).uuid, concept.uuid)


if __name__ == "__main__":
    unittest.main()
