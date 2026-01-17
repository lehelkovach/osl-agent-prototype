"""
Tests for Knowshowgo ORM write/save functionality.
"""

import unittest
from datetime import datetime, timezone

from src.personal_assistant.ksg_orm import KSGORM
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Provenance
from src.personal_assistant.ksg import KSGStore


class TestKSGORMWrite(unittest.TestCase):
    """Test KSG ORM write/save functionality."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            return [float(len(text)), 0.1]
        
        # Seed prototypes and property defs
        ksg_store = KSGStore(self.memory)
        ksg_store.ensure_seeds(embedding_fn=embed)
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.orm = KSGORM(self.memory)
        self.prov = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "orm-write-test")
    
    def test_create_object_from_prototype(self):
        """Test creating a new object from a prototype name and properties."""
        # Create a Procedure object
        obj = self.orm.create_object(
            prototype_name="Procedure",
            properties={
                "name": "LoginProcedure",
                "description": "Procedure to log in",
                "steps": [{"tool": "web.get", "url": "https://example.com"}],
            },
            embed_fn=lambda x: [1.0, 0.0],
        )
        
        self.assertIsNotNone(obj)
        self.assertIsNotNone(obj.get("uuid"))
        self.assertEqual(obj["props"]["name"], "LoginProcedure")
        self.assertEqual(obj["props"]["description"], "Procedure to log in")
        self.assertIn("steps", obj["props"])
        self.assertEqual(obj["isPrototype"], False)
    
    def test_save_object_updates_properties(self):
        """Test saving an object updates its properties."""
        # Create an object
        obj = self.orm.create_object(
            prototype_name="Procedure",
            properties={
                "name": "TestProcedure",
                "description": "Original description",
            },
            embed_fn=lambda x: [1.0, 0.0],
        )
        
        original_uuid = obj["uuid"]
        
        # Update properties
        obj["props"]["description"] = "Updated description"
        obj["props"]["status"] = "completed"
        
        # Save
        saved = self.orm.save_object(obj, embed_fn=lambda x: [1.0, 0.0])
        
        self.assertEqual(saved["uuid"], original_uuid)
        self.assertEqual(saved["props"]["description"], "Updated description")
        self.assertEqual(saved["props"]["status"], "completed")
        self.assertEqual(saved["props"]["name"], "TestProcedure")
    
    def test_update_properties(self):
        """Test updating specific properties of an object."""
        # Create an object
        obj = self.orm.create_object(
            prototype_name="Procedure",
            properties={
                "name": "TestProcedure",
                "description": "Original",
            },
            embed_fn=lambda x: [1.0, 0.0],
        )
        
        # Update specific properties
        updated = self.orm.update_properties(
            concept_uuid=obj["uuid"],
            properties={
                "description": "Updated",
                "priority": 5,
            },
            embed_fn=lambda x: [1.0, 0.0],
        )
        
        self.assertEqual(updated["props"]["description"], "Updated")
        self.assertEqual(updated["props"]["priority"], 5)
        self.assertEqual(updated["props"]["name"], "TestProcedure")  # Unchanged
    
    def test_create_and_save_workflow(self):
        """Test a complete workflow: create, modify, save."""
        # Create
        obj = self.ksg.create_object(
            prototype_name="Procedure",
            properties={
                "name": "WorkflowProcedure",
                "description": "Initial state",
            },
        )
        
        # Modify
        obj["props"]["description"] = "Modified state"
        obj["props"]["steps"] = [{"tool": "web.get", "url": "https://example.com"}]
        
        # Save
        saved = self.ksg.save_object(obj)
        
        # Verify
        self.assertEqual(saved["props"]["description"], "Modified state")
        self.assertIn("steps", saved["props"])
        
        # Reload and verify persistence
        reloaded = self.ksg.get_concept_hydrated(saved["uuid"])
        self.assertEqual(reloaded["props"]["description"], "Modified state")
        self.assertIn("steps", reloaded["props"])


if __name__ == "__main__":
    unittest.main()

