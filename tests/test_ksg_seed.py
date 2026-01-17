import unittest

from src.personal_assistant.ksg import KSGStore, DEFAULT_PROTOTYPES, DEFAULT_PROPERTY_DEFS, DEFAULT_OBJECTS
from src.personal_assistant.mock_tools import MockMemoryTools


class TestKSGSeed(unittest.TestCase):
    def test_seed_creates_prototypes_propertydefs_objects(self):
        memory = MockMemoryTools()

        def embed(text):
            return [0.1, 0.1]

        ksg = KSGStore(memory)
        ensured = ksg.ensure_seeds(embedding_fn=embed)

        self.assertEqual(len(ensured["property_defs"]), len(DEFAULT_PROPERTY_DEFS))
        self.assertEqual(len(ensured["prototypes"]), len(DEFAULT_PROTOTYPES))
        self.assertEqual(len(ensured["objects"]), len(DEFAULT_OBJECTS))

        # Verify some nodes exist
        # Prototypes are now Topics with isPrototype=true (Knowshowgo design)
        proto_nodes = [
            n for n in memory.nodes.values()
            if n.kind == "topic" and n.props.get("isPrototype") is True
        ]
        self.assertEqual(len(proto_nodes), len(DEFAULT_PROTOTYPES))
        prop_nodes = [n for n in memory.nodes.values() if n.kind == "PropertyDef"]
        self.assertEqual(len(prop_nodes), len(DEFAULT_PROPERTY_DEFS))
        obj_nodes = [n for n in memory.nodes.values() if n.kind == "Object"]
        self.assertEqual(len(obj_nodes), len(DEFAULT_OBJECTS))

        # Check inheritance edges (Knowshowgo uses "inherits" edge collection)
        inherit_edges = [e for e in memory.edges.values() if e.rel == "inherits"]
        self.assertGreaterEqual(len(inherit_edges), 1)
        rels = {(e.props.get("child"), e.props.get("parent")) for e in inherit_edges}
        # Check for BasePrototype inheritance (all prototypes inherit from BasePrototype)
        self.assertIn(("Person", "BasePrototype"), rels)
        self.assertIn(("Procedure", "BasePrototype"), rels)
        # Backward compat inheritance
        if "DAG" in DEFAULT_PROTOTYPES and "List" in DEFAULT_PROTOTYPES:
            self.assertIn(("DAG", "List"), rels)
        if "Queue" in DEFAULT_PROTOTYPES and "List" in DEFAULT_PROTOTYPES:
            self.assertIn(("Queue", "List"), rels)

    def test_vault_property_defs_present(self):
        memory = MockMemoryTools()
        ksg = KSGStore(memory)
        ksg.ensure_seeds()
        props = {pd["prop"] for pd in DEFAULT_PROPERTY_DEFS}
        expected = {
            "username",
            "password",
            "secret",
            "appName",
            "cardNumber",
            "cardExpiry",
            "cardCvv",
            "billingAddress",
            "identityNumber",
            "givenName",
            "familyName",
            "address",
            "city",
            "state",
            "postalCode",
            "country",
            "phone",
        }
        self.assertTrue(expected.issubset(props))

    def test_seed_sets_embeddings_and_tag_embedding(self):
        memory = MockMemoryTools()

        def embed(text: str):
            return [float(len(text)), 0.5]

        ksg = KSGStore(memory)
        ksg.ensure_seeds(embedding_fn=embed)

        # All seeded nodes should have embeddings
        for node in memory.nodes.values():
            self.assertIsNotNone(node.llm_embedding)
            self.assertGreater(len(node.llm_embedding), 0)

        # Add a tag and ensure it also has an embedding
        obj_uuid = next(iter(memory.nodes.keys()))
        tag_uuid = ksg.add_tag(obj_uuid, "demo-tag", embedding_fn=embed)
        tag_node = memory.nodes[tag_uuid]
        self.assertIsNotNone(tag_node.llm_embedding)
        self.assertGreater(len(tag_node.llm_embedding), 0)


if __name__ == "__main__":
    unittest.main()
