import unittest
from datetime import datetime, timezone

from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.ontology_init import ensure_default_prototypes, DEFAULT_PROTOTYPES
from src.personal_assistant.models import Provenance


class TestOntologyInit(unittest.TestCase):
    def test_ensure_prototypes_created_once(self):
        memory = MockMemoryTools()

        def embed(text):
            return [1.0, 0.0, 0.0]

        ids_first = ensure_default_prototypes(memory, embed, trace_id="test-init")
        self.assertEqual(len(ids_first), len(DEFAULT_PROTOTYPES))
        self.assertEqual(len(memory.nodes), len(DEFAULT_PROTOTYPES))
        # Run again, should not create duplicates
        ids_second = ensure_default_prototypes(memory, embed, trace_id="test-init-2")
        self.assertEqual(ids_first, ids_second)
        self.assertEqual(len(memory.nodes), len(DEFAULT_PROTOTYPES))

    def test_task_inherits_from_dag(self):
        memory = MockMemoryTools()

        def embed(text):
            return [0.5, 0.5]

        ensure_default_prototypes(memory, embed, trace_id="test-inherit")
        dag = [n for n in memory.nodes.values() if n.props.get("name") == "DAG"]
        task = [n for n in memory.nodes.values() if n.props.get("name") == "Task"]
        self.assertEqual(len(dag), 1)
        self.assertEqual(len(task), 1)
        # Edge should exist from Task -> DAG
        inherits_edges = [e for e in memory.edges.values() if e.rel == "inherits_from"]
        self.assertTrue(inherits_edges)
        task_to_dag = [
            e for e in inherits_edges
            if e.from_node == task[0].uuid and e.to_node == dag[0].uuid
        ]
        self.assertEqual(len(task_to_dag), 1)


if __name__ == "__main__":
    unittest.main()
