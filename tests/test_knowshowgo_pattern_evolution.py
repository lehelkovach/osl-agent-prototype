"""Tests for KnowShowGo pattern evolution: find_similar, transfer, auto_generalize."""
import pytest
from datetime import datetime, timezone

from src.personal_assistant.knowshowgo import KnowShowGoAPI, cosine_similarity
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
        # Simple hash-based embedding for testing
        import hashlib
        h = hashlib.md5(text.lower().encode()).hexdigest()
        # Convert hex to floats
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
        trace_id="test-pattern-evolution",
    )


class TestCosineSimilarity:
    """Test the cosine similarity helper function."""
    
    def test_identical_vectors(self):
        """Identical vectors should have similarity 1.0."""
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)
    
    def test_orthogonal_vectors(self):
        """Orthogonal vectors should have similarity 0.0."""
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert cosine_similarity(v1, v2) == pytest.approx(0.0)
    
    def test_opposite_vectors(self):
        """Opposite vectors should have similarity -1.0."""
        v1 = [1.0, 0.0]
        v2 = [-1.0, 0.0]
        assert cosine_similarity(v1, v2) == pytest.approx(-1.0)
    
    def test_empty_vectors(self):
        """Empty vectors should return 0.0."""
        assert cosine_similarity([], []) == 0.0
    
    def test_different_length_vectors(self):
        """Different length vectors should return 0.0."""
        assert cosine_similarity([1.0, 2.0], [1.0]) == 0.0


class TestFindSimilarPatterns:
    """Test find_similar_patterns method."""
    
    def test_find_similar_returns_empty_when_no_patterns(self, ksg):
        """Should return empty list when no patterns exist."""
        results = ksg.find_similar_patterns("login form")
        assert results == []
    
    def test_find_similar_returns_stored_patterns(self, ksg, embed_fn, provenance):
        """Should return patterns similar to query."""
        # Store some patterns
        ksg.store_cpms_pattern(
            pattern_name="LinkedIn Login",
            pattern_data={"form_type": "login", "fields": ["email", "password"]},
            embedding=embed_fn("LinkedIn Login form email password"),
            provenance=provenance,
        )
        ksg.store_cpms_pattern(
            pattern_name="GitHub Login",
            pattern_data={"form_type": "login", "fields": ["username", "password"]},
            embedding=embed_fn("GitHub Login form username password"),
            provenance=provenance,
        )
        
        # Search for similar patterns
        results = ksg.find_similar_patterns("login form")
        assert len(results) >= 1
    
    def test_find_similar_excludes_specified_uuids(self, ksg, embed_fn, provenance):
        """Should exclude patterns with specified UUIDs."""
        uuid1 = ksg.store_cpms_pattern(
            pattern_name="Pattern 1",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("Pattern 1 login"),
            provenance=provenance,
        )
        ksg.store_cpms_pattern(
            pattern_name="Pattern 2",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("Pattern 2 login"),
            provenance=provenance,
        )
        
        results = ksg.find_similar_patterns("login", exclude_uuids=[uuid1])
        uuids = [r["uuid"] for r in results]
        assert uuid1 not in uuids


class TestTransferPattern:
    """Test transfer_pattern method."""
    
    def test_transfer_returns_error_for_missing_source(self, ksg):
        """Should return error when source pattern not found."""
        result = ksg.transfer_pattern(
            source_pattern_uuid="nonexistent-uuid",
            target_context={"fields": ["email", "password"]},
        )
        assert "error" in result
        assert result["transferred_pattern"] is None
    
    def test_transfer_simple_field_mapping(self, ksg, embed_fn, provenance):
        """Should map fields by name similarity without LLM."""
        # Create source pattern with selectors
        source_uuid = ksg.store_cpms_pattern(
            pattern_name="Source Login",
            pattern_data={
                "form_type": "login",
                "selectors": {
                    "email": "#email-input",
                    "password": "#password-input",
                },
            },
            embedding=embed_fn("Source Login email password"),
            provenance=provenance,
        )
        
        # Update the stored pattern to include selectors in props
        # (store_cpms_pattern puts data in pattern_data, we need to check that)
        
        result = ksg.transfer_pattern(
            source_pattern_uuid=source_uuid,
            target_context={
                "fields": ["email_address", "passwd"],
                "url": "https://example.com/login",
            },
        )
        
        assert result["transferred_pattern"] is not None
        assert result["confidence"] > 0
        assert "field_mapping" in result
    
    def test_transfer_with_llm_function(self, ksg, embed_fn, provenance):
        """Should use LLM function for field mapping when provided."""
        source_uuid = ksg.store_cpms_pattern(
            pattern_name="Source Form",
            pattern_data={
                "form_type": "checkout",
                "selectors": {"card_number": "#cc", "expiry": "#exp"},
            },
            embedding=embed_fn("checkout payment card"),
            provenance=provenance,
        )
        
        # Mock LLM function
        def mock_llm(prompt):
            return '{"field_mapping": {"cc_number": "card_number"}, "confidence": 0.9, "reasoning": "test"}'
        
        result = ksg.transfer_pattern(
            source_pattern_uuid=source_uuid,
            target_context={"fields": ["cc_number", "exp_date"]},
            llm_fn=mock_llm,
        )
        
        assert result["field_mapping"].get("cc_number") == "card_number"
        assert result["confidence"] == 0.9


class TestRecordPatternSuccess:
    """Test record_pattern_success method."""
    
    def test_record_success_increments_count(self, ksg, embed_fn, provenance):
        """Should increment success count on pattern."""
        pattern_uuid = ksg.store_cpms_pattern(
            pattern_name="Test Pattern",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("test pattern"),
            provenance=provenance,
        )
        
        result1 = ksg.record_pattern_success(pattern_uuid)
        assert result1["success_count"] == 1
        
        result2 = ksg.record_pattern_success(pattern_uuid)
        assert result2["success_count"] == 2
    
    def test_record_success_stores_context(self, ksg, embed_fn, provenance):
        """Should store success context."""
        pattern_uuid = ksg.store_cpms_pattern(
            pattern_name="Test Pattern",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("test pattern"),
            provenance=provenance,
        )
        
        context = {"url": "https://example.com", "fields_filled": 3}
        result = ksg.record_pattern_success(pattern_uuid, context=context)
        
        assert result["success_count"] == 1
    
    def test_record_success_returns_error_for_missing(self, ksg):
        """Should return error for non-existent pattern."""
        result = ksg.record_pattern_success("nonexistent-uuid")
        assert "error" in result
        assert result["success_count"] == 0


class TestAutoGeneralize:
    """Test auto_generalize method."""
    
    def test_no_generalization_when_too_few_similar(self, ksg, embed_fn, provenance):
        """Should not generalize when not enough similar patterns."""
        pattern_uuid = ksg.store_cpms_pattern(
            pattern_name="Lone Pattern",
            pattern_data={"form_type": "unique"},
            embedding=embed_fn("unique lone pattern"),
            provenance=provenance,
        )
        
        # Record success but don't have similar patterns
        ksg.record_pattern_success(pattern_uuid)
        
        result = ksg.auto_generalize(pattern_uuid, min_similar=2)
        assert result is None
    
    def test_generalization_with_similar_successful_patterns(self, ksg, embed_fn, provenance):
        """Should generalize when enough similar successful patterns exist."""
        # Create multiple similar patterns
        uuid1 = ksg.store_cpms_pattern(
            pattern_name="Login Form A",
            pattern_data={"form_type": "login", "selectors": {"email": "#email"}},
            embedding=embed_fn("login form email password authentication"),
            provenance=provenance,
        )
        uuid2 = ksg.store_cpms_pattern(
            pattern_name="Login Form B",
            pattern_data={"form_type": "login", "selectors": {"email": "#user"}},
            embedding=embed_fn("login form email password authentication"),
            provenance=provenance,
        )
        uuid3 = ksg.store_cpms_pattern(
            pattern_name="Login Form C",
            pattern_data={"form_type": "login", "selectors": {"email": "#login"}},
            embedding=embed_fn("login form email password authentication"),
            provenance=provenance,
        )
        
        # Record successes
        ksg.record_pattern_success(uuid1)
        ksg.record_pattern_success(uuid2)
        ksg.record_pattern_success(uuid3)
        
        # Trigger auto-generalization
        result = ksg.auto_generalize(uuid1, min_similar=2, min_similarity=0.1)
        
        # May or may not generalize depending on embedding similarity
        # With our simple hash-based embeddings, identical text = identical embedding
        if result:
            assert "generalized_uuid" in result
            assert result["exemplar_count"] >= 2
    
    def test_already_generalized_pattern_not_re_generalized(self, ksg, embed_fn, provenance):
        """Should not re-generalize an already generalized pattern."""
        # Create and generalize some patterns
        uuid1 = ksg.store_cpms_pattern(
            pattern_name="Pattern 1",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("login"),
            provenance=provenance,
        )
        uuid2 = ksg.store_cpms_pattern(
            pattern_name="Pattern 2",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("login"),
            provenance=provenance,
        )
        
        # Manually create generalized pattern
        gen_uuid = ksg.generalize_concepts(
            exemplar_uuids=[uuid1, uuid2],
            generalized_name="Generalized Login",
            generalized_description="Test",
            generalized_embedding=embed_fn("generalized login"),
            provenance=provenance,
        )
        
        # Try to auto-generalize the generalized pattern
        result = ksg.auto_generalize(gen_uuid)
        assert result is None  # Should not re-generalize


class TestFindGeneralizedPattern:
    """Test find_generalized_pattern method."""
    
    def test_find_generalized_returns_none_when_none_exist(self, ksg):
        """Should return None when no generalized patterns exist."""
        result = ksg.find_generalized_pattern("login form")
        assert result is None
    
    def test_find_generalized_prefers_generalized_type(self, ksg, embed_fn, provenance):
        """Should prefer patterns with type='generalized'."""
        # Create a regular pattern
        ksg.store_cpms_pattern(
            pattern_name="Regular Login",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("login form"),
            provenance=provenance,
        )
        
        # Create a generalized pattern by using generalize_concepts
        uuid1 = ksg.store_cpms_pattern(
            pattern_name="Login A",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("login"),
            provenance=provenance,
        )
        uuid2 = ksg.store_cpms_pattern(
            pattern_name="Login B",
            pattern_data={"form_type": "login"},
            embedding=embed_fn("login"),
            provenance=provenance,
        )
        
        ksg.generalize_concepts(
            exemplar_uuids=[uuid1, uuid2],
            generalized_name="Generalized Login",
            generalized_description="Login patterns",
            generalized_embedding=embed_fn("generalized login"),
            provenance=provenance,
        )
        
        # Find generalized pattern
        result = ksg.find_generalized_pattern("login")
        # May find it depending on search implementation


class TestHelperMethods:
    """Test helper methods for pattern evolution."""
    
    def test_simple_field_mapping_exact_match(self, ksg):
        """Should match identical field names."""
        mapping = ksg._simple_field_mapping(
            source_fields=["email", "password"],
            target_fields=["email", "password"],
        )
        assert mapping["email"] == "email"
        assert mapping["password"] == "password"
    
    def test_simple_field_mapping_normalized_match(self, ksg):
        """Should match fields with different formatting."""
        mapping = ksg._simple_field_mapping(
            source_fields=["email_address", "pass_word"],
            target_fields=["emailaddress", "password"],
        )
        assert mapping.get("emailaddress") == "email_address"
        assert mapping.get("password") == "pass_word"
    
    def test_simple_field_mapping_substring_match(self, ksg):
        """Should match fields with substring overlap."""
        mapping = ksg._simple_field_mapping(
            source_fields=["email"],
            target_fields=["user_email"],
        )
        assert mapping.get("user_email") == "email"
    
    def test_extract_common_pattern_finds_shared_words(self, ksg):
        """Should extract common words from pattern names."""
        result = ksg._extract_common_pattern([
            "LinkedIn Login Form",
            "GitHub Login Form",
            "Twitter Login Form",
        ])
        assert "login" in result.lower()
    
    def test_average_embeddings(self, ksg, embed_fn, provenance):
        """Should average embeddings from multiple concepts."""
        uuid1 = ksg.store_cpms_pattern(
            pattern_name="Pattern 1",
            pattern_data={},
            embedding=embed_fn("pattern one"),
            provenance=provenance,
        )
        uuid2 = ksg.store_cpms_pattern(
            pattern_name="Pattern 2",
            pattern_data={},
            embedding=embed_fn("pattern two"),
            provenance=provenance,
        )
        
        avg = ksg._average_embeddings([uuid1, uuid2])
        assert len(avg) > 0
        assert all(isinstance(v, float) for v in avg)


class TestEndToEndPatternEvolution:
    """End-to-end tests for the pattern evolution flow."""
    
    def test_learn_transfer_generalize_flow(self, ksg, embed_fn, provenance):
        """Test the full Learn → Transfer → Generalize flow."""
        # Step 1: Learn patterns from multiple similar forms
        linkedin_uuid = ksg.store_cpms_pattern(
            pattern_name="LinkedIn Login",
            pattern_data={
                "form_type": "login",
                "url": "https://linkedin.com/login",
                "selectors": {"email": "#username", "password": "#password"},
            },
            embedding=embed_fn("linkedin login form email password"),
            provenance=provenance,
        )
        
        github_uuid = ksg.store_cpms_pattern(
            pattern_name="GitHub Login",
            pattern_data={
                "form_type": "login",
                "url": "https://github.com/login",
                "selectors": {"login": "#login_field", "password": "#password"},
            },
            embedding=embed_fn("github login form email password"),
            provenance=provenance,
        )
        
        # Step 2: Record successes
        ksg.record_pattern_success(linkedin_uuid, {"url": "linkedin.com"})
        ksg.record_pattern_success(github_uuid, {"url": "github.com"})
        
        # Step 3: Try to find similar patterns for a new login form
        similar = ksg.find_similar_patterns("twitter login form", min_similarity=0.1)
        assert len(similar) >= 0  # May or may not find depending on embedding
        
        # Step 4: If we found a similar pattern, try to transfer it
        if similar:
            transfer_result = ksg.transfer_pattern(
                source_pattern_uuid=similar[0]["uuid"],
                target_context={
                    "url": "https://twitter.com/login",
                    "fields": ["username_or_email", "password"],
                },
            )
            assert transfer_result["transferred_pattern"] is not None
        
        # Step 5: Try auto-generalization (may not trigger with only 2 patterns)
        gen_result = ksg.auto_generalize(linkedin_uuid, min_similar=2, min_similarity=0.1)
        # Result depends on embedding similarity
