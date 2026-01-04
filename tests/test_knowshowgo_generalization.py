import unittest
from datetime import datetime, timezone

from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.ontology_init import ensure_default_prototypes


class TestKnowShowGoGeneralization(unittest.TestCase):
    """Test concept generalization (merging exemplars into taxonomy hierarchy)"""

    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            return [float(len(text)), 0.1]
        
        ensure_default_prototypes(self.memory, embed, trace_id="generalize-test")
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.prov = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "generalize-test")
        
        # Find Procedure prototype
        self.proc_proto = None
        for node in self.memory.nodes.values():
            if node.kind == "Prototype" and node.props.get("name") == "Procedure":
                self.proc_proto = node
                break
        
        # Create exemplar concepts
        self.exemplar1_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto.uuid if self.proc_proto else "unknown",
            json_obj={"name": "Login to X.com", "description": "Login procedure for X.com"},
            embedding=[1.0, 0.0],
            provenance=self.prov
        )
        self.exemplar2_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto.uuid if self.proc_proto else "unknown",
            json_obj={"name": "Login to Y.com", "description": "Login procedure for Y.com"},
            embedding=[0.9, 0.1],
            provenance=self.prov
        )
        self.exemplar3_uuid = self.ksg.create_concept(
            prototype_uuid=self.proc_proto.uuid if self.proc_proto else "unknown",
            json_obj={"name": "Login to Z.com", "description": "Login procedure for Z.com"},
            embedding=[0.95, 0.05],
            provenance=self.prov
        )

    def test_generalize_concepts_creates_parent(self):
        """Test that generalization creates a parent concept"""
        exemplars = [self.exemplar1_uuid, self.exemplar2_uuid]
        generalized_embedding = [0.95, 0.05]
        
        parent_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=exemplars,
            generalized_name="General Login Procedure",
            generalized_description="Generalized login procedure for websites",
            generalized_embedding=generalized_embedding,
            prototype_uuid=self.proc_proto.uuid if self.proc_proto else None,
            provenance=self.prov
        )
        
        # Verify parent concept was created
        self.assertIn(parent_uuid, self.memory.nodes)
        parent_concept = self.memory.nodes[parent_uuid]
        self.assertEqual(parent_concept.kind, "Concept")
        self.assertEqual(parent_concept.props["name"], "General Login Procedure")
        self.assertEqual(parent_concept.props["type"], "generalized")
        self.assertEqual(parent_concept.props["exemplar_count"], 2)
        self.assertEqual(parent_concept.llm_embedding, generalized_embedding)

    def test_generalize_links_exemplars_as_children(self):
        """Test that exemplars are linked as children of the generalized concept"""
        exemplars = [self.exemplar1_uuid, self.exemplar2_uuid, self.exemplar3_uuid]
        generalized_embedding = [0.95, 0.05]
        
        parent_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=exemplars,
            generalized_name="General Login",
            generalized_description="Generalized login",
            generalized_embedding=generalized_embedding,
            provenance=self.prov
        )
        
        # Verify has_exemplar edges
        exemplar_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == parent_uuid and e.rel == "has_exemplar"
        ]
        self.assertEqual(len(exemplar_edges), len(exemplars))
        
        # Verify each exemplar is linked
        linked_exemplars = {e.to_node for e in exemplar_edges}
        self.assertEqual(linked_exemplars, set(exemplars))
        
        # Verify order is preserved
        for idx, edge in enumerate(exemplar_edges):
            self.assertEqual(edge.props.get("order"), idx)

    def test_generalize_creates_reverse_edges(self):
        """Test that reverse edges (generalized_by) are created"""
        exemplars = [self.exemplar1_uuid, self.exemplar2_uuid]
        generalized_embedding = [0.95, 0.05]
        
        parent_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=exemplars,
            generalized_name="General Login",
            generalized_description="Generalized login",
            generalized_embedding=generalized_embedding,
            provenance=self.prov
        )
        
        # Verify reverse edges (exemplar -> parent)
        reverse_edges = [
            e for e in self.memory.edges.values()
            if e.from_node in exemplars and e.rel == "generalized_by"
        ]
        self.assertEqual(len(reverse_edges), len(exemplars))
        
        # Verify all point to parent
        for edge in reverse_edges:
            self.assertEqual(edge.to_node, parent_uuid)
            self.assertEqual(edge.props.get("generalized_name"), "General Login")

    def test_generalize_taxonomy_hierarchy(self):
        """Test that generalization creates a proper taxonomy hierarchy"""
        # Create first level exemplars
        exemplars_level1 = [self.exemplar1_uuid, self.exemplar2_uuid]
        parent1_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=exemplars_level1,
            generalized_name="Site Login",
            generalized_description="Login to specific sites",
            generalized_embedding=[0.95, 0.05],
            provenance=self.prov
        )
        
        # Create second level (generalize the generalized + another exemplar)
        exemplars_level2 = [parent1_uuid, self.exemplar3_uuid]
        parent2_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=exemplars_level2,
            generalized_name="General Login Procedure",
            generalized_description="All login procedures",
            generalized_embedding=[0.9, 0.1],
            provenance=self.prov
        )
        
        # Verify hierarchy
        # Level 2 should have level 1 as child
        level2_children = [
            e.to_node for e in self.memory.edges.values()
            if e.from_node == parent2_uuid and e.rel == "has_exemplar"
        ]
        self.assertIn(parent1_uuid, level2_children)
        self.assertIn(self.exemplar3_uuid, level2_children)
        
        # Level 1 should have original exemplars as children
        level1_children = [
            e.to_node for e in self.memory.edges.values()
            if e.from_node == parent1_uuid and e.rel == "has_exemplar"
        ]
        self.assertEqual(set(level1_children), set(exemplars_level1))

    def test_generalize_with_single_exemplar(self):
        """Test generalization with a single exemplar (still creates parent)"""
        parent_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=[self.exemplar1_uuid],
            generalized_name="Single Exemplar Parent",
            generalized_description="Parent of single exemplar",
            generalized_embedding=[1.0, 0.0],
            provenance=self.prov
        )
        
        self.assertIn(parent_uuid, self.memory.nodes)
        exemplar_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == parent_uuid and e.rel == "has_exemplar"
        ]
        self.assertEqual(len(exemplar_edges), 1)


if __name__ == "__main__":
    unittest.main()

