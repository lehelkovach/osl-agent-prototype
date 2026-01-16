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

    def store_survey_response(
        self,
        form_url: str,
        questions_and_answers: List[Dict[str, Any]],
        form_title: Optional[str] = None,
    ) -> Optional[str]:
        """
        Store a completed survey response for future reuse.
        
        Args:
            form_url: URL of the survey form
            questions_and_answers: List of {question, field_name, answer} dicts
            form_title: Optional title of the survey
            
        Returns:
            UUID of the created SurveyResponse node
        """
        from uuid import uuid4
        from datetime import datetime, timezone
        from src.personal_assistant.models import Node, Provenance
        
        node_uuid = str(uuid4())
        props = {
            "form_url": form_url,
            "form_title": form_title or f"Survey at {extract_domain(form_url)}",
            "questions": questions_and_answers,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Also store individual field values for easy lookup
        for qa in questions_and_answers:
            field = qa.get("field_name", "")
            answer = qa.get("answer")
            if field and answer is not None:
                props[field] = answer
        
        try:
            # Create embedding from questions for semantic search
            text_for_embed = form_title or ""
            text_for_embed += " " + " ".join(
                qa.get("question", "") for qa in questions_and_answers
            )
            embedding = []
            if self.embed_fn:
                try:
                    embedding = self.embed_fn(text_for_embed[:500])
                except Exception:
                    pass
            
            node = Node(
                uuid=node_uuid,
                kind="SurveyResponse",
                props=props,
                labels=["SurveyResponse", extract_domain(form_url)],
                llm_embedding=embedding or []
            )
            provenance = Provenance(
                source="survey",
                ts=datetime.now(timezone.utc).isoformat(),
                confidence=1.0,
                trace_id=f"survey-{node_uuid[:8]}"
            )
            self.memory.upsert(node, provenance)
            return node_uuid
        except Exception:
            return None

    def get_missing_survey_fields(
        self,
        required_fields: List[str],
        available_answers: Dict[str, Any]
    ) -> List[str]:
        """
        Determine which required fields don't have answers.
        
        Args:
            required_fields: List of required field names
            available_answers: Dict of field -> answer from matched surveys
            
        Returns:
            List of field names that need user input
        """
        missing = []
        for field in required_fields:
            if field not in available_answers or available_answers[field] is None:
                missing.append(field)
        return missing

    def build_survey_prompt(
        self,
        missing_fields: List[str],
        field_labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate a prompt asking the user for missing survey information.
        
        Args:
            missing_fields: List of field names that need values
            field_labels: Optional mapping of field_name -> human-readable label
            
        Returns:
            Prompt string for the user
        """
        field_labels = field_labels or {}
        
        prompt = "Please provide the following information to complete the form:\n\n"
        
        for field in missing_fields:
            label = field_labels.get(field, field.replace("_", " ").title())
            prompt += f"- {label}: \n"
        
        return prompt

    # Common field synonyms for matching similar questions across surveys
    # These are exact matches or field names that contain these terms
    FIELD_SYNONYMS = {
        "name": ["name", "full_name", "fullname", "your_name", "customer_name"],
        "first_name": ["first_name", "firstname", "given_name", "forename"],
        "last_name": ["last_name", "lastname", "surname", "family_name"],
        "email": ["email", "email_address", "e_mail", "emailaddress"],
        "phone": ["phone", "phone_number", "telephone", "mobile", "cell", "tel"],
        "company": ["company", "company_name", "companyname", "employer", "workplace"],
        "organization": ["organization", "organisation", "org"],
        "job_title": ["job_title", "jobtitle", "role", "position", "job_position", "title"],
        "industry": ["industry", "sector", "business_type"],
        "feedback": ["feedback", "comments", "additional_comments", "notes"],
        "country": ["country", "nation", "location_country"],
        "city": ["city", "town", "location_city"],
        "address": ["address", "street_address", "street"],
        "zip": ["zip", "zipcode", "zip_code", "postal_code", "postcode"],
    }

    def normalize_field_name(self, field: str) -> str:
        """
        Normalize a field name to a canonical form for matching.
        
        Args:
            field: Raw field name from form
            
        Returns:
            Normalized canonical field name
        """
        field_lower = field.lower().strip().replace("-", "_").replace(" ", "_")
        
        # First check for exact matches (highest priority)
        for canonical, synonyms in self.FIELD_SYNONYMS.items():
            if field_lower in synonyms:
                return canonical
        
        # Check for concatenated forms (e.g., "firstname" -> "first_name")
        for canonical, synonyms in self.FIELD_SYNONYMS.items():
            for syn in synonyms:
                # Handle underscore-less versions (firstname vs first_name)
                syn_no_underscore = syn.replace("_", "")
                if field_lower == syn_no_underscore:
                    return canonical
        
        # Then check if field contains a synonym (but must be a significant match)
        for canonical, synonyms in self.FIELD_SYNONYMS.items():
            for syn in synonyms:
                # Only match if synonym is at least 4 chars and is a word boundary match
                if len(syn) >= 4 and (
                    field_lower == syn or
                    field_lower.startswith(syn + "_") or
                    field_lower.endswith("_" + syn) or
                    f"_{syn}_" in field_lower
                ):
                    return canonical
        
        return field_lower

    def build_survey_autofill(
        self,
        form_fields: List[Dict[str, Any]],
        query: str = "survey form personal info",
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Build autofill data for a survey form from stored responses.
        
        Args:
            form_fields: List of {field_name, label, required} dicts describing the form
            query: Search query for finding relevant stored data
            top_k: Number of stored responses to search
            
        Returns:
            Dict with:
                - autofill: {field_name: value} for fields we can fill
                - missing: [field_names] that need user input
                - confidence: Overall confidence score
        """
        # Normalize field names for matching
        normalized_fields = {}
        required_fields = []
        field_labels = {}
        
        for f in form_fields:
            field_name = f.get("field_name", "")
            label = f.get("label", field_name)
            required = f.get("required", False)
            
            if field_name:
                normalized = self.normalize_field_name(field_name)
                normalized_fields[field_name] = normalized
                field_labels[field_name] = label
                if required:
                    required_fields.append(field_name)
        
        # Search for stored data (SurveyResponse, Identity, FormData)
        results = self.memory.search(query, top_k=top_k)
        
        # Collect values from all matching nodes
        values_by_field: Dict[str, Any] = {}
        values_by_normalized: Dict[str, Any] = {}
        
        for node in results:
            props = node.get("props", {}) if isinstance(node, dict) else getattr(node, "props", {})
            kind = node.get("kind") if isinstance(node, dict) else getattr(node, "kind", None)
            
            if kind not in self.SUPPORTED_KINDS:
                continue
            
            for key, value in props.items():
                if value is not None and key not in ("questions", "form_url", "completed_at", "stored_at"):
                    normalized_key = self.normalize_field_name(key)
                    if normalized_key not in values_by_normalized:
                        values_by_normalized[normalized_key] = value
                    if key not in values_by_field:
                        values_by_field[key] = value
        
        # Build autofill map
        autofill = {}
        for field_name, normalized in normalized_fields.items():
            # Try exact match first
            if field_name in values_by_field:
                autofill[field_name] = values_by_field[field_name]
            # Then try normalized match
            elif normalized in values_by_normalized:
                autofill[field_name] = values_by_normalized[normalized]
        
        # Find missing required fields
        missing = self.get_missing_survey_fields(required_fields, autofill)
        
        # Calculate confidence
        if len(form_fields) > 0:
            filled_ratio = len(autofill) / len(form_fields)
        else:
            filled_ratio = 0.0
        
        return {
            "autofill": autofill,
            "missing": missing,
            "missing_labels": {f: field_labels.get(f, f) for f in missing},
            "confidence": filled_ratio,
            "total_fields": len(form_fields),
            "filled_fields": len(autofill),
        }

    # Payment/Billing Result Detection Methods
    
    PAYMENT_SUCCESS_INDICATORS = [
        "payment successful", "payment complete", "order confirmed",
        "thank you for your order", "transaction complete", "purchase complete",
        "payment accepted", "order placed", "confirmation", "receipt",
        "success", "✓", "✔", "approved"
    ]
    
    PAYMENT_FAILURE_INDICATORS = [
        "payment failed", "card declined", "transaction failed",
        "insufficient funds", "invalid card", "expired card",
        "payment error", "try again", "unable to process",
        "declined", "rejected", "error", "✗", "✘", "failed"
    ]
    
    def detect_payment_result(self, page_text: str, page_html: str = "") -> Dict[str, Any]:
        """
        Analyze page content to detect if a payment submission succeeded or failed.
        
        Args:
            page_text: Visible text content from the page
            page_html: Full HTML (optional, for class/id detection)
            
        Returns:
            Dict with:
                - status: "success" | "failed" | "unknown"
                - confidence: 0.0-1.0
                - message: Detected message text
                - reason: Why it failed (if applicable)
        """
        text_lower = page_text.lower()
        html_lower = page_html.lower() if page_html else ""
        
        # Check for success indicators
        success_score = 0
        success_matches = []
        for indicator in self.PAYMENT_SUCCESS_INDICATORS:
            if indicator in text_lower:
                success_score += 1
                success_matches.append(indicator)
        
        # Check for failure indicators
        failure_score = 0
        failure_matches = []
        failure_reason = None
        for indicator in self.PAYMENT_FAILURE_INDICATORS:
            if indicator in text_lower:
                failure_score += 1
                failure_matches.append(indicator)
                if not failure_reason:
                    failure_reason = indicator
        
        # Check HTML classes for additional signals
        if html_lower:
            if any(cls in html_lower for cls in ['class="success"', 'payment-success', 'order-success']):
                success_score += 2
            if any(cls in html_lower for cls in ['class="error"', 'payment-failed', 'payment-error']):
                failure_score += 2
        
        # Determine result
        if success_score > failure_score and success_score >= 1:
            return {
                "status": "success",
                "confidence": min(1.0, success_score * 0.3),
                "message": f"Payment appears successful. Indicators: {', '.join(success_matches[:3])}",
                "reason": None
            }
        elif failure_score > success_score and failure_score >= 1:
            return {
                "status": "failed",
                "confidence": min(1.0, failure_score * 0.3),
                "message": f"Payment appears to have failed. Indicators: {', '.join(failure_matches[:3])}",
                "reason": failure_reason
            }
        else:
            return {
                "status": "unknown",
                "confidence": 0.3,
                "message": "Could not determine payment result from page content",
                "reason": None
            }
    
    def store_payment_method(
        self,
        card_last_four: str,
        props: Dict[str, Any],
        is_valid: bool = True,
        failure_reason: Optional[str] = None
    ) -> Optional[str]:
        """
        Store a payment method with its validity status.
        
        Args:
            card_last_four: Last 4 digits of card
            props: Payment method properties
            is_valid: Whether the card was accepted
            failure_reason: Why it was rejected (if applicable)
            
        Returns:
            UUID of the created PaymentMethod node
        """
        from uuid import uuid4
        from datetime import datetime, timezone
        from src.personal_assistant.models import Node, Provenance
        
        node_uuid = str(uuid4())
        pm_props = {
            "card_last_four": card_last_four,
            "is_valid": is_valid,
            "failure_reason": failure_reason,
            "tested_at": datetime.now(timezone.utc).isoformat(),
            **props
        }
        
        try:
            node = Node(
                uuid=node_uuid,
                kind="PaymentMethod",
                props=pm_props,
                labels=["PaymentMethod", "valid" if is_valid else "invalid"],
                llm_embedding=[]
            )
            provenance = Provenance(
                source="payment_test",
                ts=datetime.now(timezone.utc).isoformat(),
                confidence=0.9 if is_valid else 0.5,
                trace_id=f"payment-{node_uuid[:8]}"
            )
            self.memory.upsert(node, provenance)
            return node_uuid
        except Exception:
            return None
    
    def get_valid_payment_methods(self, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve payment methods that have been verified as valid.
        
        Returns:
            List of valid PaymentMethod concepts
        """
        results = self.memory.search("payment method card", top_k=top_k * 2)
        valid_methods = []
        
        for r in results:
            props = r.get("props", {}) if isinstance(r, dict) else getattr(r, "props", {})
            kind = r.get("kind") if isinstance(r, dict) else getattr(r, "kind", None)
            
            if kind == "PaymentMethod" and props.get("is_valid", False):
                valid_methods.append(r if isinstance(r, dict) else r.__dict__)
        
        return valid_methods[:top_k]
    
    def build_payment_prompt(self, failure_reason: Optional[str] = None) -> str:
        """
        Generate a prompt asking the user for payment information.
        
        Args:
            failure_reason: Why the previous attempt failed (if applicable)
            
        Returns:
            Prompt string for the user
        """
        base_prompt = "Please provide your payment information:"
        
        if failure_reason:
            if "declined" in failure_reason.lower():
                base_prompt = f"Your card was declined. Please provide a different card:\n"
            elif "insufficient" in failure_reason.lower():
                base_prompt = f"Insufficient funds on the card. Please provide a different card:\n"
            elif "expired" in failure_reason.lower():
                base_prompt = f"Your card has expired. Please provide a valid card:\n"
            elif "invalid" in failure_reason.lower():
                base_prompt = f"Invalid card number. Please check and re-enter:\n"
            else:
                base_prompt = f"Payment failed ({failure_reason}). Please try again:\n"
        
        return base_prompt + """
- Card Number: 
- Expiry (MM/YY): 
- CVV: 
- Name on Card: 
- Billing Address: 
- City: 
- State: 
- ZIP Code: 
- Country: """
