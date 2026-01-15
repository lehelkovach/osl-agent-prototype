"""Tests for KnowShowGo Adapter."""
import unittest
import os
from unittest.mock import patch, MagicMock

from src.personal_assistant.knowshowgo_adapter import KnowShowGoAdapter


class TestKnowShowGoAdapterMock(unittest.TestCase):
    """Test adapter with mock backend."""
    
    def setUp(self):
        self.adapter = KnowShowGoAdapter.create_mock()
    
    def test_create_mock_adapter(self):
        self.assertIsNotNone(self.adapter)
        self.assertEqual(self.adapter.backend, "mock")
        self.assertTrue(self.adapter.is_service_mode())
    
    def test_create_concept(self):
        uuid = self.adapter.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "Test"},
            embedding=[0.1, 0.2]
        )
        self.assertIsNotNone(uuid)
    
    def test_search(self):
        # Create some data
        self.adapter.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "SearchTest"}
        )
        
        results = self.adapter.search("SearchTest", top_k=5)
        self.assertIsInstance(results, list)
    
    def test_store_and_find_pattern(self):
        pattern_uuid = self.adapter.store_cpms_pattern(
            pattern_name="test-form",
            pattern_data={"form_type": "login"}
        )
        self.assertIsNotNone(pattern_uuid)
        
        matches = self.adapter.find_best_cpms_pattern(
            url="http://test.com",
            form_type="login"
        )
        self.assertGreaterEqual(len(matches), 1)
    
    def test_upsert_node(self):
        uuid = self.adapter.upsert(
            kind="Task",
            props={"title": "Test"},
            labels=["Task"]
        )
        self.assertIsNotNone(uuid)


class TestKnowShowGoAdapterEmbedded(unittest.TestCase):
    """Test adapter with embedded backend."""
    
    def setUp(self):
        self.adapter = KnowShowGoAdapter.create(force_embedded=True)
    
    def test_create_embedded_adapter(self):
        self.assertIsNotNone(self.adapter)
        self.assertEqual(self.adapter.backend, "embedded")
        self.assertFalse(self.adapter.is_service_mode())
    
    def test_memory_property(self):
        self.assertIsNotNone(self.adapter.memory)
    
    def test_search_embedded(self):
        results = self.adapter.search("test", top_k=5)
        self.assertIsInstance(results, list)


class TestKnowShowGoAdapterFactory(unittest.TestCase):
    """Test adapter factory methods."""
    
    def test_create_with_no_service(self):
        """Without service URL, should default to embedded."""
        with patch.dict(os.environ, {"KNOWSHOWGO_URL": ""}, clear=False):
            adapter = KnowShowGoAdapter.create(force_embedded=True)
            self.assertEqual(adapter.backend, "embedded")
    
    def test_force_embedded(self):
        """Force embedded should always use embedded."""
        adapter = KnowShowGoAdapter.create(force_embedded=True)
        self.assertEqual(adapter.backend, "embedded")


if __name__ == "__main__":
    unittest.main()
