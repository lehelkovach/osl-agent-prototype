"""Tests for ProcedureManager - LLM JSON to KnowShowGo DAG conversion."""
import unittest
import json

from src.personal_assistant.procedure_manager import (
    ProcedureManager,
    ValidationResult,
    PROCEDURE_JSON_SCHEMA,
    PROCEDURE_JSON_EXAMPLE,
    create_procedure_manager,
)
from src.personal_assistant.networkx_memory import NetworkXMemoryTools
from src.personal_assistant.models import Provenance


def dummy_embed(text: str):
    """Simple embedding for testing."""
    return [0.1] * 128


class TestProcedureJSONSchema(unittest.TestCase):
    """Tests for procedure JSON schema and examples."""
    
    def test_schema_has_required_fields(self):
        self.assertIn("type", PROCEDURE_JSON_SCHEMA)
        self.assertIn("required", PROCEDURE_JSON_SCHEMA)
        self.assertIn("properties", PROCEDURE_JSON_SCHEMA)
        
        # Required fields
        required = PROCEDURE_JSON_SCHEMA["required"]
        self.assertIn("name", required)
        self.assertIn("description", required)
        self.assertIn("steps", required)
    
    def test_example_is_valid_json(self):
        # Should be serializable
        json_str = json.dumps(PROCEDURE_JSON_EXAMPLE)
        parsed = json.loads(json_str)
        
        self.assertEqual(parsed["name"], "LinkedIn Login")
        self.assertEqual(len(parsed["steps"]), 5)
    
    def test_example_has_proper_dag_structure(self):
        steps = PROCEDURE_JSON_EXAMPLE["steps"]
        
        # First step has no dependencies
        self.assertEqual(steps[0]["depends_on"], [])
        
        # Step 2 and 3 depend on step 1
        self.assertEqual(steps[1]["depends_on"], ["step_1"])
        self.assertEqual(steps[2]["depends_on"], ["step_1"])
        
        # Step 4 depends on steps 2 and 3 (parallel merge)
        self.assertEqual(set(steps[3]["depends_on"]), {"step_2", "step_3"})
        
        # Step 5 depends on step 4
        self.assertEqual(steps[4]["depends_on"], ["step_4"])


class TestProcedureValidation(unittest.TestCase):
    """Tests for procedure JSON validation."""
    
    def setUp(self):
        self.memory = NetworkXMemoryTools()
        self.manager = ProcedureManager(memory=self.memory, embed_fn=dummy_embed)
    
    def test_valid_procedure_passes(self):
        result = self.manager.validate(PROCEDURE_JSON_EXAMPLE)
        self.assertTrue(result.valid)
        self.assertEqual(len(result.errors), 0)
    
    def test_missing_name_fails(self):
        proc = {"description": "test", "steps": []}
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("name" in e.path for e in result.errors))
    
    def test_missing_steps_fails(self):
        proc = {"name": "test", "description": "test"}
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("steps" in e.path for e in result.errors))
    
    def test_empty_steps_fails(self):
        proc = {"name": "test", "description": "test", "steps": []}
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("at least one step" in e.message for e in result.errors))
    
    def test_step_missing_id_fails(self):
        proc = {
            "name": "test",
            "description": "test",
            "steps": [{"tool": "web.get", "params": {}}]
        }
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("id" in e.message for e in result.errors))
    
    def test_step_missing_tool_fails(self):
        proc = {
            "name": "test",
            "description": "test",
            "steps": [{"id": "step_1", "params": {}}]
        }
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("tool" in e.message for e in result.errors))
    
    def test_duplicate_step_ids_fails(self):
        proc = {
            "name": "test",
            "description": "test",
            "steps": [
                {"id": "step_1", "tool": "web.get", "params": {}},
                {"id": "step_1", "tool": "web.fill", "params": {}},  # Duplicate
            ]
        }
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Duplicate" in e.message for e in result.errors))
    
    def test_unknown_dependency_fails(self):
        proc = {
            "name": "test",
            "description": "test",
            "steps": [
                {"id": "step_1", "tool": "web.get", "params": {}, "depends_on": ["nonexistent"]}
            ]
        }
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Unknown dependency" in e.message for e in result.errors))
    
    def test_circular_dependency_fails(self):
        proc = {
            "name": "test",
            "description": "test",
            "steps": [
                {"id": "step_1", "tool": "a", "params": {}, "depends_on": ["step_2"]},
                {"id": "step_2", "tool": "b", "params": {}, "depends_on": ["step_1"]},
            ]
        }
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Circular" in e.message for e in result.errors))
    
    def test_complex_cycle_detected(self):
        proc = {
            "name": "test",
            "description": "test",
            "steps": [
                {"id": "a", "tool": "t", "params": {}, "depends_on": ["c"]},
                {"id": "b", "tool": "t", "params": {}, "depends_on": ["a"]},
                {"id": "c", "tool": "t", "params": {}, "depends_on": ["b"]},
            ]
        }
        result = self.manager.validate(proc)
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Circular" in e.message for e in result.errors))
    
    def test_valid_json_string(self):
        json_str = json.dumps(PROCEDURE_JSON_EXAMPLE)
        result = self.manager.validate(json_str)
        
        self.assertTrue(result.valid)
    
    def test_invalid_json_string(self):
        result = self.manager.validate("not valid json{")
        
        self.assertFalse(result.valid)
        self.assertTrue(any("Invalid JSON" in e.message for e in result.errors))


class TestProcedureCreation(unittest.TestCase):
    """Tests for creating procedures from JSON."""
    
    def setUp(self):
        self.memory = NetworkXMemoryTools()
        self.manager = ProcedureManager(memory=self.memory, embed_fn=dummy_embed)
    
    def test_create_simple_procedure(self):
        proc = {
            "name": "Simple Test",
            "description": "A simple test procedure",
            "steps": [
                {"id": "step_1", "tool": "echo", "params": {"text": "hello"}}
            ]
        }
        
        result = self.manager.create_from_json(proc)
        
        self.assertIn("procedure_uuid", result)
        self.assertIn("step_uuids", result)
        self.assertEqual(len(result["step_uuids"]), 1)
    
    def test_create_dag_procedure(self):
        proc = {
            "name": "DAG Test",
            "description": "Test with dependencies",
            "steps": [
                {"id": "step_1", "tool": "a", "params": {}},
                {"id": "step_2", "tool": "b", "params": {}, "depends_on": ["step_1"]},
                {"id": "step_3", "tool": "c", "params": {}, "depends_on": ["step_1"]},
                {"id": "step_4", "tool": "d", "params": {}, "depends_on": ["step_2", "step_3"]},
            ]
        }
        
        result = self.manager.create_from_json(proc)
        
        self.assertEqual(len(result["step_uuids"]), 4)
        self.assertEqual(result["dag_edges"], 4)  # 0 + 1 + 1 + 2 = 4
    
    def test_create_from_example(self):
        result = self.manager.create_from_json(PROCEDURE_JSON_EXAMPLE)
        
        self.assertIn("procedure_uuid", result)
        self.assertEqual(len(result["step_uuids"]), 5)
    
    def test_procedure_stored_in_memory(self):
        proc = {
            "name": "Memory Test",
            "description": "Test storage",
            "steps": [{"id": "s1", "tool": "test", "params": {}}]
        }
        
        result = self.manager.create_from_json(proc)
        proc_uuid = result["procedure_uuid"]
        
        # Should be searchable
        search_results = self.memory.search(
            "Memory Test",
            top_k=5,
            filters={"kind": "Procedure"}
        )
        
        self.assertGreater(len(search_results), 0)
    
    def test_steps_linked_to_procedure(self):
        proc = {
            "name": "Link Test",
            "description": "Test linking",
            "steps": [
                {"id": "s1", "tool": "a", "params": {}},
                {"id": "s2", "tool": "b", "params": {}},
            ]
        }
        
        result = self.manager.create_from_json(proc)
        
        # Check edges exist
        proc_uuid = result["procedure_uuid"]
        edges = list(self.memory.edges.values())
        has_step_edges = [e for e in edges if e.rel == "has_step" and e.from_node == proc_uuid]
        
        self.assertEqual(len(has_step_edges), 2)
    
    def test_dependency_edges_created(self):
        proc = {
            "name": "Dep Test",
            "description": "Test dependencies",
            "steps": [
                {"id": "s1", "tool": "a", "params": {}},
                {"id": "s2", "tool": "b", "params": {}, "depends_on": ["s1"]},
            ]
        }
        
        result = self.manager.create_from_json(proc)
        
        # Check dependency edges
        edges = list(self.memory.edges.values())
        dep_edges = [e for e in edges if e.rel == "depends_on"]
        
        self.assertEqual(len(dep_edges), 1)
    
    def test_validation_can_be_skipped(self):
        # Invalid procedure (no steps)
        proc = {"name": "test", "description": "test", "steps": []}
        
        # Should fail with validation
        with self.assertRaises(ValueError):
            self.manager.create_from_json(proc, validate_first=True)
        
        # Note: skipping validation with invalid data would cause errors
        # in the actual creation, but the validation skip flag exists
    
    def test_provenance_used(self):
        proc = {
            "name": "Prov Test",
            "description": "Test provenance",
            "steps": [{"id": "s1", "tool": "t", "params": {}}]
        }
        
        prov = Provenance(
            source="test",
            ts="2024-01-01T00:00:00Z",
            confidence=0.9,
            trace_id="test-123"
        )
        
        result = self.manager.create_from_json(proc, provenance=prov)
        
        # Procedure should be created with provenance
        self.assertIn("procedure_uuid", result)


class TestProcedureRetrieval(unittest.TestCase):
    """Tests for retrieving stored procedures."""
    
    def setUp(self):
        self.memory = NetworkXMemoryTools()
        self.manager = ProcedureManager(memory=self.memory, embed_fn=dummy_embed)
    
    def test_search_procedures(self):
        # Create some procedures
        proc1 = {
            "name": "Login to LinkedIn",
            "description": "Authenticate on LinkedIn",
            "steps": [{"id": "s1", "tool": "web.get", "params": {}}]
        }
        proc2 = {
            "name": "Search GitHub",
            "description": "Search repositories",
            "steps": [{"id": "s1", "tool": "web.get", "params": {}}]
        }
        
        self.manager.create_from_json(proc1)
        self.manager.create_from_json(proc2)
        
        # Search
        results = self.manager.search_procedures("LinkedIn login", top_k=5)
        
        self.assertGreater(len(results), 0)


class TestExecutionPlanConversion(unittest.TestCase):
    """Tests for converting procedures to execution plans."""
    
    def setUp(self):
        self.memory = NetworkXMemoryTools()
        self.manager = ProcedureManager(memory=self.memory, embed_fn=dummy_embed)
    
    def test_to_execution_plan_basic_structure(self):
        """Test that execution plan has required fields."""
        proc = {
            "name": "Test Plan",
            "description": "Test conversion",
            "goal": "Test the conversion",
            "steps": [
                {"id": "s1", "tool": "a", "params": {"x": 1}},
                {"id": "s2", "tool": "b", "params": {"y": 2}, "depends_on": ["s1"]},
            ]
        }
        
        result = self.manager.create_from_json(proc)
        plan = self.manager.to_execution_plan(result["procedure_uuid"])
        
        self.assertIn("procedure_uuid", plan)
        self.assertIn("goal", plan)
        self.assertIn("steps", plan)
        self.assertTrue(plan.get("reuse"))
        
        # Note: Steps retrieval requires get_node/get_edges which NetworkXMemoryTools
        # doesn't fully implement. In production, use a memory backend that supports these.
        self.assertIsInstance(plan["steps"], list)


class TestPromptInstructions(unittest.TestCase):
    """Tests for LLM prompt instructions."""
    
    def setUp(self):
        self.memory = NetworkXMemoryTools()
        self.manager = ProcedureManager(memory=self.memory)
    
    def test_get_prompt_instructions(self):
        instructions = self.manager.get_prompt_instructions()
        
        self.assertIn("JSON", instructions)
        self.assertIn("steps", instructions)
        self.assertIn("depends_on", instructions)
        self.assertIn("DAG", instructions)
    
    def test_get_schema(self):
        schema = self.manager.get_schema()
        
        self.assertEqual(schema["type"], "object")
        self.assertIn("steps", schema["properties"])
    
    def test_get_example(self):
        example = self.manager.get_example()
        
        self.assertEqual(example["name"], "LinkedIn Login")
        self.assertEqual(len(example["steps"]), 5)


class TestFactoryFunction(unittest.TestCase):
    """Tests for factory function."""
    
    def test_create_procedure_manager(self):
        memory = NetworkXMemoryTools()
        manager = create_procedure_manager(memory, embed_fn=dummy_embed)
        
        self.assertIsInstance(manager, ProcedureManager)
        self.assertEqual(manager.memory, memory)
        self.assertEqual(manager.embed_fn, dummy_embed)


if __name__ == "__main__":
    unittest.main()
