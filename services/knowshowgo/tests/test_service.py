"""Tests for KnowShowGo Service API."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

import pytest
from fastapi.testclient import TestClient

from services.knowshowgo.service import app, store


@pytest.fixture(autouse=True)
def reset_store():
    """Reset store before each test."""
    store.nodes.clear()
    store.edges.clear()
    store._init_prototypes()
    yield


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestHealthEndpoint:
    """Tests for health check endpoint."""
    
    def test_health_returns_ok(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "concepts_count" in data
    
    def test_health_shows_prototype_count(self, client):
        response = client.get("/health")
        data = response.json()
        # Should have initial prototypes
        assert data["concepts_count"] >= 5


class TestConceptsEndpoint:
    """Tests for concept CRUD operations."""
    
    def test_create_concept(self, client):
        response = client.post("/concepts", json={
            "prototype_uuid": "proto-concept",
            "json_obj": {"name": "TestConcept", "value": 42},
            "embedding": [0.1, 0.2, 0.3],
        })
        assert response.status_code == 200
        data = response.json()
        assert "uuid" in data
        assert data["kind"] == "Concept"
        assert data["props"]["name"] == "TestConcept"
    
    def test_create_concept_invalid_prototype(self, client):
        response = client.post("/concepts", json={
            "prototype_uuid": "nonexistent",
            "json_obj": {"name": "Test"},
            "embedding": [],
        })
        assert response.status_code == 404
    
    def test_get_concept(self, client):
        # Create concept first
        create_response = client.post("/concepts", json={
            "prototype_uuid": "proto-concept",
            "json_obj": {"name": "GetTest"},
            "embedding": [],
        })
        concept_uuid = create_response.json()["uuid"]
        
        # Get it back
        response = client.get(f"/concepts/{concept_uuid}")
        assert response.status_code == 200
        data = response.json()
        assert data["uuid"] == concept_uuid
        assert data["props"]["name"] == "GetTest"
    
    def test_get_concept_not_found(self, client):
        response = client.get("/concepts/nonexistent-uuid")
        assert response.status_code == 404


class TestSearchEndpoint:
    """Tests for search operations."""
    
    def test_search_by_query(self, client):
        # Create some concepts
        client.post("/concepts", json={
            "prototype_uuid": "proto-concept",
            "json_obj": {"name": "Login Form Pattern"},
            "embedding": [],
        })
        client.post("/concepts", json={
            "prototype_uuid": "proto-concept",
            "json_obj": {"name": "Billing Form"},
            "embedding": [],
        })
        
        # Search
        response = client.post("/search", json={
            "query": "Login",
            "top_k": 10
        })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert any("Login" in r["props"].get("name", "") for r in data["results"])
    
    def test_search_with_filters(self, client):
        # Create concepts
        client.post("/concepts", json={
            "prototype_uuid": "proto-credential",
            "json_obj": {"name": "Credential1"},
            "embedding": [],
        })
        
        # Search with filter
        response = client.post("/search", json={
            "query": "test",
            "filters": {"kind": "Credential"},
            "top_k": 10
        })
        assert response.status_code == 200
    
    def test_search_empty_results(self, client):
        response = client.post("/search", json={
            "query": "nonexistent-xyz-abc",
            "top_k": 10
        })
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0


class TestUpsertEndpoint:
    """Tests for upsert operations."""
    
    def test_upsert_node(self, client):
        response = client.post("/upsert", json={
            "kind": "Task",
            "props": {"title": "Test Task", "priority": 1},
            "labels": ["Task", "High Priority"],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["type"] == "node"
        assert "uuid" in data
    
    def test_upsert_edge(self, client):
        # Create two nodes first
        node1 = client.post("/upsert", json={
            "kind": "Node1",
            "props": {"name": "A"},
        }).json()
        
        node2 = client.post("/upsert", json={
            "kind": "Node2",
            "props": {"name": "B"},
        }).json()
        
        # Create edge
        response = client.post("/upsert", json={
            "kind": "Edge",
            "from_node": node1["uuid"],
            "to_node": node2["uuid"],
            "rel": "related_to",
            "props": {"weight": 0.8},
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["type"] == "edge"


class TestPatternEndpoints:
    """Tests for pattern storage and matching."""
    
    def test_store_pattern(self, client):
        response = client.post("/patterns/store", json={
            "pattern_name": "LinkedIn Login",
            "pattern_data": {
                "form_type": "login",
                "fields": [
                    {"type": "email", "selector": "#email"},
                    {"type": "password", "selector": "#password"},
                ]
            },
            "embedding": [0.1, 0.2],
        })
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert "uuid" in data
    
    def test_match_patterns(self, client):
        # Store a pattern first
        client.post("/patterns/store", json={
            "pattern_name": "GitHub Login",
            "pattern_data": {"form_type": "login"},
            "embedding": [],
        })
        
        # Try to match
        response = client.post("/patterns/match", json={
            "url": "https://github.com/login",
            "form_type": "login",
            "top_k": 5
        })
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestPrototypesEndpoint:
    """Tests for prototype listing."""
    
    def test_list_prototypes(self, client):
        response = client.get("/prototypes")
        assert response.status_code == 200
        data = response.json()
        assert "prototypes" in data
        assert len(data["prototypes"]) >= 5  # Initial prototypes
        
        # Check for expected prototypes
        names = [p["props"]["name"] for p in data["prototypes"]]
        assert "Concept" in names
        assert "Procedure" in names
        assert "Credential" in names
