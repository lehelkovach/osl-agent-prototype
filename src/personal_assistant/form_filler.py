from typing import List, Dict, Any, Optional, Callable

from src.personal_assistant.tools import MemoryTools

EmbedFn = Callable[[str], List[float]]


class FormDataRetriever:
    """
    Helper to pull remembered FormData/Identity/Credential/PaymentMethod concepts
    from memory and build an autofill map for form fields.
    Also supports survey answer reuse by matching similar questions.
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

    def build_autofill(self, required_fields: List[str], query: str = "form data") -> Dict[str, Any]:
        """
        Build a field->value map for the requested fields using the most recent
        supported nodes from memory.
        """
        field_map: Dict[str, Any] = {}
        nodes = self.fetch_latest(query=query, top_k=20)
        for node in nodes:
            props = node.get("props", {})
            for f in required_fields:
                if f in props and props[f] is not None:
                    field_map[f] = props[f]
        return field_map

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
