"""Integration tests for agent with KnowShowGo service client."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import unittest
from datetime import datetime, timezone

from services.knowshowgo.client import MockKnowShowGoClient, create_client
from src.personal_assistant.models import Node, Edge, Provenance


class TestMockKnowShowGoClientIntegration(unittest.TestCase):
    """Test MockKnowShowGoClient as replacement for embedded KnowShowGoAPI."""
    
    def setUp(self):
        self.client = create_client(use_mock=True, embed_fn=lambda x: [0.1, 0.2, 0.3])
    
    def test_create_and_retrieve_concept(self):
        """Test concept creation and retrieval workflow."""
        # Create a concept
        uuid = self.client.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "TestProcedure", "steps": ["step1", "step2"]},
            embedding=[0.1, 0.2, 0.3]
        )
        
        # Retrieve it
        concept = self.client.get_concept(uuid)
        
        self.assertEqual(concept["props"]["name"], "TestProcedure")
        self.assertEqual(concept["props"]["steps"], ["step1", "step2"])
    
    def test_search_finds_created_concepts(self):
        """Test that search returns created concepts."""
        # Create concepts
        self.client.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "LinkedIn Login Procedure"},
        )
        self.client.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "GitHub Login Procedure"},
        )
        
        # Search
        results = self.client.search("Login", top_k=10)
        
        self.assertGreaterEqual(len(results), 2)
    
    def test_pattern_storage_and_retrieval(self):
        """Test form pattern workflow."""
        # Store pattern
        pattern_uuid = self.client.store_cpms_pattern(
            pattern_name="linkedin.com/login",
            pattern_data={
                "form_type": "login",
                "fields": [
                    {"type": "email", "selector": "#username"},
                    {"type": "password", "selector": "#password"},
                ]
            }
        )
        
        # Find pattern
        matches = self.client.find_best_cpms_pattern(
            url="https://linkedin.com/login",
            form_type="login"
        )
        
        self.assertGreaterEqual(len(matches), 1)
        self.assertEqual(matches[0]["concept"]["uuid"], pattern_uuid)
    
    def test_upsert_node_workflow(self):
        """Test node upsert for storing arbitrary data."""
        # Store a credential
        cred_uuid = self.client.upsert(
            kind="Credential",
            props={
                "domain": "example.com",
                "username": "test@example.com",
                "password": "secret123"
            },
            labels=["Credential", "example.com"]
        )
        
        self.assertIsNotNone(cred_uuid)
        
        # Verify it's searchable
        results = self.client.search("example.com", top_k=5)
        found = any(r["uuid"] == cred_uuid for r in results)
        self.assertTrue(found)
    
    def test_upsert_edge_workflow(self):
        """Test edge creation between concepts."""
        # Create two nodes
        node1 = self.client.upsert(kind="A", props={"name": "NodeA"})
        node2 = self.client.upsert(kind="B", props={"name": "NodeB"})
        
        # Create edge
        edge_uuid = self.client.upsert(
            kind="Edge",
            props={"created_at": datetime.now(timezone.utc).isoformat()},
            from_node=node1,
            to_node=node2,
            rel="related_to"
        )
        
        self.assertIsNotNone(edge_uuid)
        self.assertIn(edge_uuid, self.client.edges)


class TestKnowShowGoClientFallback(unittest.TestCase):
    """Test fallback behavior when service is unavailable."""
    
    def test_is_available_returns_false_for_unreachable_service(self):
        """Real client should return False when service unreachable."""
        from services.knowshowgo.client import KnowShowGoClient
        
        client = KnowShowGoClient(base_url="http://localhost:99999")  # Invalid port
        self.assertFalse(client.is_available())
    
    def test_mock_client_always_available(self):
        """Mock client should always be available."""
        client = create_client(use_mock=True)
        self.assertTrue(client.is_available())


class TestPrototypeManagement(unittest.TestCase):
    """Test prototype listing and management."""
    
    def setUp(self):
        self.client = create_client(use_mock=True)
    
    def test_list_prototypes_returns_standard_set(self):
        """Should have standard prototypes initialized."""
        prototypes = self.client.list_prototypes()
        
        names = [p["props"]["name"] for p in prototypes]
        self.assertIn("Concept", names)
        self.assertIn("Procedure", names)
        self.assertIn("Credential", names)
        self.assertIn("FormPattern", names)
        self.assertIn("QueueItem", names)
    
    def test_created_concepts_inherit_from_prototype(self):
        """Created concepts should have prototype_uuid in props."""
        uuid = self.client.create_concept(
            prototype_uuid="proto-procedure",
            json_obj={"name": "Test"}
        )
        
        concept = self.client.get_concept(uuid)
        self.assertEqual(concept["props"]["prototype_uuid"], "proto-procedure")


class TestSearchFiltering(unittest.TestCase):
    """Test search with various filters."""
    
    def setUp(self):
        self.client = create_client(use_mock=True)
        
        # Create mixed content
        self.client.upsert(kind="Credential", props={"name": "TestCred"})
        self.client.upsert(kind="Procedure", props={"name": "TestProc"})
        self.client.upsert(kind="Task", props={"name": "TestTask"})
    
    def test_search_with_kind_filter(self):
        """Search should respect kind filter."""
        results = self.client.search("Test", filters={"kind": "Credential"})
        
        for r in results:
            # Should only have Credentials (or prototypes are excluded anyway)
            if not r.get("props", {}).get("isPrototype"):
                self.assertEqual(r["kind"], "Credential")


if __name__ == "__main__":
    unittest.main()
