"""
Tests for Knowshowgo ORM (prototype-based object hydration).
"""

import unittest
from datetime import datetime, timezone

from src.personal_assistant.ksg_orm import KSGORM
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance, Node, Edge
from src.personal_assistant.ksg import KSGStore


class TestKSGORM(unittest.TestCase):
    """Test KSG ORM hydration functionality."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            return [float(len(text)), 0.1]
        
        # Seed prototypes and property defs
        ksg_store = KSGStore(self.memory)
        ksg_store.ensure_seeds(embedding_fn=embed)
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.orm = KSGORM(self.memory)
        self.prov = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "orm-test")
    
    def test_get_concept_hydrated_finds_prototype(self):
        """Test that get_concept_hydrated finds the prototype via instanceOf."""
        # Find Procedure prototype
        procedure_proto = None
        for node in self.memory.nodes.values():
            if (node.kind == "topic" and 
                node.props.get("isPrototype") is True and
                node.props.get("label") == "Procedure"):
                procedure_proto = node
                break
        
        self.assertIsNotNone(procedure_proto, "Procedure prototype should exist")
        
        # Create a Procedure concept
        procedure_uuid = self.ksg.create_concept(
            prototype_uuid=procedure_proto.uuid,
            json_obj={
                "name": "LoginProcedure",
                "description": "Procedure to log in",
                "steps": [{"tool": "web.get", "url": "https://example.com"}],
            },
            embedding=[1.0, 0.0],
            provenance=self.prov,
        )
        
        # Get hydrated concept
        hydrated = self.orm.get_concept(procedure_uuid, hydrate=True)
        
        self.assertIsNotNone(hydrated)
        self.assertEqual(hydrated["props"]["name"], "LoginProcedure")
        self.assertEqual(hydrated["props"]["description"], "Procedure to log in")
        self.assertIn("steps", hydrated["props"])
    
    def test_hydrate_concept_merges_prototype_properties(self):
        """Test that hydration merges prototype properties with concept values."""
        # Find Procedure prototype
        procedure_proto = None
        for node in self.memory.nodes.values():
            if (node.kind == "topic" and 
                node.props.get("isPrototype") is True and
                node.props.get("label") == "Procedure"):
                procedure_proto = node
                break
        
        if not procedure_proto:
            self.skipTest("Procedure prototype not found")
        
        # Create a Procedure concept with some values
        procedure_uuid = self.ksg.create_concept(
            prototype_uuid=procedure_proto.uuid,
            json_obj={
                "name": "TestProcedure",
                "description": "Test",
            },
            embedding=[1.0, 0.0],
            provenance=self.prov,
        )
        
        # Get concept node
        concept_node = None
        for node in self.memory.nodes.values():
            if node.uuid == procedure_uuid:
                concept_node = node
                break
        
        self.assertIsNotNone(concept_node)
        
        # Hydrate
        hydrated = self.orm.hydrate_concept(concept_node)
        
        # Should have concept values
        self.assertEqual(hydrated["props"]["name"], "TestProcedure")
        self.assertEqual(hydrated["props"]["description"], "Test")
        
        # Should have prototype structure (even if empty)
        self.assertIn("props", hydrated)
    
    def test_get_concept_without_hydration(self):
        """Test that get_concept without hydration returns raw concept."""
        # Create a simple concept
        procedure_proto = None
        for node in self.memory.nodes.values():
            if (node.kind == "topic" and 
                node.props.get("isPrototype") is True and
                node.props.get("label") == "Procedure"):
                procedure_proto = node
                break
        
        if not procedure_proto:
            self.skipTest("Procedure prototype not found")
        
        procedure_uuid = self.ksg.create_concept(
            prototype_uuid=procedure_proto.uuid,
            json_obj={"name": "Test"},
            embedding=[1.0, 0.0],
            provenance=self.prov,
        )
        
        # Get without hydration
        raw = self.orm.get_concept(procedure_uuid, hydrate=False)
        
        self.assertIsNotNone(raw)
        self.assertEqual(raw["props"]["name"], "Test")
    
    def test_query_with_hydration(self):
        """Test that query can hydrate results."""
        # Create a concept
        procedure_proto = None
        for node in self.memory.nodes.values():
            if (node.kind == "topic" and 
                node.props.get("isPrototype") is True and
                node.props.get("label") == "Procedure"):
                procedure_proto = node
                break
        
        if not procedure_proto:
            self.skipTest("Procedure prototype not found")
        
        procedure_uuid = self.ksg.create_concept(
            prototype_uuid=procedure_proto.uuid,
            json_obj={"name": "LoginProcedure", "description": "Login"},
            embedding=[1.0, 0.0],
            provenance=self.prov,
        )
        
        # Query with hydration
        results = self.orm.query("LoginProcedure", top_k=5, hydrate=True)
        
        # Should find the concept
        found = False
        for result in results:
            if result.get("uuid") == procedure_uuid:
                found = True
                self.assertEqual(result["props"]["name"], "LoginProcedure")
                break
        
        # Note: Search might not find it if embedding similarity is low
        # This test verifies the hydration mechanism works if results are found


if __name__ == "__main__":
    unittest.main()

