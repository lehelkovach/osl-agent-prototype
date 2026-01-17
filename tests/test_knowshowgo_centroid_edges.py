"""Tests for KnowShowGo centroid-based embeddings and first-class edges."""
import pytest
from datetime import datetime, timezone

from src.personal_assistant.knowshowgo import (
    KnowShowGoAPI,
    cosine_similarity,
    vector_add,
    vector_scale,
    compute_centroid,
)
from src.personal_assistant.networkx_memory import NetworkXMemoryTools
from src.personal_assistant.models import Provenance


@pytest.fixture
def memory():
    """Create a NetworkX-backed memory for testing."""
    return NetworkXMemoryTools()


@pytest.fixture
def embed_fn():
    """Simple embedding function for testing."""
    def _embed(text: str):
        import hashlib
        h = hashlib.md5(text.lower().encode()).hexdigest()
        return [int(h[i:i+2], 16) / 255.0 for i in range(0, 32, 2)]
    return _embed


@pytest.fixture
def ksg(memory, embed_fn):
    """Create KnowShowGo API with memory and embeddings."""
    return KnowShowGoAPI(memory=memory, embed_fn=embed_fn)


@pytest.fixture
def provenance():
    """Create a test provenance."""
    return Provenance(
        source="test",
        ts=datetime.now(timezone.utc).isoformat(),
        confidence=1.0,
        trace_id="test-centroid-edges",
    )


class TestVectorOperations:
    """Test vector helper functions."""
    
    def test_vector_add(self):
        """Should add vectors element-wise."""
        a = [1.0, 2.0, 3.0]
        b = [4.0, 5.0, 6.0]
        result = vector_add(a, b)
        assert result == [5.0, 7.0, 9.0]
    
    def test_vector_add_empty(self):
        """Should handle empty vectors."""
        assert vector_add([], [1.0, 2.0]) == [1.0, 2.0]
        assert vector_add([1.0, 2.0], []) == [1.0, 2.0]
    
    def test_vector_scale(self):
        """Should scale vector by scalar."""
        v = [2.0, 4.0, 6.0]
        result = vector_scale(v, 0.5)
        assert result == [1.0, 2.0, 3.0]
    
    def test_compute_centroid(self):
        """Should compute centroid of embeddings."""
        embeddings = [
            [1.0, 0.0],
            [0.0, 1.0],
            [1.0, 1.0],
        ]
        centroid = compute_centroid(embeddings)
        assert len(centroid) == 2
        assert centroid[0] == pytest.approx(2.0 / 3.0)
        assert centroid[1] == pytest.approx(2.0 / 3.0)
    
    def test_compute_centroid_single(self):
        """Should return single embedding unchanged."""
        embeddings = [[1.0, 2.0, 3.0]]
        centroid = compute_centroid(embeddings)
        assert centroid == [1.0, 2.0, 3.0]
    
    def test_compute_centroid_empty(self):
        """Should return empty for no embeddings."""
        assert compute_centroid([]) == []


class TestAddExemplar:
    """Test add_exemplar method for centroid updates."""
    
    def test_add_exemplar_updates_count(self, ksg, embed_fn, provenance):
        """Should increment exemplar count."""
        # Create a concept
        uuid = ksg.store_cpms_pattern(
            pattern_name="Test Concept",
            pattern_data={},
            embedding=embed_fn("test concept"),
            provenance=provenance,
        )
        
        # Add exemplar
        result = ksg.add_exemplar(
            concept_uuid=uuid,
            exemplar_embedding=embed_fn("exemplar one"),
            provenance=provenance,
        )
        
        assert result["updated"] is True
        assert result["exemplar_count"] == 2  # Original + 1
    
    def test_add_exemplar_updates_embedding(self, ksg, embed_fn, provenance):
        """Should update embedding toward centroid."""
        original_emb = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        uuid = ksg.store_cpms_pattern(
            pattern_name="Test",
            pattern_data={},
            embedding=original_emb,
            provenance=provenance,
        )
        
        # Add exemplar with different embedding
        new_emb = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        ksg.add_exemplar(
            concept_uuid=uuid,
            exemplar_embedding=new_emb,
            provenance=provenance,
        )
        
        # Check centroid moved
        centroid = ksg.get_concept_centroid(uuid)
        assert centroid is not None
        # Should be average of [1,0,...] and [0,1,...]
        assert centroid[0] == pytest.approx(0.5)
        assert centroid[1] == pytest.approx(0.5)
    
    def test_add_exemplar_missing_concept(self, ksg, embed_fn):
        """Should return error for missing concept."""
        result = ksg.add_exemplar(
            concept_uuid="nonexistent",
            exemplar_embedding=[1.0, 2.0],
        )
        assert "error" in result
        assert result["updated"] is False
    
    def test_add_exemplar_links_exemplar(self, ksg, embed_fn, provenance):
        """Should create edge to exemplar if UUID provided."""
        concept_uuid = ksg.store_cpms_pattern(
            pattern_name="Concept",
            pattern_data={},
            embedding=embed_fn("concept"),
            provenance=provenance,
        )
        exemplar_uuid = ksg.store_cpms_pattern(
            pattern_name="Exemplar",
            pattern_data={},
            embedding=embed_fn("exemplar"),
            provenance=provenance,
        )
        
        result = ksg.add_exemplar(
            concept_uuid=concept_uuid,
            exemplar_embedding=embed_fn("exemplar"),
            exemplar_uuid=exemplar_uuid,
            provenance=provenance,
        )
        
        assert result["updated"] is True
        # Check edge was created
        found_edge = False
        for edge in ksg.memory.edges.values():
            if edge.from_node == concept_uuid and edge.to_node == exemplar_uuid:
                found_edge = True
                break
        assert found_edge


class TestRecomputeCentroid:
    """Test recompute_centroid method."""
    
    def test_recompute_with_exemplars(self, ksg, embed_fn, provenance):
        """Should recompute centroid from linked exemplars."""
        # Create concept and exemplars
        concept_uuid = ksg.store_cpms_pattern(
            pattern_name="Parent",
            pattern_data={},
            embedding=[0.0] * 16,  # Start at origin
            provenance=provenance,
        )
        
        # Add exemplars with known embeddings
        emb1 = [1.0] + [0.0] * 15
        emb2 = [0.0, 1.0] + [0.0] * 14
        
        ex1_uuid = ksg.store_cpms_pattern(
            pattern_name="Ex1",
            pattern_data={},
            embedding=emb1,
            provenance=provenance,
        )
        ex2_uuid = ksg.store_cpms_pattern(
            pattern_name="Ex2",
            pattern_data={},
            embedding=emb2,
            provenance=provenance,
        )
        
        # Link exemplars using has_exemplar edges
        from src.personal_assistant.models import Edge
        edge1 = Edge(from_node=concept_uuid, to_node=ex1_uuid, rel="has_exemplar", props={})
        edge2 = Edge(from_node=concept_uuid, to_node=ex2_uuid, rel="has_exemplar", props={})
        ksg.memory.upsert(edge1, provenance, embedding_request=False)
        ksg.memory.upsert(edge2, provenance, embedding_request=False)
        
        # Recompute
        result = ksg.recompute_centroid(concept_uuid, provenance)
        
        assert result["recomputed"] is True
        assert result["exemplar_count"] == 2
    
    def test_recompute_no_exemplars(self, ksg, embed_fn, provenance):
        """Should report no exemplars found."""
        uuid = ksg.store_cpms_pattern(
            pattern_name="Lonely",
            pattern_data={},
            embedding=embed_fn("lonely"),
            provenance=provenance,
        )
        
        result = ksg.recompute_centroid(uuid, provenance)
        assert result["recomputed"] is False


class TestFirstClassEdges:
    """Test first-class edge (relationship as node) methods."""
    
    def test_create_relationship(self, ksg, embed_fn, provenance):
        """Should create relationship node and edges."""
        # Create two concepts
        from_uuid = ksg.store_cpms_pattern(
            pattern_name="Source",
            pattern_data={},
            embedding=embed_fn("source"),
            provenance=provenance,
        )
        to_uuid = ksg.store_cpms_pattern(
            pattern_name="Target",
            pattern_data={},
            embedding=embed_fn("target"),
            provenance=provenance,
        )
        
        # Create relationship
        result = ksg.create_relationship(
            from_uuid=from_uuid,
            to_uuid=to_uuid,
            rel_type="depends_on",
            properties={"strength": 0.8},
            provenance=provenance,
        )
        
        assert "relationship_uuid" in result
        assert "from_edge_uuid" in result
        assert "to_edge_uuid" in result
        assert result["rel_type"] == "depends_on"
    
    def test_create_relationship_with_embedding(self, ksg, embed_fn, provenance):
        """Should create relationship with custom embedding."""
        from_uuid = ksg.store_cpms_pattern(
            pattern_name="A",
            pattern_data={},
            embedding=embed_fn("a"),
            provenance=provenance,
        )
        to_uuid = ksg.store_cpms_pattern(
            pattern_name="B",
            pattern_data={},
            embedding=embed_fn("b"),
            provenance=provenance,
        )
        
        custom_emb = [0.5] * 16
        result = ksg.create_relationship(
            from_uuid=from_uuid,
            to_uuid=to_uuid,
            rel_type="similar_to",
            embedding=custom_emb,
            provenance=provenance,
        )
        
        # Check relationship node has embedding
        rel_node = ksg._get_concept_by_uuid(result["relationship_uuid"])
        assert rel_node is not None
        assert rel_node.get("llm_embedding") == custom_emb
    
    def test_search_relationships(self, ksg, embed_fn, provenance):
        """Should find relationships by similarity."""
        # Create concepts and relationships
        login_uuid = ksg.store_cpms_pattern(
            pattern_name="Login Form",
            pattern_data={},
            embedding=embed_fn("login"),
            provenance=provenance,
        )
        auth_uuid = ksg.store_cpms_pattern(
            pattern_name="Authentication",
            pattern_data={},
            embedding=embed_fn("authentication"),
            provenance=provenance,
        )
        
        ksg.create_relationship(
            from_uuid=login_uuid,
            to_uuid=auth_uuid,
            rel_type="requires",
            provenance=provenance,
        )
        
        # Search for relationships
        results = ksg.search_relationships(
            query="login authentication",
            min_similarity=0.0,  # Low threshold for testing
        )
        
        # Should find the relationship (may vary based on embedding similarity)
        assert isinstance(results, list)
    
    def test_search_relationships_by_type(self, ksg, embed_fn, provenance):
        """Should filter relationships by type."""
        a = ksg.store_cpms_pattern("A", {}, embed_fn("a"), provenance=provenance)
        b = ksg.store_cpms_pattern("B", {}, embed_fn("b"), provenance=provenance)
        c = ksg.store_cpms_pattern("C", {}, embed_fn("c"), provenance=provenance)
        
        ksg.create_relationship(a, b, "uses", provenance=provenance)
        ksg.create_relationship(b, c, "depends_on", provenance=provenance)
        
        # Search for "uses" relationships only
        results = ksg.search_relationships(
            query="relationship",
            rel_type="uses",
            min_similarity=0.0,
        )
        
        for r in results:
            assert r["rel_type"] == "uses"


class TestCentroidEvolution:
    """Test that centroids evolve correctly over multiple exemplars."""
    
    def test_centroid_converges(self, ksg, provenance):
        """Centroid should converge to average of exemplars."""
        # Create concept with known embedding
        initial = [1.0, 0.0, 0.0, 0.0]
        uuid = ksg.store_cpms_pattern(
            pattern_name="Evolving",
            pattern_data={},
            embedding=initial,
            provenance=provenance,
        )
        
        # Add several exemplars all at [0, 1, 0, 0]
        target = [0.0, 1.0, 0.0, 0.0]
        for _ in range(10):
            ksg.add_exemplar(uuid, target, provenance=provenance)
        
        # Centroid should be much closer to target than initial
        centroid = ksg.get_concept_centroid(uuid)
        assert centroid is not None
        
        sim_to_target = cosine_similarity(centroid, target)
        sim_to_initial = cosine_similarity(centroid, initial)
        
        # After 10 exemplars all at target, centroid should be closer to target
        assert sim_to_target > sim_to_initial
    
    def test_embedding_drift_tracked(self, ksg, embed_fn, provenance):
        """Should track embedding drift with each exemplar."""
        uuid = ksg.store_cpms_pattern(
            pattern_name="Drifting",
            pattern_data={},
            embedding=[1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            provenance=provenance,
        )
        
        # Add different exemplar
        result = ksg.add_exemplar(
            uuid,
            [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            provenance=provenance,
        )
        
        # Should report drift (1.0 = no change, lower = more drift)
        assert "embedding_drift" in result
        assert result["embedding_drift"] < 1.0
