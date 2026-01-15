"""
KnowShowGo Client - HTTP client for the KnowShowGo Service.

This client provides the same interface as the embedded KnowShowGoAPI
but communicates with the remote service over HTTP.
"""
import os
import requests
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime, timezone


EmbedFn = Callable[[str], List[float]]


class KnowShowGoServiceError(Exception):
    """Error communicating with KnowShowGo service."""
    pass


class KnowShowGoClient:
    """
    HTTP client for KnowShowGo Service.
    
    Provides the same interface as KnowShowGoAPI but communicates
    with a remote service.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        embed_fn: Optional[EmbedFn] = None,
        timeout: int = 30
    ):
        """
        Initialize the client.
        
        Args:
            base_url: URL of the KnowShowGo service (default: from env or localhost:8001)
            embed_fn: Function to generate embeddings
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or os.getenv("KNOWSHOWGO_URL", "http://localhost:8001")
        self.base_url = self.base_url.rstrip("/")
        self.embed_fn = embed_fn
        self.timeout = timeout
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        """Make an HTTP request to the service."""
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", self.timeout)
        
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.ConnectionError as e:
            raise KnowShowGoServiceError(f"Cannot connect to KnowShowGo service at {self.base_url}: {e}")
        except requests.exceptions.Timeout as e:
            raise KnowShowGoServiceError(f"Request to KnowShowGo service timed out: {e}")
        except requests.exceptions.HTTPError as e:
            raise KnowShowGoServiceError(f"HTTP error from KnowShowGo service: {e}")
        except Exception as e:
            raise KnowShowGoServiceError(f"Error communicating with KnowShowGo service: {e}")
    
    def health(self) -> Dict[str, Any]:
        """Check service health."""
        return self._request("GET", "/health")
    
    def is_available(self) -> bool:
        """Check if the service is available."""
        try:
            health = self.health()
            return health.get("status") == "ok"
        except Exception:
            return False
    
    def create_concept(
        self,
        prototype_uuid: str,
        json_obj: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        provenance: Optional[Any] = None,
        previous_version_uuid: Optional[str] = None,
    ) -> str:
        """
        Create a concept from a prototype.
        
        Returns:
            UUID of the created concept
        """
        # Generate embedding if not provided
        if embedding is None and self.embed_fn:
            try:
                text = json_obj.get("name", "") or json_obj.get("title", "") or str(json_obj)
                embedding = self.embed_fn(text[:500])
            except Exception:
                embedding = []
        
        result = self._request("POST", "/concepts", json={
            "prototype_uuid": prototype_uuid,
            "json_obj": json_obj,
            "embedding": embedding or [],
            "previous_version_uuid": previous_version_uuid,
        })
        
        return result["uuid"]
    
    def get_concept(self, concept_uuid: str) -> Dict[str, Any]:
        """Get a concept by UUID."""
        return self._request("GET", f"/concepts/{concept_uuid}")
    
    def search(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """
        Search for concepts.
        
        Returns:
            List of matching concepts with scores
        """
        # Generate embedding if not provided
        if embedding is None and self.embed_fn:
            try:
                embedding = self.embed_fn(query)
            except Exception:
                embedding = None
        
        result = self._request("POST", "/search", json={
            "query": query,
            "embedding": embedding,
            "top_k": top_k,
            "filters": filters,
            "min_similarity": min_similarity,
        })
        
        return result.get("results", [])
    
    def upsert(
        self,
        kind: str,
        props: Dict[str, Any],
        uuid: Optional[str] = None,
        labels: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
        # Edge fields
        from_node: Optional[str] = None,
        to_node: Optional[str] = None,
        rel: Optional[str] = None,
    ) -> str:
        """
        Upsert a node or edge.
        
        Returns:
            UUID of the upserted item
        """
        result = self._request("POST", "/upsert", json={
            "kind": kind,
            "uuid": uuid,
            "labels": labels or [],
            "props": props,
            "embedding": embedding,
            "from_node": from_node,
            "to_node": to_node,
            "rel": rel,
        })
        
        return result["uuid"]
    
    def store_cpms_pattern(
        self,
        pattern_name: str,
        pattern_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        concept_uuid: Optional[str] = None,
    ) -> str:
        """
        Store a form pattern for reuse.
        
        Returns:
            UUID of the stored pattern
        """
        # Generate embedding if not provided
        if embedding is None and self.embed_fn:
            try:
                embedding = self.embed_fn(pattern_name)
            except Exception:
                embedding = []
        
        result = self._request("POST", "/patterns/store", json={
            "pattern_name": pattern_name,
            "pattern_data": pattern_data,
            "embedding": embedding or [],
            "concept_uuid": concept_uuid,
        })
        
        return result["uuid"]
    
    def find_best_cpms_pattern(
        self,
        url: str,
        html: Optional[str] = None,
        form_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find matching patterns for a URL/form.
        
        Returns:
            List of matching patterns with scores
        """
        result = self._request("POST", "/patterns/match", json={
            "url": url,
            "html": html,
            "form_type": form_type,
            "top_k": top_k,
        })
        
        return result
    
    def list_prototypes(self) -> List[Dict[str, Any]]:
        """List all prototypes."""
        result = self._request("GET", "/prototypes")
        return result.get("prototypes", [])


class MockKnowShowGoClient:
    """
    Mock client for testing without a running service.
    
    Stores data in memory, behaves like the real client.
    """
    
    def __init__(self, embed_fn: Optional[EmbedFn] = None):
        self.embed_fn = embed_fn
        self.nodes: Dict[str, Dict[str, Any]] = {}
        self.edges: Dict[str, Dict[str, Any]] = {}
        self._init_prototypes()
    
    def _init_prototypes(self):
        """Initialize standard prototypes."""
        prototypes = [
            ("proto-concept", "Concept"),
            ("proto-procedure", "Procedure"),
            ("proto-credential", "Credential"),
            ("proto-form-pattern", "FormPattern"),
            ("proto-queue-item", "QueueItem"),
        ]
        for uuid, name in prototypes:
            self.nodes[uuid] = {
                "uuid": uuid,
                "kind": "Prototype",
                "props": {"name": name, "isPrototype": True},
                "labels": [name],
                "embedding": [],
            }
    
    def health(self) -> Dict[str, Any]:
        return {
            "status": "ok",
            "version": "mock",
            "concepts_count": len(self.nodes),
            "edges_count": len(self.edges)
        }
    
    def is_available(self) -> bool:
        return True
    
    def create_concept(
        self,
        prototype_uuid: str,
        json_obj: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        provenance: Optional[Any] = None,
        previous_version_uuid: Optional[str] = None,
    ) -> str:
        import uuid as uuid_mod
        concept_uuid = str(uuid_mod.uuid4())
        
        self.nodes[concept_uuid] = {
            "uuid": concept_uuid,
            "kind": "Concept",
            "props": {
                **json_obj,
                "prototype_uuid": prototype_uuid,
                "isPrototype": False,
            },
            "labels": [json_obj.get("name", "concept")],
            "embedding": embedding or [],
        }
        
        return concept_uuid
    
    def get_concept(self, concept_uuid: str) -> Dict[str, Any]:
        if concept_uuid not in self.nodes:
            raise KnowShowGoServiceError(f"Concept {concept_uuid} not found")
        return self.nodes[concept_uuid]
    
    def search(
        self,
        query: str,
        embedding: Optional[List[float]] = None,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        results = []
        query_lower = query.lower()
        
        for node in self.nodes.values():
            if node.get("props", {}).get("isPrototype"):
                continue
            
            # Apply filters
            if filters:
                if filters.get("kind") and node.get("kind") != filters["kind"]:
                    continue
            
            # Simple text matching
            node_text = " ".join([
                str(node.get("kind", "")),
                " ".join(node.get("labels", [])),
                str(node.get("props", {})),
            ]).lower()
            
            score = 0.5 if query_lower in node_text else 0.3
            results.append({**node, "score": score})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def upsert(
        self,
        kind: str,
        props: Dict[str, Any],
        uuid: Optional[str] = None,
        labels: Optional[List[str]] = None,
        embedding: Optional[List[float]] = None,
        from_node: Optional[str] = None,
        to_node: Optional[str] = None,
        rel: Optional[str] = None,
    ) -> str:
        import uuid as uuid_mod
        item_uuid = uuid or str(uuid_mod.uuid4())
        
        if from_node and to_node and rel:
            self.edges[item_uuid] = {
                "uuid": item_uuid,
                "from_node": from_node,
                "to_node": to_node,
                "rel": rel,
                "props": props,
            }
        else:
            self.nodes[item_uuid] = {
                "uuid": item_uuid,
                "kind": kind,
                "labels": labels or [],
                "props": props,
                "embedding": embedding or [],
            }
        
        return item_uuid
    
    def store_cpms_pattern(
        self,
        pattern_name: str,
        pattern_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        concept_uuid: Optional[str] = None,
    ) -> str:
        import uuid as uuid_mod
        pattern_uuid = concept_uuid or str(uuid_mod.uuid4())
        
        self.nodes[pattern_uuid] = {
            "uuid": pattern_uuid,
            "kind": "FormPattern",
            "props": {
                "name": pattern_name,
                "pattern_data": pattern_data,
                "isPrototype": False,
            },
            "labels": ["FormPattern", pattern_name],
            "embedding": embedding or [],
        }
        
        return pattern_uuid
    
    def find_best_cpms_pattern(
        self,
        url: str,
        html: Optional[str] = None,
        form_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        results = []
        
        for node in self.nodes.values():
            if node.get("kind") != "FormPattern":
                continue
            
            pattern_data = node.get("props", {}).get("pattern_data", {})
            results.append({
                "concept": {"uuid": node["uuid"], "props": node["props"]},
                "pattern_data": pattern_data,
                "score": 0.5
            })
        
        return results[:top_k]
    
    def list_prototypes(self) -> List[Dict[str, Any]]:
        return [
            node for node in self.nodes.values()
            if node.get("props", {}).get("isPrototype")
        ]


def create_client(
    use_mock: bool = False,
    base_url: Optional[str] = None,
    embed_fn: Optional[EmbedFn] = None
) -> "KnowShowGoClient | MockKnowShowGoClient":
    """
    Factory function to create a KnowShowGo client.
    
    Args:
        use_mock: If True, return a mock client for testing
        base_url: URL of the service (ignored if use_mock=True)
        embed_fn: Embedding function
        
    Returns:
        Either a real or mock client
    """
    if use_mock:
        return MockKnowShowGoClient(embed_fn=embed_fn)
    return KnowShowGoClient(base_url=base_url, embed_fn=embed_fn)
