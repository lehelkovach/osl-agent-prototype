"""Tests for KnowShowGo Client."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import pytest
from unittest.mock import patch, MagicMock

from services.knowshowgo.client import (
    KnowShowGoClient,
    MockKnowShowGoClient,
    KnowShowGoServiceError,
    create_client
)


class TestMockClient:
    """Tests for MockKnowShowGoClient."""
    
    def test_health(self):
        client = MockKnowShowGoClient()
        health = client.health()
        assert health["status"] == "ok"
        assert health["version"] == "mock"
    
    def test_is_available(self):
        client = MockKnowShowGoClient()
        assert client.is_available() is True
    
    def test_create_concept(self):
        client = MockKnowShowGoClient()
        uuid = client.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "Test", "value": 1},
            embedding=[0.1, 0.2]
        )
        assert uuid is not None
        assert len(uuid) > 0
        
        # Verify it was stored
        concept = client.get_concept(uuid)
        assert concept["props"]["name"] == "Test"
    
    def test_get_concept_not_found(self):
        client = MockKnowShowGoClient()
        with pytest.raises(KnowShowGoServiceError):
            client.get_concept("nonexistent")
    
    def test_search(self):
        client = MockKnowShowGoClient()
        
        # Create some data
        client.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "Login Form"},
            embedding=[]
        )
        
        results = client.search("Login", top_k=5)
        assert len(results) >= 1
    
    def test_upsert_node(self):
        client = MockKnowShowGoClient()
        uuid = client.upsert(
            kind="Task",
            props={"title": "Test Task"},
            labels=["Task"]
        )
        assert uuid is not None
    
    def test_upsert_edge(self):
        client = MockKnowShowGoClient()
        
        # Create nodes
        node1 = client.upsert(kind="A", props={"name": "A"})
        node2 = client.upsert(kind="B", props={"name": "B"})
        
        # Create edge
        edge_uuid = client.upsert(
            kind="Edge",
            props={"weight": 0.5},
            from_node=node1,
            to_node=node2,
            rel="related"
        )
        assert edge_uuid is not None
        assert edge_uuid in client.edges
    
    def test_store_pattern(self):
        client = MockKnowShowGoClient()
        uuid = client.store_cpms_pattern(
            pattern_name="Test Pattern",
            pattern_data={"form_type": "login"},
            embedding=[0.1]
        )
        assert uuid is not None
        assert uuid in client.nodes
        assert client.nodes[uuid]["kind"] == "FormPattern"
    
    def test_find_patterns(self):
        client = MockKnowShowGoClient()
        
        # Store a pattern
        client.store_cpms_pattern(
            pattern_name="LinkedIn Login",
            pattern_data={"form_type": "login", "url": "linkedin.com"}
        )
        
        # Find it
        matches = client.find_best_cpms_pattern(
            url="https://linkedin.com/login",
            form_type="login"
        )
        assert len(matches) >= 1
    
    def test_list_prototypes(self):
        client = MockKnowShowGoClient()
        prototypes = client.list_prototypes()
        assert len(prototypes) >= 5
        names = [p["props"]["name"] for p in prototypes]
        assert "Concept" in names


class TestCreateClient:
    """Tests for client factory function."""
    
    def test_create_mock_client(self):
        client = create_client(use_mock=True)
        assert isinstance(client, MockKnowShowGoClient)
    
    def test_create_real_client(self):
        client = create_client(use_mock=False, base_url="http://test:8001")
        assert isinstance(client, KnowShowGoClient)
        assert client.base_url == "http://test:8001"
    
    def test_create_client_with_embed_fn(self):
        embed_fn = lambda x: [0.1, 0.2]
        client = create_client(use_mock=True, embed_fn=embed_fn)
        assert client.embed_fn is not None


class TestRealClient:
    """Tests for KnowShowGoClient (mocked HTTP)."""
    
    def test_client_init_default_url(self):
        client = KnowShowGoClient()
        assert "localhost:8001" in client.base_url
    
    def test_client_init_custom_url(self):
        client = KnowShowGoClient(base_url="http://custom:9000")
        assert client.base_url == "http://custom:9000"
    
    def test_client_strips_trailing_slash(self):
        client = KnowShowGoClient(base_url="http://test:8001/")
        assert client.base_url == "http://test:8001"
    
    @patch("services.knowshowgo.client.requests.request")
    def test_health_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok", "version": "0.1.0"}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response
        
        client = KnowShowGoClient(base_url="http://test:8001")
        health = client.health()
        
        assert health["status"] == "ok"
        mock_request.assert_called_once()
    
    @patch("services.knowshowgo.client.requests.request")
    def test_is_available_true(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response
        
        client = KnowShowGoClient(base_url="http://test:8001")
        assert client.is_available() is True
    
    @patch("services.knowshowgo.client.requests.request")
    def test_is_available_false_on_error(self, mock_request):
        mock_request.side_effect = Exception("Connection refused")
        
        client = KnowShowGoClient(base_url="http://test:8001")
        assert client.is_available() is False
    
    @patch("services.knowshowgo.client.requests.request")
    def test_create_concept(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "uuid": "test-uuid",
            "kind": "Concept",
            "props": {"name": "Test"}
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response
        
        client = KnowShowGoClient(base_url="http://test:8001")
        uuid = client.create_concept(
            prototype_uuid="proto-concept",
            json_obj={"name": "Test"},
            embedding=[0.1]
        )
        
        assert uuid == "test-uuid"
    
    @patch("services.knowshowgo.client.requests.request")
    def test_search(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "results": [
                {"uuid": "1", "kind": "Concept", "props": {"name": "Test"}, "score": 0.8}
            ],
            "total": 1,
            "query": "test"
        }
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response
        
        client = KnowShowGoClient(base_url="http://test:8001")
        results = client.search("test", top_k=5)
        
        assert len(results) == 1
        assert results[0]["uuid"] == "1"
    
    @patch("services.knowshowgo.client.requests.request")
    def test_connection_error(self, mock_request):
        from requests.exceptions import ConnectionError
        mock_request.side_effect = ConnectionError("Connection refused")
        
        client = KnowShowGoClient(base_url="http://test:8001")
        with pytest.raises(KnowShowGoServiceError) as exc:
            client.health()
        
        assert "Cannot connect" in str(exc.value)


class TestClientWithEmbedding:
    """Tests for client embedding generation."""
    
    def test_mock_client_uses_embed_fn(self):
        embed_calls = []
        def embed_fn(text):
            embed_calls.append(text)
            return [0.1, 0.2, 0.3]
        
        client = MockKnowShowGoClient(embed_fn=embed_fn)
        # Mock client doesn't auto-generate embeddings, so this just tests setup
        assert client.embed_fn is not None
    
    @patch("services.knowshowgo.client.requests.request")
    def test_real_client_generates_embedding_for_search(self, mock_request):
        mock_response = MagicMock()
        mock_response.json.return_value = {"results": [], "total": 0, "query": "test"}
        mock_response.raise_for_status = MagicMock()
        mock_request.return_value = mock_response
        
        embed_calls = []
        def embed_fn(text):
            embed_calls.append(text)
            return [0.1, 0.2, 0.3]
        
        client = KnowShowGoClient(base_url="http://test:8001", embed_fn=embed_fn)
        client.search("test query")
        
        assert len(embed_calls) == 1
        assert embed_calls[0] == "test query"
