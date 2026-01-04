import unittest
from datetime import datetime, timezone

from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.ontology_init import ensure_default_prototypes


class TestKnowShowGoRecursive(unittest.TestCase):
    """Test recursive concept creation with nested DAG structures"""

    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            # Simple embedding function for testing
            return [float(len(text)), 0.1]
        
        # Ensure default prototypes are seeded
        ensure_default_prototypes(self.memory, embed, trace_id="recursive-test")
        
        # Find Procedure prototype
        self.proc_proto = None
        for node in self.memory.nodes.values():
            if node.kind == "Prototype" and node.props.get("name") == "Procedure":
                self.proc_proto = node
                break
        
        # If not found, create it
        if not self.proc_proto:
            self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
            proto_uuid = self.ksg.create_prototype(
                name="Procedure",
                description="Procedure prototype",
                context="workflow",
                labels=["Prototype", "Procedure"],
                embedding=embed("Procedure"),
            )
            self.proc_proto = self.memory.nodes[proto_uuid]
        else:
            self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        
        self.prov = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "recursive-test")

    def test_create_concept_recursive_with_nested_steps(self):
        """Test creating a concept with nested steps that have sub-procedures"""
        # Create a main procedure concept with nested steps that have their own steps
        main_concept_json = {
            "name": "Login to X.com",
            "description": "Login procedure for X.com",
            "steps": [
                {
                    "name": "Navigate to X.com",
                    "prototype_uuid": self.proc_proto.uuid,
                    "tool": "web.get",
                    "params": {"url": "https://x.com"},
                    "order": 0
                    # Atomic - has tool but no nested steps - should NOT create nested concept
                },
                {
                    "name": "Fill and Submit",
                    "prototype_uuid": self.proc_proto.uuid,
                    "steps": [
                        {"name": "Fill email", "tool": "web.fill", "params": {"field": "email"}},
                        {"name": "Fill password", "tool": "web.fill", "params": {"field": "password"}},
                        {"name": "Click submit", "tool": "web.click_selector", "params": {"selector": "button"}}
                    ],
                    "order": 1
                    # Non-atomic - has nested steps - SHOULD create nested concept
                }
            ]
        }
        
        embedding = [1.0, 0.5, 0.3]
        concept_uuid = self.ksg.create_concept_recursive(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=main_concept_json,
            embedding=embedding,
            provenance=self.prov
        )
        
        # Verify main concept was created
        self.assertIn(concept_uuid, self.memory.nodes)
        main_concept = self.memory.nodes[concept_uuid]
        self.assertEqual(main_concept.kind, "Concept")
        self.assertEqual(main_concept.props["name"], "Login to X.com")
        self.assertEqual(main_concept.llm_embedding, embedding)
        
        # Verify only the non-atomic step creates a nested concept
        step_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == concept_uuid and e.rel == "has_step"
        ]
        self.assertEqual(len(step_edges), 1, "Only non-atomic step should create nested concept")
        
        # Verify the nested concept exists and has its own steps
        nested_concept_uuid = step_edges[0].to_node
        self.assertIn(nested_concept_uuid, self.memory.nodes)
        nested_concept = self.memory.nodes[nested_concept_uuid]
        self.assertEqual(nested_concept.kind, "Concept")
        # The nested concept should have steps in its props (atomic steps)
        nested_steps = nested_concept.props.get("steps", [])
        self.assertGreater(len(nested_steps), 0, "Nested concept should have steps")

    def test_create_concept_recursive_with_children(self):
        """Test creating a concept with children array"""
        main_concept_json = {
            "name": "General Login Procedure",
            "description": "Generalized login procedure",
            "children": [
                {
                    "name": "Navigate to site",
                    "prototype_uuid": self.proc_proto.uuid,
                    "tool": "web.get",
                    "order": 0
                },
                {
                    "name": "Fill form",
                    "prototype_uuid": self.proc_proto.uuid,
                    "tool": "web.fill",
                    "order": 1
                }
            ]
        }
        
        embedding = [0.8, 0.6]
        concept_uuid = self.ksg.create_concept_recursive(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=main_concept_json,
            embedding=embedding,
            provenance=self.prov
        )
        
        # Verify main concept
        self.assertIn(concept_uuid, self.memory.nodes)
        
        # Verify has_child edges (not has_step for children)
        child_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == concept_uuid and e.rel == "has_child"
        ]
        self.assertEqual(len(child_edges), 2, "Should have 2 child edges")

    def test_create_concept_recursive_without_nested(self):
        """Test that create_concept_recursive works like create_concept when no nested structures"""
        simple_json = {
            "name": "Simple Concept",
            "description": "No nested structures"
        }
        
        embedding = [0.5, 0.3]
        concept_uuid = self.ksg.create_concept_recursive(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=simple_json,
            embedding=embedding,
            provenance=self.prov
        )
        
        # Should work like regular create_concept
        self.assertIn(concept_uuid, self.memory.nodes)
        concept = self.memory.nodes[concept_uuid]
        self.assertEqual(concept.props["name"], "Simple Concept")
        
        # Should have instantiates edge
        inst_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == concept_uuid and e.rel == "instantiates"
        ]
        self.assertEqual(len(inst_edges), 1)

    def test_create_concept_recursive_atomic_procedures_not_recursed(self):
        """Test that atomic procedures (single tool commands) are not recursed"""
        main_concept_json = {
            "name": "Procedure with atomic and non-atomic steps",
            "steps": [
                {
                    "name": "Atomic Step",
                    "prototype_uuid": self.proc_proto.uuid,
                    "tool": "web.get",
                    "params": {"url": "https://example.com"},
                    # Atomic: has tool but no nested steps - should NOT create nested concept
                },
                {
                    "name": "Non-Atomic Step",
                    "prototype_uuid": self.proc_proto.uuid,
                    "steps": [
                        {"name": "Sub-step 1", "tool": "web.get"},
                        {"name": "Sub-step 2", "tool": "web.fill"}
                    ],
                    # Non-atomic: has nested steps - SHOULD create nested concept
                }
            ]
        }
        
        embedding = [0.7, 0.4]
        concept_uuid = self.ksg.create_concept_recursive(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=main_concept_json,
            embedding=embedding,
            provenance=self.prov
        )
        
        # Main concept should be created
        self.assertIn(concept_uuid, self.memory.nodes)
        
        # Only the non-atomic step should create a nested concept
        step_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == concept_uuid and e.rel == "has_step"
        ]
        self.assertEqual(len(step_edges), 1, "Only non-atomic step should create a nested concept")
        
        # Verify the atomic step is stored in main concept's props, not as separate concept
        main_concept = self.memory.nodes[concept_uuid]
        steps_in_props = main_concept.props.get("steps", [])
        self.assertGreater(len(steps_in_props), 0, "Atomic steps should be in main concept props")

    def test_create_concept_recursive_preserves_order(self):
        """Test that step order is preserved in edges"""
        main_concept_json = {
            "name": "Ordered Procedure",
            "steps": [
                {
                    "name": "First",
                    "prototype_uuid": self.proc_proto.uuid,
                    "order": 0
                },
                {
                    "name": "Second",
                    "prototype_uuid": self.proc_proto.uuid,
                    "order": 1
                },
                {
                    "name": "Third",
                    "prototype_uuid": self.proc_proto.uuid,
                    "order": 2
                }
            ]
        }
        
        embedding = [0.6, 0.5]
        concept_uuid = self.ksg.create_concept_recursive(
            prototype_uuid=self.proc_proto.uuid,
            json_obj=main_concept_json,
            embedding=embedding,
            provenance=self.prov
        )
        
        # Get step edges and verify order
        step_edges = [
            e for e in self.memory.edges.values()
            if e.from_node == concept_uuid and e.rel == "has_step"
        ]
        self.assertEqual(len(step_edges), 3)
        
        # Check that order is stored in edge props
        orders = [e.props.get("order", -1) for e in step_edges]
        self.assertIn(0, orders)
        self.assertIn(1, orders)
        self.assertIn(2, orders)


if __name__ == "__main__":
    unittest.main()

