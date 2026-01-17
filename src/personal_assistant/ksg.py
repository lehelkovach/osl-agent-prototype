from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


# Knowshowgo v0.1 PropertyDef catalog (minimal set for agent functionality)
# Aligned with Knowshowgo_SYSTEM_DESIGN_v0.1.md
DEFAULT_PROPERTY_DEFS = [
    # Ontology core
    {"prop": "instanceOf", "dtype": "topic_ref", "description": "Topic → Prototype (type membership)"},
    {"prop": "broaderThan", "dtype": "topic_ref", "description": "Broader concept relationship"},
    {"prop": "narrowerThan", "dtype": "topic_ref", "description": "Narrower concept relationship"},
    {"prop": "relatedTo", "dtype": "topic_ref", "description": "General relatedness"},
    {"prop": "partOf", "dtype": "topic_ref", "description": "Part-whole relationship"},
    {"prop": "hasPart", "dtype": "topic_ref", "description": "Has-part relationship"},
    {"prop": "synonymOf", "dtype": "topic_ref", "description": "Soft equivalence"},
    {"prop": "sameAs", "dtype": "topic_ref", "description": "Strong equivalence/merge"},
    {"prop": "hasSource", "dtype": "topic_ref", "description": "Source reference (DigitalResource or URL)"},
    # Identity & external refs
    {"prop": "alias", "dtype": "string", "description": "Alternative name/label"},
    {"prop": "externalUrl", "dtype": "url", "description": "External URL reference"},
    {"prop": "imageUrl", "dtype": "url", "description": "Image URL"},
    {"prop": "schemaOrgType", "dtype": "url", "description": "Schema.org type reference"},
    {"prop": "wikipediaUrl", "dtype": "url", "description": "Wikipedia URL"},
    # Time + scheduling (assistant)
    {"prop": "startTime", "dtype": "date", "description": "Start time/datetime"},
    {"prop": "endTime", "dtype": "date", "description": "End time/datetime"},
    {"prop": "dueTime", "dtype": "date", "description": "Due time/datetime"},
    {"prop": "priority", "dtype": "number", "description": "Priority level"},
    {"prop": "status", "dtype": "string", "description": "Status (todo|doing|done|blocked|active|deprecated)"},
    # Procedural memory (assistant)
    {"prop": "hasStep", "dtype": "topic_ref", "description": "Procedure → Step"},
    {"prop": "nextStep", "dtype": "topic_ref", "description": "Step → Step (sequence)"},
    {"prop": "usesCommandlet", "dtype": "topic_ref", "description": "Step → Commandlet"},
    {"prop": "params", "dtype": "json", "description": "Parameters (JSON)"},
    {"prop": "trigger", "dtype": "topic_ref", "description": "Procedure → Trigger"},
    {"prop": "successCriteria", "dtype": "json", "description": "Success criteria (JSON/string)"},
    {"prop": "appliesToSite", "dtype": "topic_ref", "description": "Procedure → WebResource"},
    {"prop": "runsProcedure", "dtype": "topic_ref", "description": "QueueItem → Procedure"},
    {"prop": "context", "dtype": "json", "description": "Context data (JSON)"},
    # Additional assistant properties (backward compat)
    {"prop": "name", "dtype": "string", "description": "Name/label"},
    {"prop": "description", "dtype": "string", "description": "Description/summary"},
    {"prop": "createdAt", "dtype": "date", "description": "Creation timestamp"},
    {"prop": "updatedAt", "dtype": "date", "description": "Update timestamp"},
    {"prop": "givenName", "dtype": "string", "description": "Given name (Person)"},
    {"prop": "familyName", "dtype": "string", "description": "Family name (Person)"},
    {"prop": "email", "dtype": "string", "description": "Email address"},
    {"prop": "phone", "dtype": "string", "description": "Phone number"},
    {"prop": "address", "dtype": "string", "description": "Address"},
    {"prop": "city", "dtype": "string", "description": "City"},
    {"prop": "state", "dtype": "string", "description": "State/province"},
    {"prop": "postalCode", "dtype": "string", "description": "Postal/ZIP code"},
    {"prop": "country", "dtype": "string", "description": "Country"},
    {"prop": "url", "dtype": "url", "description": "URL"},
    # Vault-related properties (backward compat)
    {"prop": "username", "dtype": "string", "description": "Username"},
    {"prop": "password", "dtype": "string", "description": "Password"},
    {"prop": "secret", "dtype": "string", "description": "Secret/API key"},
    {"prop": "appName", "dtype": "string", "description": "Application name"},
    {"prop": "cardNumber", "dtype": "string", "description": "Card number"},
    {"prop": "cardExpiry", "dtype": "string", "description": "Card expiry"},
    {"prop": "cardCvv", "dtype": "string", "description": "Card CVV"},
    {"prop": "billingAddress", "dtype": "string", "description": "Billing address"},
    {"prop": "identityNumber", "dtype": "string", "description": "Identity number"},
]

# Knowshowgo v0.1 Prototypes (minimal set for agent functionality)
# Aligned with Knowshowgo_SYSTEM_DESIGN_v0.1.md
# Root
DEFAULT_PROTOTYPES = [
    "BasePrototype",  # Root schema (all prototypes inherit from this)
    # Public semantic registry (minimum useful set)
    "Person",
    "Organization",
    "Place",
    "Thing",  # Generic physical object
    "DigitalResource",  # URL-anchored resource
    "CreativeWork",  # Article/post/video
    # Assistant / learning agent (minimum useful set)
    "Event",
    "Task",
    "Project",
    "Commandlet",  # Primitive IO op
    "Procedure",  # Learned workflow
    "Step",  # Sequence/DAG node
    "Trigger",  # Condition/trigger
    "QueueItem",  # Priority queue item
    "WebResource",  # Site identity (e.g., linkedin.com)
    # Backward compat (keep for existing code)
    "Object",  # Generic object (maps to Thing)
    "List",  # List container
    "DAG",  # Directed acyclic graph
    "Queue",  # Queue container
]

# Prototype inheritance mapping child -> parent
# Aligned with Knowshowgo design: all prototypes inherit from BasePrototype
PROTOTYPE_INHERITS = {
    # All prototypes inherit from BasePrototype
    "Person": "BasePrototype",
    "Organization": "BasePrototype",
    "Place": "BasePrototype",
    "Thing": "BasePrototype",
    "DigitalResource": "BasePrototype",
    "CreativeWork": "BasePrototype",
    "Event": "BasePrototype",
    "Task": "BasePrototype",
    "Project": "BasePrototype",
    "Commandlet": "BasePrototype",
    "Procedure": "BasePrototype",
    "Step": "BasePrototype",
    "Trigger": "BasePrototype",
    "QueueItem": "BasePrototype",
    "WebResource": "BasePrototype",
    # Backward compat inheritance
    "DAG": "List",
    "Queue": "List",
    "Object": "BasePrototype",
    "List": "BasePrototype",
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
        # Seed property defs (as PropertyDef nodes per Knowshowgo design)
        for pd in DEFAULT_PROPERTY_DEFS:
            prop_name = pd["prop"]
            dtype = pd["dtype"]
            description = pd.get("description", f"{prop_name} property")
            node = Node(
                kind="PropertyDef",
                labels=["PropertyDef", prop_name],
                props={
                    "name": prop_name,  # PropertyDef name
                    "valueType": dtype,  # Knowshowgo: valueType (string|number|boolean|date|url|json|topic_ref)
                    "cardinality": "0..*",  # Default cardinality
                    "description": description,
                    "status": "active",
                },
            )
            if embedding_fn:
                try:
                    node.llm_embedding = embedding_fn(f"{prop_name} {description}")
                except Exception:
                    node.llm_embedding = None
            self.memory.upsert(node, prov, embedding_request=True)
            ensured["property_defs"].append(node.uuid)

        # Seed prototypes (as Topics with isPrototype=true per Knowshowgo design)
        proto_nodes: Dict[str, Node] = {}
        for proto in DEFAULT_PROTOTYPES:
            # Create Prototype as Topic with isPrototype=true
            # Use proto name as primary label
            label = proto
            summary = self._get_prototype_summary(proto)
            node = Node(
                kind="topic",  # All nodes are Topics in Knowshowgo
                labels=[label],  # Primary label
                props={
                    "label": label,  # Primary label
                    "aliases": [],  # Additional labels
                    "summary": summary,
                    "isPrototype": True,  # Mark as Prototype
                    "status": "active",
                    "namespace": "public",
                    "protoId": proto,  # Backward compat
                    "version": "1.0.0",
                    "immutable": True,
                },
            )
            if embedding_fn:
                try:
                    node.llm_embedding = embedding_fn(f"{proto} {summary}")
                except Exception:
                    node.llm_embedding = None
            self.memory.upsert(node, prov, embedding_request=True)
            ensured["prototypes"].append(node.uuid)
            proto_nodes[proto] = node

        # Link prototype inheritance edges (inherits edge per Knowshowgo design)
        # Find PropertyDef for "instanceOf" to use as predicate reference (p)
        instance_of_prop_def_uuid = None
        for pd_uuid in ensured["property_defs"]:
            # Search for instanceOf PropertyDef
            # Note: This is simplified; in production would query by name
            pass  # Will use rel="inherits" for now, can enhance later with PropertyDef lookup
        
        for child, parent in PROTOTYPE_INHERITS.items():
            if child in proto_nodes and parent in proto_nodes:
                # Use "inherits" edge (Knowshowgo design uses "inherits" edge collection)
                # Can optionally add PropertyDef reference (p) if instanceOf PropertyDef is found
                self.add_assoc(
                    from_uuid=proto_nodes[child].uuid,
                    to_uuid=proto_nodes[parent].uuid,
                    rel="inherits",  # Knowshowgo: inherits edge collection
                    props={
                        "child": child,
                        "parent": parent,
                        "w": 1.0,  # Weight (fuzzy association strength)
                        "status": "accepted",
                    },
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

    def _get_prototype_summary(self, proto_name: str) -> str:
        """Get summary/description for a prototype."""
        summaries = {
            "BasePrototype": "Root prototype for all prototypes (schema definitions)",
            "Person": "A human individual",
            "Organization": "An organization or company",
            "Place": "A physical location",
            "Thing": "Generic physical object",
            "DigitalResource": "URL-anchored digital resource",
            "CreativeWork": "Article, post, video, or other creative work",
            "Event": "A calendar event or scheduled occurrence",
            "Task": "A task or to-do item",
            "Project": "A project containing multiple tasks",
            "Commandlet": "Primitive IO operation (HTTP_GET, BROWSER_GOTO, etc.)",
            "Procedure": "Learned workflow with steps",
            "Step": "A step in a procedure (sequence/DAG node)",
            "Trigger": "Trigger or condition for procedure execution",
            "QueueItem": "Item in a priority queue",
            "WebResource": "Web site identity (e.g., linkedin.com)",
            "Object": "Generic object (backward compat)",
            "List": "List container",
            "DAG": "Directed acyclic graph",
            "Queue": "Queue container",
        }
        return summaries.get(proto_name, f"{proto_name} prototype")

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
