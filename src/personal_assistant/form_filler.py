from typing import List, Dict, Any, Optional

from src.personal_assistant.tools import MemoryTools


class FormDataRetriever:
    """
    Helper to pull remembered FormData/Identity/Credential/PaymentMethod concepts
    from memory and build an autofill map for form fields.
    """

    SUPPORTED_KINDS = {"FormData", "Identity", "Credential", "PaymentMethod"}

    def __init__(self, memory: MemoryTools):
        self.memory = memory

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
