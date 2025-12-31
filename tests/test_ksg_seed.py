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
        proto_nodes = [n for n in memory.nodes.values() if n.kind == "Prototype"]
        self.assertEqual(len(proto_nodes), len(DEFAULT_PROTOTYPES))
        prop_nodes = [n for n in memory.nodes.values() if n.kind == "PropertyDef"]
        self.assertEqual(len(prop_nodes), len(DEFAULT_PROPERTY_DEFS))
        obj_nodes = [n for n in memory.nodes.values() if n.kind == "Object"]
        self.assertEqual(len(obj_nodes), len(DEFAULT_OBJECTS))

        # Check inheritance edges for list/chain/dag
        inherit_edges = [e for e in memory.edges.values() if e.rel == "inherits_from"]
        self.assertGreaterEqual(len(inherit_edges), 2)
        rels = {(e.props.get("child"), e.props.get("parent")) for e in inherit_edges}
        self.assertIn(("Chain", "List"), rels)
        self.assertIn(("DAG", "Chain"), rels)


if __name__ == "__main__":
    unittest.main()
