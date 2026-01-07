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
    """
    Represents a node in the knowledge graph (Topic/Concept).
    
    Aligned with Knowshowgo v0.1 Topic schema:
    - All nodes are Topics (including Prototypes where isPrototype=true)
    - Concepts are Topics with isPrototype=false
    - Prototypes are Topics with isPrototype=true
    """
    kind: str  # "topic" or "Concept" or "Prototype" (backward compat)
    labels: List[str]  # Primary label + aliases
    props: Dict[str, Any]  # All properties including label, aliases, summary, etc.
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    llm_embedding: Optional[List[float]] = None
    status: Optional[str] = None  # "active", "proposed", "deprecated", etc.
    # Knowshowgo Topic fields (stored in props, but accessible via helpers)
    # label: str (primary label, typically first in labels)
    # aliases: List[str] (additional labels)
    # summary: str (description)
    # isPrototype: bool (True for Prototypes, False for Concepts/Topics)
    # namespace: str (default "public")
    # externalRefs: List[Dict] (references to external systems)

@dataclass
class Edge:
    """
    Represents an association edge between two nodes (Topic → Topic/Value).
    
    Aligned with Knowshowgo v0.1 Association model:
    - Properties-as-edges with PropertyDef reference (p)
    - Weight (w) for fuzzy association strength (0.0-1.0)
    - Confidence, provenance, votes, status
    """
    from_node: str  # UUID of the source Topic/Concept
    to_node: str    # UUID of the destination Topic/Concept or Value
    rel: str        # Relationship type (backward compat; prefer p for PropertyDef reference)
    props: Dict[str, Any]  # All edge attributes
    uuid: str = field(default_factory=lambda: str(uuid.uuid4()))
    kind: str = "edge"
    # Knowshowgo Association fields (stored in props, but accessible via helpers):
    # p: str (PropertyDef UUID reference - predicate)
    # w: float (weight/strength 0.0-1.0 - primary fuzzy association strength)
    # confidence: float (0.0-1.0)
    # status: str ("proposed", "accepted", "rejected", "deprecated")
    # provenance: Dict (source, user, url, etc.)
    # revisionId: str (optional Revision reference)
    # votesUp: int, votesDown: int (or voteScore)
