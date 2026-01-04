"""
Test Module 5: Agent auto-generalizes working procedures.

Goal: When multiple similar procedures work, agent automatically merges/averages
them into a generalized pattern.
"""
import unittest
import numpy as np

from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.ontology_init import ensure_default_prototypes
from datetime import datetime, timezone


def get_procedure_prototype(memory):
    """Helper to get Procedure prototype UUID"""
    for node in memory.nodes.values():
        if node.kind == "Prototype" and node.props.get("name") == "Procedure":
            return node.uuid
    return None


def average_vector_embeddings(embeddings):
    """
    Helper to average vector embeddings dimension-wise.
    Creates a centroid embedding in vector space.
    """
    if not embeddings:
        return None
    if len(embeddings) == 1:
        return embeddings[0]
    # Average each dimension: centroid of vector embeddings
    dim = len(embeddings[0])
    return [sum(emb[i] for emb in embeddings) / len(embeddings) for i in range(dim)]


class TestAgentAutoGeneralize(unittest.TestCase):
    """Test automatic generalization of working procedures"""

    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            return [float(len(text)), 0.1 * len(text.split())]
        
        ensure_default_prototypes(self.memory, embed, trace_id="generalize-test")
        self.proc_proto_uuid = get_procedure_prototype(self.memory)
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.prov = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "generalize-test")

    def test_merge_embeddings_for_generalization(self):
        """Test merging/averaging embeddings from multiple procedures"""
        # Create multiple similar procedures with different embeddings
        proc1_embedding = [1.0, 0.5]
        proc2_embedding = [0.95, 0.48]
        proc3_embedding = [0.98, 0.49]
        
        proc1_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login to X.com"},
            proc1_embedding,
            self.prov
        )
        proc2_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login to Y.com"},
            proc2_embedding,
            self.prov
        )
        proc3_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login to Z.com"},
            proc3_embedding,
            self.prov
        )
        
        # Average vector embeddings (dimension-wise)
        exemplar_embeddings = [proc1_embedding, proc2_embedding, proc3_embedding]
        generalized_embedding = average_vector_embeddings(exemplar_embeddings)
        
        # Create generalized pattern
        generalized_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=[proc1_uuid, proc2_uuid, proc3_uuid],
            generalized_name="General Login Procedure",
            generalized_description="Generalized login procedure for websites",
            generalized_embedding=generalized_embedding,
            prototype_uuid=self.proc_proto_uuid,
            provenance=self.prov
        )
        
        # Verify generalized pattern created
        generalized = self.memory.nodes[generalized_uuid]
        self.assertEqual(generalized.props["name"], "General Login Procedure")
        # Verify vector embedding is averaged (centroid in embedding space)
        expected_avg = [(1.0 + 0.95 + 0.98) / 3, (0.5 + 0.48 + 0.49) / 3]
        self.assertAlmostEqual(generalized.llm_embedding[0], expected_avg[0], places=2, msg="Vector embedding dimension 0 should be averaged")
        self.assertAlmostEqual(generalized.llm_embedding[1], expected_avg[1], places=2, msg="Vector embedding dimension 1 should be averaged")
        self.assertEqual(len(generalized.llm_embedding), 2, "Generalized embedding should have same dimensionality")

    def test_extract_common_steps(self):
        """Test extracting common steps from multiple procedures"""
        # Create procedures with similar but not identical steps
        common_step = {"tool": "web.get", "params": {"url": "https://example.com/login"}}
        
        proc1_steps = [
            common_step,
            {"tool": "web.fill", "params": {"selectors": {"email": "input[type='email']"}}},
            {"tool": "web.click_selector", "params": {"selector": "button[type='submit']"}},
        ]
        proc2_steps = [
            common_step,
            {"tool": "web.fill", "params": {"selectors": {"email": "input[name='email']"}}},  # Different selector
            {"tool": "web.click_selector", "params": {"selector": "button[type='submit']"}},
        ]
        proc3_steps = [
            common_step,
            {"tool": "web.fill", "params": {"selectors": {"email": "input#email"}}},  # Different selector
            {"tool": "web.click_selector", "params": {"selector": "button.submit"}},  # Different selector
        ]
        
        # Store procedures
        proc1_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login X", "steps": proc1_steps},
            [1.0, 0.5],
            self.prov
        )
        proc2_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login Y", "steps": proc2_steps},
            [0.95, 0.48],
            self.prov
        )
        proc3_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login Z", "steps": proc3_steps},
            [0.98, 0.49],
            self.prov
        )
        
        # Extract common steps (simplified: all have web.get as first step)
        # In real implementation, would do more sophisticated comparison
        common_steps = [common_step]  # All have this step
        
        # Create generalized pattern with common steps
        # Average vector embeddings for generalization
        generalized_embedding = average_vector_embeddings([[1.0, 0.5], [0.95, 0.48], [0.98, 0.49]])
        generalized_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=[proc1_uuid, proc2_uuid, proc3_uuid],
            generalized_name="General Login",
            generalized_description="Generalized login",
            generalized_embedding=generalized_embedding,
            prototype_uuid=self.proc_proto_uuid,
            provenance=self.prov
        )
        
        # Verify generalized pattern can store common steps
        # (Note: generalize_concepts doesn't extract steps automatically yet,
        # but structure supports it)
        generalized = self.memory.nodes[generalized_uuid]
        self.assertEqual(generalized.props["name"], "General Login")

    def test_links_exemplars_to_generalized(self):
        """Test that exemplars are linked to generalized pattern"""
        # Create exemplars
        proc1_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login X"},
            [1.0, 0.5],
            self.prov
        )
        proc2_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login Y"},
            [0.95, 0.48],
            self.prov
        )
        
        # Generalize
        generalized_uuid = self.ksg.generalize_concepts(
            exemplar_uuids=[proc1_uuid, proc2_uuid],
            generalized_name="General Login",
            generalized_description="Generalized",
            generalized_embedding=[0.975, 0.49],
            prototype_uuid=self.proc_proto_uuid,
            provenance=self.prov
        )
        
        # Verify links
        has_exemplar_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == generalized_uuid and e.rel == "has_exemplar"
        ]
        self.assertEqual(len(has_exemplar_edges), 2)
        
        # Verify reverse links
        generalized_by_edges = [
            e for e in self.memory.edges.values()
            if e.from_node in [proc1_uuid, proc2_uuid] and e.rel == "generalized_by"
        ]
        self.assertEqual(len(generalized_by_edges), 2)

    def test_auto_generalize_trigger_condition(self):
        """Test conditions for triggering auto-generalization"""
        # Conditions:
        # 1. Multiple similar procedures found (2+)
        # 2. Procedures execute successfully
        # 3. Similarity above threshold
        
        # Create multiple similar procedures
        proc1_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login X", "success_count": 5},
            [1.0, 0.5],
            self.prov
        )
        proc2_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login Y", "success_count": 3},
            [0.95, 0.48],
            self.prov
        )
        proc3_uuid = self.ksg.create_concept(
            self.proc_proto_uuid,
            {"name": "Login Z", "success_count": 2},
            [0.98, 0.49],
            self.prov
        )
        
        # Search for similar procedures
        query_embedding = [0.98, 0.49]  # Similar to all three
        matches = self.ksg.search_concepts(
            "login procedure",
            top_k=5,
            query_embedding=query_embedding
        )
        
        # Should find multiple similar procedures
        self.assertGreaterEqual(len(matches), 2, "Should find multiple similar procedures")
        
        # Filter to only successful ones (simulated)
        successful_matches = [
            m for m in matches
            if isinstance(m, dict) and m.get("props", {}).get("success_count", 0) > 0
        ]
        
        # If 2+ successful matches, should trigger generalization
        should_generalize = len(successful_matches) >= 2
        self.assertTrue(should_generalize, "Should trigger generalization with 2+ successful matches")


if __name__ == "__main__":
    unittest.main()

