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


if __name__ == "__main__":
    unittest.main()
