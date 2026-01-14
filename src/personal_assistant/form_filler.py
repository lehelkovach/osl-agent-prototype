from typing import List, Dict, Any, Optional, Callable
from urllib.parse import urlparse

from src.personal_assistant.tools import MemoryTools

EmbedFn = Callable[[str], List[float]]


def extract_domain(url: str) -> str:
    """Extract domain from URL for matching purposes."""
    if not url:
        return ""
    try:
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove port if present
        if ":" in domain:
            domain = domain.split(":")[0]
        # Remove www. prefix
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


class FormDataRetriever:
    """
    Helper to pull remembered FormData/Identity/Credential/PaymentMethod concepts
    from memory and build an autofill map for form fields.
    Also supports survey answer reuse by matching similar questions.
    
    Enhanced with domain-based credential preference (Milestone B):
    - Prefer credentials associated with the same domain
    - Score credentials by domain match and recency
    """

    SUPPORTED_KINDS = {"FormData", "Identity", "Credential", "PaymentMethod", "SurveyResponse"}

    def __init__(self, memory: MemoryTools, embed_fn: Optional[EmbedFn] = None):
        self.memory = memory
        self.embed_fn = embed_fn

    def fetch_latest(self, query: str = "form data", top_k: int = 10) -> List[Dict[str, Any]]:
        """
        Search memory and filter for supported kinds. Returns raw dicts.
        """
        results = self.memory.search(query, top_k=top_k, query_embedding=None)
        filtered = []
        for r in results:
            kind = r.get("kind") if isinstance(r, dict) else getattr(r, "kind", None)
            if kind in self.SUPPORTED_KINDS:
                filtered.append(r if isinstance(r, dict) else r.__dict__)
        return filtered

    def build_autofill(
        self,
        required_fields: List[str],
        query: str = "form data",
        url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build a field->value map for the requested fields using the most relevant
        supported nodes from memory.
        
        If url is provided, prefers credentials/identity associated with the same domain.
        
        Args:
            required_fields: List of field names needed (e.g., ["email", "password"])
            query: Search query for memory
            url: Optional URL to enable domain-based preference
            
        Returns:
            Dict mapping field names to values
        """
        field_map: Dict[str, Any] = {}
        
        # If we have a URL, try domain-specific lookup first
        if url:
            domain = extract_domain(url)
            if domain:
                # Try to find credentials for this specific domain
                domain_results = self.find_for_domain(domain, top_k=5)
                for node in domain_results:
                    props = node.get("props", {})
                    for f in required_fields:
                        if f not in field_map and f in props and props[f] is not None:
                            field_map[f] = props[f]
        
        # If we still have missing fields, fall back to general search
        missing = [f for f in required_fields if f not in field_map]
        if missing:
            nodes = self.fetch_latest(query=query, top_k=20)
            for node in nodes:
                props = node.get("props", {})
                for f in missing:
                    if f not in field_map and f in props and props[f] is not None:
                        field_map[f] = props[f]
        
        return field_map
    
    def find_for_domain(self, domain: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find credentials, identity, or payment info associated with a specific domain.
        
        Searches memory for nodes with matching domain property or associated URLs.
        
        Args:
            domain: Target domain (e.g., "linkedin.com")
            top_k: Maximum results to return
            
        Returns:
            List of matching nodes, sorted by relevance
        """
        if not domain:
            return []
        
        # Search by domain name
        results = self.memory.search(domain, top_k=top_k * 2, query_embedding=None)
        
        scored: List[tuple] = []
        for r in results:
            node = r if isinstance(r, dict) else r.__dict__
            kind = node.get("kind")
            if kind not in self.SUPPORTED_KINDS:
                continue
            
            props = node.get("props", {})
            score = 0.0
            
            # Check domain property
            domain_match = False
            node_domain = props.get("domain", "")
            if node_domain:
                node_domain_parsed = extract_domain(node_domain)
                if node_domain_parsed == domain:
                    score += 10.0  # Strong domain match
                    domain_match = True
                elif domain in node_domain_parsed or node_domain_parsed in domain:
                    score += 5.0  # Partial domain match
                    domain_match = True
            
            # Check URL property
            node_url = props.get("url", "")
            if node_url:
                url_domain = extract_domain(node_url)
                if url_domain == domain:
                    score += 8.0
                    domain_match = True
                elif domain in url_domain or url_domain in domain:
                    score += 4.0
                    domain_match = True
            
            # Only apply kind bonus if there's a domain match
            if domain_match:
                if kind == "Credential":
                    score += 2.0  # Prefer credentials
                elif kind == "Identity":
                    score += 1.0
            
            # Include only if there's a domain match
            if domain_match and score > 0:
                scored.append((score, node))
        
        # Sort by score and return top_k
        scored.sort(key=lambda x: -x[0])
        return [node for _, node in scored[:top_k]]
    
    def get_missing_fields(
        self,
        required_fields: List[str],
        url: Optional[str] = None
    ) -> List[str]:
        """
        Determine which fields are missing from memory.
        
        Used to prompt user only for fields that aren't stored.
        
        Args:
            required_fields: Fields needed for the form
            url: Optional URL for domain-based lookup
            
        Returns:
            List of field names not found in memory
        """
        existing = self.build_autofill(required_fields, url=url)
        return [f for f in required_fields if f not in existing]
    
    def store_credential(
        self,
        domain: str,
        props: Dict[str, Any],
        concept_uuid: Optional[str] = None
    ) -> Optional[str]:
        """
        Store a credential immediately after user provides it.
        
        Creates a Credential node with the domain and provided properties.
        
        Args:
            domain: Associated domain (e.g., "linkedin.com")
            props: Credential properties (email, password, etc.)
            concept_uuid: Optional UUID for the new credential
            
        Returns:
            UUID of the created credential node
        """
        from uuid import uuid4
        from datetime import datetime, timezone
        from src.personal_assistant.models import Node, Provenance
        
        node_uuid = concept_uuid or str(uuid4())
        cred_props = {
            "domain": domain,
            "stored_at": datetime.now(timezone.utc).isoformat(),
            **props
        }
        
        try:
            node = Node(
                uuid=node_uuid,
                kind="Credential",
                props=cred_props,
                labels=["Credential"],
                llm_embedding=[]
            )
            provenance = Provenance(
                source="user",
                ts=datetime.now(timezone.utc).isoformat(),
                confidence=1.0,
                trace_id=f"cred-{node_uuid[:8]}"
            )
            self.memory.upsert(node, provenance)
            return node_uuid
        except Exception:
            return None

    def match_survey_answers(
        self,
        questions: List[Dict[str, Any]],
        query_embedding: Optional[List[float]] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Match survey questions to stored answers from previous surveys.
        
        Args:
            questions: List of question dicts with "question" (text), "field_name", "label" (optional)
            query_embedding: Optional embedding for the survey context
            top_k: Number of survey responses to search
            
        Returns:
            Dict mapping field_name -> answer value from similar questions
        """
        if not questions:
            return {}
        
        # Search for survey responses
        survey_query = "survey response"
        survey_results = self.memory.search(
            survey_query,
            top_k=top_k,
            query_embedding=query_embedding
        )
        
        # Extract question-answer pairs from survey responses
        answer_map: Dict[str, Any] = {}
        
        for survey_node in survey_results:
            props = survey_node.get("props", {}) if isinstance(survey_node, dict) else getattr(survey_node, "props", {})
            questions_list = props.get("questions", [])
            
            if not questions_list:
                continue
            
            # For each question in the current form, try to match with stored questions
            for current_q in questions:
                current_q_text = current_q.get("question") or current_q.get("label", "")
                current_field = current_q.get("field_name", "")
                
                if not current_q_text:
                    continue
                
                # Try to find a similar question in stored responses
                best_match = None
                best_score = 0.0
                
                for stored_qa in questions_list:
                    stored_q = stored_qa.get("question", "")
                    stored_a = stored_qa.get("answer")
                    
                    if not stored_q or stored_a is None:
                        continue
                    
                    # Simple text similarity (can be enhanced with embeddings)
                    # Check if questions are similar (contain similar keywords)
                    current_words = set(current_q_text.lower().split())
                    stored_words = set(stored_q.lower().split())
                    
                    # Calculate Jaccard similarity
                    intersection = len(current_words & stored_words)
                    union = len(current_words | stored_words)
                    similarity = intersection / union if union > 0 else 0.0
                    
                    # Also check for key terms (experience, years, language, etc.)
                    key_terms = ["experience", "years", "language", "programming", "work", "environment", "preferred", "favorite"]
                    key_matches = sum(1 for term in key_terms if term in current_q_text.lower() and term in stored_q.lower())
                    similarity += key_matches * 0.2  # Boost for key term matches
                    
                    if similarity > best_score and similarity > 0.3:  # Threshold for matching
                        best_score = similarity
                        best_match = stored_a
                
                # If we found a match, use the stored answer
                if best_match is not None and current_field:
                    answer_map[current_field] = best_match
        
        return answer_map
