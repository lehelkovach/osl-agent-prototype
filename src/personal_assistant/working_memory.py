"""
Working Memory Graph: Short-term activation layer with reinforcement.

Ported from deprecated knowshowgo repository.
Implements Hebbian learning: frequently accessed associations become stronger.

Design principle (per GPT-5.2): This is SEPARATE from semantic memory.
- Semantic store (Arango/Chroma) = durable, global knowledge
- Working memory = session-scoped activation for retrieval boosting
"""

import networkx as nx
from typing import Optional


class WorkingMemoryGraph:
    """NetworkX-backed working memory for selection/retrieval boosting.

    Implements reinforcement-on-access: edges strengthen when used.
    
    Usage:
        wm = WorkingMemoryGraph(reinforce_delta=1.0, max_weight=100.0)
        
        # Create/reinforce edge when concept is selected
        weight = wm.link("procedure_uuid", "step_uuid", seed_weight=0.5)
        
        # Access reinforces existing edges (read = strengthen)
        weight = wm.access("procedure_uuid", "step_uuid")
        
        # Query without side effects
        weight = wm.get_weight("procedure_uuid", "step_uuid")
    """

    def __init__(self, reinforce_delta: float = 1.0, max_weight: float = 100.0) -> None:
        self._g = nx.DiGraph()
        self.reinforce_delta = reinforce_delta
        self.max_weight = max_weight

    def _ensure_nodes(self, u: str, v: str) -> None:
        if not self._g.has_node(u):
            self._g.add_node(u)
        if not self._g.has_node(v):
            self._g.add_node(v)

    def link(self, source: str, target: str, seed_weight: float = 0.0) -> float:
        """Create or reinforce an edge; returns updated weight."""
        self._ensure_nodes(source, target)
        if self._g.has_edge(source, target):
            self._g[source][target]["weight"] = min(
                self.max_weight, self._g[source][target]["weight"] + self.reinforce_delta
            )
        else:
            self._g.add_edge(source, target, weight=min(self.max_weight, seed_weight))
        return self._g[source][target]["weight"]

    def access(self, source: str, target: str) -> Optional[float]:
        """Access reinforces the edge if present. Returns None if edge doesn't exist."""
        if not self._g.has_edge(source, target):
            return None
        self._g[source][target]["weight"] = min(
            self.max_weight, self._g[source][target]["weight"] + self.reinforce_delta
        )
        return self._g[source][target]["weight"]

    def get_weight(self, source: str, target: str) -> Optional[float]:
        """Query edge weight without reinforcement (no side effects)."""
        edge = self._g.get_edge_data(source, target)
        return None if edge is None else edge.get("weight")

    def get_activation_boost(self, node_uuid: str, default: float = 0.0) -> float:
        """Get total incoming activation for a node (for retrieval boosting)."""
        if not self._g.has_node(node_uuid):
            return default
        total = sum(
            self._g[pred][node_uuid].get("weight", 0.0)
            for pred in self._g.predecessors(node_uuid)
        )
        return total if total > 0 else default

    def decay_all(self, decay_factor: float = 0.9) -> None:
        """Apply decay to all edges (call periodically for forgetting)."""
        for u, v, data in self._g.edges(data=True):
            data["weight"] = data.get("weight", 0.0) * decay_factor

    def clear(self) -> None:
        """Clear all activation (start fresh session)."""
        self._g.clear()
    
    def get_top_activated(self, top_k: int = 10) -> list:
        """Get nodes with highest total incoming activation."""
        activations = []
        for node in self._g.nodes():
            boost = self.get_activation_boost(node, default=0.0)
            if boost > 0:
                activations.append((node, boost))
        activations.sort(key=lambda x: x[1], reverse=True)
        return activations[:top_k]
