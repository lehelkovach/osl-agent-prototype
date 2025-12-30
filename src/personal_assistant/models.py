import uuid
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Literal

@dataclass
class Provenance:
    """Represents the origin of a piece of information."""
    source: Literal["user", "tool", "doc"]
    ts: str
    confidence: float
    trace_id: str

@dataclass
class Node:
    """Represents a node in the knowledge graph (e.g., a person, task, or concept)."""
    kind: str
    labels: List[str]
    props: Dict[str, Any]
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    llm_embedding: Optional[List[float]] = None
    status: Optional[str] = None

@dataclass
class Edge:
    """Represents a relationship between two nodes in the knowledge graph."""
    from_node: str  # UUID of the source node
    to_node: str    # UUID of the destination node
    rel: str        # The relationship type (e.g., "created", "assigned_to")
    props: Dict[str, Any]
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "edge"
