"""Tests for domain-based credential preference (Milestone B)."""
import unittest
from uuid import uuid4
from datetime import datetime, timezone
from src.personal_assistant.form_filler import FormDataRetriever, extract_domain
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Node, Provenance


def _create_provenance():
    """Create a test provenance object."""
    return Provenance(
        source="test",
        ts=datetime.now(timezone.utc).isoformat(),
        confidence=1.0,
        trace_id="test-trace"
    )


def _upsert_node(memory, uuid, kind, props):
    """Helper to upsert a node with proper Node object."""
    node = Node(
        uuid=uuid,
        kind=kind,
        props=props,
        labels=[kind],
        llm_embedding=[]
    )
    memory.upsert(node, _create_provenance())


class TestExtractDomain(unittest.TestCase):
    """Test domain extraction utility."""
    
    def test_extract_domain_basic(self):
        """Basic domain extraction."""
        self.assertEqual(extract_domain("https://linkedin.com"), "linkedin.com")
        self.assertEqual(extract_domain("https://www.linkedin.com"), "linkedin.com")
        self.assertEqual(extract_domain("http://example.com/path"), "example.com")
    
    def test_extract_domain_with_www(self):
        """Remove www prefix."""
        self.assertEqual(extract_domain("https://www.google.com"), "google.com")
        self.assertEqual(extract_domain("www.facebook.com"), "facebook.com")
    
    def test_extract_domain_without_scheme(self):
        """Handle URLs without http/https."""
        self.assertEqual(extract_domain("twitter.com"), "twitter.com")
        self.assertEqual(extract_domain("example.com/page"), "example.com")
    
    def test_extract_domain_empty(self):
        """Handle empty input."""
        self.assertEqual(extract_domain(""), "")
        self.assertEqual(extract_domain(None), "")


class TestFindForDomain(unittest.TestCase):
    """Test domain-based credential lookup."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_find_for_domain_exact_match(self):
        """Find credentials with exact domain match."""
        # Store a credential for linkedin.com
        _upsert_node(
            self.memory,
            uuid="cred-1",
            kind="Credential",
            props={"domain": "linkedin.com", "email": "user@example.com", "password": "pass123"}
        )
        
        results = self.retriever.find_for_domain("linkedin.com")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["props"]["email"], "user@example.com")
    
    def test_find_for_domain_url_match(self):
        """Find credentials by URL property."""
        _upsert_node(
            self.memory,
            uuid="cred-2",
            kind="Credential",
            props={"url": "https://facebook.com/login", "email": "fb@example.com"}
        )
        
        results = self.retriever.find_for_domain("facebook.com")
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["props"]["email"], "fb@example.com")
    
    def test_find_for_domain_no_match(self):
        """Return empty when no matching domain."""
        _upsert_node(
            self.memory,
            uuid="cred-3",
            kind="Credential",
            props={"domain": "twitter.com", "email": "tw@example.com"}
        )
        
        results = self.retriever.find_for_domain("instagram.com")
        
        self.assertEqual(len(results), 0)
    
    def test_find_for_domain_prefers_credential_kind(self):
        """Prefer Credential kind over Identity."""
        _upsert_node(
            self.memory,
            uuid="id-1",
            kind="Identity",
            props={"domain": "github.com", "name": "John Doe"}
        )
        _upsert_node(
            self.memory,
            uuid="cred-4",
            kind="Credential",
            props={"domain": "github.com", "username": "johndoe", "password": "secret"}
        )
        
        results = self.retriever.find_for_domain("github.com")
        
        self.assertEqual(len(results), 2)
        # Credential should be first due to higher score
        self.assertEqual(results[0]["kind"], "Credential")


class TestBuildAutofillWithDomain(unittest.TestCase):
    """Test autofill building with domain preference."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_build_autofill_prefers_same_domain(self):
        """When URL provided, prefer credentials from same domain."""
        # Store credentials for different domains
        _upsert_node(
            self.memory,
            uuid="cred-twitter",
            kind="Credential",
            props={"domain": "twitter.com", "email": "twitter@example.com", "password": "twpass"}
        )
        _upsert_node(
            self.memory,
            uuid="cred-linkedin",
            kind="Credential",
            props={"domain": "linkedin.com", "email": "linkedin@example.com", "password": "lnpass"}
        )
        
        # Request autofill for LinkedIn
        result = self.retriever.build_autofill(
            required_fields=["email", "password"],
            url="https://www.linkedin.com/login"
        )
        
        self.assertEqual(result["email"], "linkedin@example.com")
        self.assertEqual(result["password"], "lnpass")
    
    def test_build_autofill_fallback_without_domain_match(self):
        """Fall back to general search if no domain match."""
        _upsert_node(
            self.memory,
            uuid="cred-general",
            kind="Credential",
            props={"email": "general@example.com", "password": "genpass"}
        )
        
        # Request autofill for a domain with no specific credential
        result = self.retriever.build_autofill(
            required_fields=["email", "password"],
            url="https://newsite.com"
        )
        
        self.assertEqual(result["email"], "general@example.com")
        self.assertEqual(result["password"], "genpass")
    
    def test_build_autofill_without_url(self):
        """Without URL, use general search."""
        _upsert_node(
            self.memory,
            uuid="cred-any",
            kind="Credential",
            props={"username": "testuser", "password": "testpass"}
        )
        
        result = self.retriever.build_autofill(
            required_fields=["username", "password"]
        )
        
        self.assertEqual(result["username"], "testuser")
        self.assertEqual(result["password"], "testpass")


class TestGetMissingFields(unittest.TestCase):
    """Test detection of missing fields."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_get_missing_fields_all_present(self):
        """No missing fields when all are stored."""
        _upsert_node(
            self.memory,
            uuid="cred-full",
            kind="Credential",
            props={"email": "test@example.com", "password": "pass"}
        )
        
        missing = self.retriever.get_missing_fields(["email", "password"])
        
        self.assertEqual(missing, [])
    
    def test_get_missing_fields_some_missing(self):
        """Identify missing fields."""
        _upsert_node(
            self.memory,
            uuid="cred-partial",
            kind="Credential",
            props={"email": "test@example.com"}
        )
        
        missing = self.retriever.get_missing_fields(["email", "password", "username"])
        
        self.assertIn("password", missing)
        self.assertIn("username", missing)
        self.assertNotIn("email", missing)
    
    def test_get_missing_fields_all_missing(self):
        """All fields missing when nothing stored."""
        missing = self.retriever.get_missing_fields(["card_number", "expiry", "cvv"])
        
        self.assertEqual(set(missing), {"card_number", "expiry", "cvv"})


class TestStoreCredential(unittest.TestCase):
    """Test immediate credential storage."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_store_credential_basic(self):
        """Store a credential and retrieve it."""
        uuid = self.retriever.store_credential(
            domain="github.com",
            props={"username": "devuser", "password": "devpass"}
        )
        
        self.assertIsNotNone(uuid)
        
        # Verify it's stored
        results = self.retriever.find_for_domain("github.com")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["props"]["username"], "devuser")
        self.assertEqual(results[0]["props"]["domain"], "github.com")
    
    def test_store_credential_with_custom_uuid(self):
        """Store credential with specified UUID."""
        custom_uuid = str(uuid4())
        result_uuid = self.retriever.store_credential(
            domain="example.com",
            props={"email": "me@example.com"},
            concept_uuid=custom_uuid
        )
        
        self.assertEqual(result_uuid, custom_uuid)
    
    def test_store_credential_adds_timestamp(self):
        """Stored credential includes timestamp."""
        self.retriever.store_credential(
            domain="test.com",
            props={"key": "value"}
        )
        
        results = self.retriever.find_for_domain("test.com")
        self.assertIn("stored_at", results[0]["props"])


if __name__ == "__main__":
    unittest.main()
