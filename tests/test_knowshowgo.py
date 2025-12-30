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

    def test_create_prototype_and_versioned_concept(self):
        memory = MockMemoryTools()
        api = KnowShowGoAPI(memory)
        parent_proto_uuid = api.create_prototype(
            name="BaseProto",
            description="base",
            context="ctx",
            labels=["prototype", "base"],
            embedding=[0.1, 0.2],
            provenance=None,
        )
        child_proto_uuid = api.create_prototype(
            name="ChildProto",
            description="child",
            context="ctx",
            labels=["prototype", "child"],
            embedding=[0.2, 0.1],
            provenance=None,
            base_prototype_uuid=parent_proto_uuid,
        )
        self.assertIn(child_proto_uuid, memory.nodes)
        inherits = [e for e in memory.edges.values() if e.rel == "inherits_from"]
        self.assertEqual(len(inherits), 1)
        self.assertEqual(inherits[0].to_node, parent_proto_uuid)

        c1 = api.create_concept(child_proto_uuid, {"name": "ConceptV1"}, [0.3, 0.3], provenance=None)
        c2 = api.create_concept(
            child_proto_uuid,
            {"name": "ConceptV2"},
            [0.4, 0.4],
            provenance=None,
            previous_version_uuid=c1,
        )
        edges = [e for e in memory.edges.values() if e.rel == "next_version"]
        self.assertEqual(len(edges), 1)
        self.assertEqual(edges[0].from_node, c1)
        self.assertEqual(edges[0].to_node, c2)


if __name__ == "__main__":
    unittest.main()
