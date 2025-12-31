from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


DEFAULT_PROPERTY_DEFS = [
    {"prop": "name", "dtype": "text"},
    {"prop": "description", "dtype": "text"},
    {"prop": "tags", "dtype": "list[text]"},
    {"prop": "createdAt", "dtype": "date"},
    {"prop": "updatedAt", "dtype": "date"},
    {"prop": "startAt", "dtype": "date"},
    {"prop": "endAt", "dtype": "date"},
    {"prop": "dueAt", "dtype": "date"},
    {"prop": "status", "dtype": "text"},
    {"prop": "priority", "dtype": "int"},
    {"prop": "owner", "dtype": "ref(Agent)"},
    {"prop": "participants", "dtype": "list[ref(Agent)]"},
    {"prop": "location", "dtype": "ref(Place)"},
    {"prop": "url", "dtype": "url"},
    {"prop": "sender", "dtype": "ref(Agent)"},
    {"prop": "recipient", "dtype": "list[ref(Agent)]"},
]

DEFAULT_PROTOTYPES = [
    "Agent",
    "ContactMethod",
    "Place",
    "TimeInterval",
    "Event",
    "Task",
    "Message",
    "Document",
    "Device",
    "PreferenceRule",
    "List",
    "Chain",
    "DAG",
]

# Prototype inheritance mapping child -> parent
PROTOTYPE_INHERITS = {
    "Chain": "List",
    "DAG": "Chain",
}

DEFAULT_OBJECTS = [
    {"name": "self", "kind": "Agent", "labels": ["seed", "agent"]},
    {"name": "assistant", "kind": "Agent", "labels": ["seed", "agent"]},
    {"name": "home", "kind": "Place", "labels": ["seed", "place"]},
    {"name": "work", "kind": "Place", "labels": ["seed", "place"]},
]


class KSGStore:
    """
    Minimal KnowShowGo store over MemoryTools (concepts + assoc edges).
    """

    def __init__(self, memory: MemoryTools):
        self.memory = memory

    def _prov(self, trace_id: str = "ksg-init") -> Provenance:
        return Provenance(
            source="user", ts=datetime.now(timezone.utc).isoformat(), confidence=1.0, trace_id=trace_id
        )

    def create_concept(self, kind: str, name: Optional[str], labels: List[str], props: Dict[str, Any]) -> Node:
        node = Node(kind=kind, labels=labels, props={**props, "name": name} if name else props)
        self.memory.upsert(node, self._prov())
        return node

    def add_assoc(
        self,
        from_uuid: str,
        to_uuid: str,
        rel: str,
        props: Optional[Dict[str, Any]] = None,
        trace_id: str = "ksg-assoc",
    ) -> Edge:
        edge = Edge(from_node=from_uuid, to_node=to_uuid, rel=rel, props=props or {})
        self.memory.upsert(edge, self._prov(trace_id))
        return edge

    def ensure_seeds(self, embedding_fn=None) -> Dict[str, List[str]]:
        ensured = {"property_defs": [], "prototypes": [], "objects": []}
        prov = self._prov("ksg-seed")
        # Seed property defs
        for pd in DEFAULT_PROPERTY_DEFS:
            node = Node(
                kind="PropertyDef",
                labels=["PropertyDef"],
                props={"propertyName": pd["prop"], "dtype": pd["dtype"]},
            )
            if embedding_fn:
                try:
                    node.llm_embedding = embedding_fn(f"{pd['prop']} {pd['dtype']}")
                except Exception:
                    node.llm_embedding = None
            self.memory.upsert(node, prov, embedding_request=True)
            ensured["property_defs"].append(node.uuid)

        # Seed prototypes
        proto_nodes: Dict[str, Node] = {}
        for proto in DEFAULT_PROTOTYPES:
            node = Node(
                kind="Prototype",
                labels=["Prototype", proto],
                props={"protoId": proto, "version": "1.0.0", "immutable": True},
            )
            if embedding_fn:
                try:
                    node.llm_embedding = embedding_fn(proto)
                except Exception:
                    node.llm_embedding = None
            self.memory.upsert(node, prov, embedding_request=True)
            ensured["prototypes"].append(node.uuid)
            proto_nodes[proto] = node

        # Link prototype inheritance edges
        for child, parent in PROTOTYPE_INHERITS.items():
            if child in proto_nodes and parent in proto_nodes:
                self.add_assoc(
                    from_uuid=proto_nodes[child].uuid,
                    to_uuid=proto_nodes[parent].uuid,
                    rel="inherits_from",
                    props={"child": child, "parent": parent},
                    trace_id="ksg-proto-inherit",
                )

        # Seed objects
        for obj in DEFAULT_OBJECTS:
            node = Node(kind="Object", labels=obj["labels"], props={"name": obj["name"], "kind": obj["kind"]})
            if embedding_fn:
                try:
                    node.llm_embedding = embedding_fn(obj["name"])
                except Exception:
                    node.llm_embedding = None
            self.memory.upsert(node, prov, embedding_request=True)
            ensured["objects"].append(node.uuid)

        return ensured
