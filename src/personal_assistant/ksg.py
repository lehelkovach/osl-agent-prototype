from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


DEFAULT_PROPERTY_DEFS = [
    {"prop": "name", "dtype": "text"},
    {"prop": "description", "dtype": "text"},
    {"prop": "tags", "dtype": "list[ref(Tag)]"},
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
    {"prop": "username", "dtype": "text"},
    {"prop": "password", "dtype": "text"},
    {"prop": "secret", "dtype": "text"},
    {"prop": "appName", "dtype": "text"},
    {"prop": "cardNumber", "dtype": "text"},
    {"prop": "cardExpiry", "dtype": "text"},
    {"prop": "cardCvv", "dtype": "text"},
    {"prop": "billingAddress", "dtype": "text"},
    {"prop": "identityNumber", "dtype": "text"},
    {"prop": "givenName", "dtype": "text"},
    {"prop": "familyName", "dtype": "text"},
    {"prop": "address", "dtype": "text"},
    {"prop": "city", "dtype": "text"},
    {"prop": "state", "dtype": "text"},
    {"prop": "postalCode", "dtype": "text"},
    {"prop": "country", "dtype": "text"},
    {"prop": "phone", "dtype": "text"},
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
    "DAG",
    "Tag",
    "Queue",
    "Procedure",
    "Step",
    "Vault",
    "Credential",
    "PaymentMethod",
    "Identity",
    "FormData",
]

# Prototype inheritance mapping child -> parent
PROTOTYPE_INHERITS = {
    "DAG": "List",
    "Queue": "List",
    "Procedure": "DAG",
    "Credential": "Vault",
    "PaymentMethod": "Vault",
    "Identity": "Vault",
    "FormData": "Vault",
}

DEFAULT_OBJECTS = [
    {"name": "self", "kind": "Agent", "labels": ["seed", "agent"]},
    {"name": "assistant", "kind": "Agent", "labels": ["seed", "agent"]},
    {"name": "home", "kind": "Place", "labels": ["seed", "place"]},
    {"name": "work", "kind": "Place", "labels": ["seed", "place"]},
    {"name": "language:en", "kind": "Language", "labels": ["seed", "language"]},
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

    def add_tag(
        self,
        concept_uuid: str,
        tag_name: str,
        language: str = "language:en",
        weight: float = 1.0,
        embedding_fn=None,
    ) -> str:
        prov = self._prov("ksg-tag")
        tag_node = Node(
            kind="Tag",
            labels=["Tag"],
            props={"name": tag_name, "language": language},
        )
        try:
            tag_node.llm_embedding = embedding_fn(tag_name) if embedding_fn else None
        except Exception:
            tag_node.llm_embedding = None
        self.memory.upsert(tag_node, prov, embedding_request=True)
        edge = Edge(
            from_node=concept_uuid,
            to_node=tag_node.uuid,
            rel="has_tag",
            props={"w": weight},
        )
        self.memory.upsert(edge, prov, embedding_request=False)
        # Link tag -> language object if present
        lang_nodes = [n for n in getattr(self.memory, "nodes", {}).values() if n.props.get("name") == language]
        if lang_nodes:
            lang_edge = Edge(
                from_node=tag_node.uuid,
                to_node=lang_nodes[0].uuid,
                rel="is_a",
                props={"kind": "Language"},
            )
            self.memory.upsert(lang_edge, prov, embedding_request=False)
        return tag_node.uuid
