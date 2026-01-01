from typing import List, Dict, Any, Optional, Union
import math
import networkx as nx

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


class NetworkXMemoryTools(MemoryTools):
    """
    In-memory MemoryTools backed by a NetworkX MultiDiGraph.

    Stores Node/Edge objects, supports simple filter + embedding-aware search,
    and exposes node/edge maps for compatibility with other backends.
    """

    def __init__(self):
        self.graph = nx.MultiDiGraph()
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}

    def search(
        self,
        query_text: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        candidates = list(self.nodes.values())
        if filters:
            filtered = []
            for n in candidates:
                match = True
                for k, v in filters.items():
                    if getattr(n, k, None) != v:
                        match = False
                        break
                if match:
                    filtered.append(n)
            candidates = filtered

        def cosine(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        if query_embedding:
            candidates.sort(
                key=lambda n: cosine(query_embedding, n.llm_embedding or []),
                reverse=True,
            )

        return candidates[:top_k]

    def upsert(self, item: Union[Node, Edge], provenance: Provenance, embedding_request: Optional[bool] = False) -> Dict[str, Any]:
        if isinstance(item, Node):
            self.nodes[item.uuid] = item
            self.graph.add_node(item.uuid, data=item, provenance=provenance)
        elif isinstance(item, Edge):
            self.edges[item.uuid] = item
            self.graph.add_edge(item.from_node, item.to_node, key=item.uuid, data=item, provenance=provenance)
        return {"status": "success", "uuid": item.uuid}
