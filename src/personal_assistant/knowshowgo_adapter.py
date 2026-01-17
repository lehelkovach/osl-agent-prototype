"""
KnowShowGo Adapter - Choose between embedded API or remote service.

This adapter provides a unified interface for the agent to interact with
KnowShowGo, whether it's running as an embedded library or a remote service.
"""
import os
import logging
from typing import Any, Callable, Dict, List, Optional

# Try to import the service client
try:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    from services.knowshowgo.client import KnowShowGoClient, MockKnowShowGoClient
    SERVICE_CLIENT_AVAILABLE = True
except ImportError:
    SERVICE_CLIENT_AVAILABLE = False

from .knowshowgo import KnowShowGoAPI
from .chroma_memory import MemoryTools
from .models import Node, Edge, Provenance

logger = logging.getLogger(__name__)


EmbedFn = Callable[[str], List[float]]


class KnowShowGoAdapter:
    """
    Adapter that provides unified interface for KnowShowGo operations.
    
    Can use either:
    1. Remote service (if KNOWSHOWGO_URL is set and service is available)
    2. Embedded KnowShowGoAPI (fallback)
    
    Usage:
        adapter = KnowShowGoAdapter.create(memory, embed_fn)
        
        # All methods work regardless of backend
        uuid = adapter.create_concept(...)
        results = adapter.search(...)
    """
    
    def __init__(
        self,
        backend: str,
        embedded_api: Optional[KnowShowGoAPI] = None,
        service_client: Optional[Any] = None,
        embed_fn: Optional[EmbedFn] = None,
    ):
        self.backend = backend  # "embedded" or "service"
        self.embedded_api = embedded_api
        self.service_client = service_client
        self.embed_fn = embed_fn
    
    @classmethod
    def create(
        cls,
        memory: Optional[MemoryTools] = None,
        embed_fn: Optional[EmbedFn] = None,
        force_embedded: bool = False,
        force_service: bool = False,
    ) -> "KnowShowGoAdapter":
        """
        Create adapter with best available backend.
        
        Args:
            memory: MemoryTools for embedded API
            embed_fn: Embedding function
            force_embedded: Force use of embedded API
            force_service: Force use of service (will fail if unavailable)
            
        Returns:
            KnowShowGoAdapter configured with appropriate backend
        """
        service_url = os.getenv("KNOWSHOWGO_URL", "")
        use_service = os.getenv("USE_KNOWSHOWGO_SERVICE", "").lower() in ("1", "true")
        
        # Try service first if configured
        if (use_service or force_service or service_url) and not force_embedded:
            if SERVICE_CLIENT_AVAILABLE:
                client = KnowShowGoClient(
                    base_url=service_url or "http://localhost:8001",
                    embed_fn=embed_fn
                )
                
                if client.is_available():
                    logger.info(f"Using KnowShowGo service at {client.base_url}")
                    return cls(
                        backend="service",
                        service_client=client,
                        embed_fn=embed_fn
                    )
                elif force_service:
                    raise RuntimeError(f"KnowShowGo service at {client.base_url} is not available")
                else:
                    logger.warning(f"KnowShowGo service at {client.base_url} not available, falling back to embedded")
        
        # Use embedded API
        if memory is None:
            from .networkx_memory import NetworkXMemoryTools
            memory = NetworkXMemoryTools()
        
        logger.info("Using embedded KnowShowGoAPI")
        embedded = KnowShowGoAPI(memory=memory, embed_fn=embed_fn)
        
        return cls(
            backend="embedded",
            embedded_api=embedded,
            embed_fn=embed_fn
        )
    
    @classmethod
    def create_mock(cls, embed_fn: Optional[EmbedFn] = None) -> "KnowShowGoAdapter":
        """Create adapter with mock service client for testing."""
        if not SERVICE_CLIENT_AVAILABLE:
            raise ImportError("Service client not available for mock")
        
        mock_client = MockKnowShowGoClient(embed_fn=embed_fn)
        return cls(
            backend="mock",
            service_client=mock_client,
            embed_fn=embed_fn
        )
    
    def is_service_mode(self) -> bool:
        """Check if using remote service."""
        return self.backend in ("service", "mock")
    
    def create_concept(
        self,
        prototype_uuid: str,
        json_obj: Dict[str, Any],
        provenance: Optional[Provenance] = None,
        previous_version_uuid: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """Create a concept from a prototype."""
        if self.is_service_mode():
            return self.service_client.create_concept(
                prototype_uuid=prototype_uuid,
                json_obj=json_obj,
                embedding=embedding,
                provenance=provenance,
                previous_version_uuid=previous_version_uuid
            )
        else:
            node = self.embedded_api.create_concept(
                prototype_uuid=prototype_uuid,
                json_obj=json_obj,
                provenance=provenance,
                previous_version_uuid=previous_version_uuid
            )
            return node.uuid
    
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        min_similarity: float = 0.0
    ) -> List[Dict[str, Any]]:
        """Search for concepts."""
        if self.is_service_mode():
            return self.service_client.search(
                query=query,
                top_k=top_k,
                filters=filters,
                min_similarity=min_similarity
            )
        else:
            nodes = self.embedded_api.search_concepts(
                query=query,
                top_k=top_k
            )
            # Convert to dict format
            return [
                {
                    "uuid": node.uuid,
                    "kind": node.kind,
                    "props": node.props,
                    "labels": getattr(node, "labels", []),
                    "score": getattr(node, "_score", 0.5)
                }
                for node in nodes
            ]
    
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
        """Upsert a node or edge."""
        if self.is_service_mode():
            return self.service_client.upsert(
                kind=kind,
                props=props,
                uuid=uuid,
                labels=labels,
                embedding=embedding,
                from_node=from_node,
                to_node=to_node,
                rel=rel
            )
        else:
            if from_node and to_node and rel:
                # Create edge
                edge = Edge(
                    uuid=uuid or "",
                    from_node=from_node,
                    to_node=to_node,
                    rel=rel,
                    props=props
                )
                self.embedded_api.memory.upsert_edge(edge)
                return edge.uuid
            else:
                # Create node
                node = Node(
                    uuid=uuid or "",
                    kind=kind,
                    props=props,
                    labels=labels or [],
                    embedding=embedding or []
                )
                self.embedded_api.memory.upsert_node(node)
                return node.uuid
    
    def store_cpms_pattern(
        self,
        pattern_name: str,
        pattern_data: Dict[str, Any],
        embedding: Optional[List[float]] = None,
        concept_uuid: Optional[str] = None,
    ) -> str:
        """Store a form pattern."""
        if self.is_service_mode():
            return self.service_client.store_cpms_pattern(
                pattern_name=pattern_name,
                pattern_data=pattern_data,
                embedding=embedding,
                concept_uuid=concept_uuid
            )
        else:
            return self.embedded_api.store_cpms_pattern(
                pattern_name=pattern_name,
                pattern_data=pattern_data,
                concept_uuid=concept_uuid
            )
    
    def find_best_cpms_pattern(
        self,
        url: str,
        html: Optional[str] = None,
        form_type: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Find matching patterns."""
        if self.is_service_mode():
            return self.service_client.find_best_cpms_pattern(
                url=url,
                html=html,
                form_type=form_type,
                top_k=top_k
            )
        else:
            matches = self.embedded_api.find_best_cpms_pattern(url=url)
            if matches:
                return [{"concept": matches[0], "pattern_data": matches[1], "score": 0.8}]
            return []
    
    def get_concept(self, concept_uuid: str) -> Dict[str, Any]:
        """Get a concept by UUID."""
        if self.is_service_mode():
            return self.service_client.get_concept(concept_uuid)
        else:
            node = self.embedded_api.memory.get_node(concept_uuid)
            if node:
                return {
                    "uuid": node.uuid,
                    "kind": node.kind,
                    "props": node.props,
                    "labels": getattr(node, "labels", [])
                }
            raise ValueError(f"Concept {concept_uuid} not found")
    
    @property
    def memory(self):
        """Access underlying memory (for backward compatibility)."""
        if self.embedded_api:
            return self.embedded_api.memory
        return None
    
    @property
    def orm(self):
        """Access ORM (for backward compatibility)."""
        if self.embedded_api:
            return self.embedded_api.orm
        return None
