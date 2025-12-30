from typing import List
from datetime import datetime, timezone

from src.personal_assistant.models import Provenance, Node, Edge
from src.personal_assistant.tools import MemoryTools


DEFAULT_PROTOTYPES = [
    {
        "name": "Person",
        "description": "Prototype for person entities",
        "context": "people and identities",
        "labels": ["prototype", "person"],
    },
    {
        "name": "Event",
        "description": "Prototype for events (meetings, reminders, schedules)",
        "context": "calendar events and occurrences",
        "labels": ["prototype", "event"],
    },
    {
        "name": "Procedure",
        "description": "Prototype for procedures/recipes/step-by-step instructions",
        "context": "procedures and workflows",
        "labels": ["prototype", "procedure"],
    },
    {
        "name": "DAG",
        "description": "Prototype for directed acyclic graph modeling procedural logic with nested nodes",
        "context": "graph structure for procedural logic",
        "labels": ["prototype", "dag"],
    },
    {
        "name": "Task",
        "description": "Prototype for tasks represented as DAG-backed procedures",
        "context": "task planning and execution",
        "labels": ["prototype", "task"],
        "base": "DAG",
    },
]


def ensure_default_prototypes(memory: MemoryTools, embedding_fn, trace_id: str = "ontology-init") -> List[str]:
    """
    Ensure default prototypes exist in memory; create if missing.
    embedding_fn: callable(str) -> List[float]
    Returns list of ensured prototype UUIDs.
    """
    ensured = []
    now = datetime.now(timezone.utc).isoformat()
    provenance = Provenance("user", now, 1.0, trace_id)

    existing = {}
    nodes_attr = getattr(memory, "nodes", None)
    if isinstance(nodes_attr, dict):
        for node in nodes_attr.values():
            if node.kind == "Prototype":
                existing[node.props.get("name")] = node
    else:
        try:
            results = memory.search("", top_k=100, filters={"kind": "Prototype"}, query_embedding=None)
            for r in results:
                name = r.get("props", {}).get("name") if isinstance(r, dict) else None
                if name:
                    existing[name] = r
        except Exception:
            pass

    for proto in DEFAULT_PROTOTYPES:
        if proto["name"] in existing:
            ensured.append(existing[proto["name"]].uuid if hasattr(existing[proto["name"]], "uuid") else existing[proto["name"]].get("uuid"))
            continue
        node = Node(
            kind="Prototype",
            labels=proto["labels"],
            props={"name": proto["name"], "description": proto["description"], "context": proto["context"]},
        )
        try:
            node.llm_embedding = embedding_fn(f"{proto['name']} {proto['description']} {proto['context']}") if embedding_fn else None
        except Exception:
            node.llm_embedding = None
        memory.upsert(node, provenance, embedding_request=True)
        existing[proto["name"]] = node
        ensured.append(node.uuid)
        # Link to base prototype if specified and available
        base_name = proto.get("base")
        if base_name and base_name in existing:
            base_uuid = existing[base_name].uuid if hasattr(existing[base_name], "uuid") else existing[base_name].get("uuid")
            try:
                edge = Edge(
                    from_node=node.uuid,
                    to_node=base_uuid,
                    rel="inherits_from",
                    props={"child": proto["name"], "parent": base_name},
                )
                memory.upsert(edge, provenance, embedding_request=False)
            except Exception:
                pass
    return ensured
