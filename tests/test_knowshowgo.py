import unittest
from datetime import datetime, timezone

from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.ontology_init import ensure_default_prototypes


class TestKnowShowGoAPI(unittest.TestCase):
    def test_create_concept_links_to_prototype(self):
        memory = MockMemoryTools()

        def embed(text):
            return [0.6, 0.4]

        ids = ensure_default_prototypes(memory, embed, trace_id="kg-test")
        dag_proto = [n for n in memory.nodes.values() if n.props.get("name") == "DAG"][0]

        api = KnowShowGoAPI(memory)
        concept_uuid = api.create_concept(
            prototype_uuid=dag_proto.uuid,
            json_obj={"name": "Workflow", "description": "Test workflow"},
            embedding=[0.9, 0.1],
            provenance=None,
        )

        self.assertIn(concept_uuid, memory.nodes)
        concept = memory.nodes[concept_uuid]
        self.assertEqual(concept.props["prototype_uuid"], dag_proto.uuid)
        self.assertEqual(concept.llm_embedding, [0.9, 0.1])

        # Edge exists from concept -> prototype
        edges = [e for e in memory.edges.values() if e.rel == "instantiates"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].from_node, concept_uuid)
        self.assertEqual(edges[0].to_node, dag_proto.uuid)


if __name__ == "__main__":
    unittest.main()
