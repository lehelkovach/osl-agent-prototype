from typing import Optional, List

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


class KnowledgeGraphInterface:
    """
    Abstraction over MemoryTools (backed by Arango or other) for creating
    prototypes and instantiating concepts from those prototypes.
    """

    def __init__(self, memory: MemoryTools):
        self.memory = memory

    def create_prototype(
        self,
        name: str,
        description: str,
        context: str,
        embedding: List[float],
        provenance: Provenance,
    ) -> Node:
        proto = Node(
            kind="Prototype",
            labels=[name],
            props={
                "name": name,
                "description": description,
                "context": context,
            },
            llm_embedding=embedding,
        )
        self.memory.upsert(proto, provenance, embedding_request=True)
        return proto

    def instantiate_concept(
        self,
        prototype_uuid: str,
        phrase: str,
        context: str,
        embedding: List[float],
        provenance: Provenance,
    ) -> Node:
        concept = Node(
            kind="Concept",
            labels=[phrase],
            props={
                "phrase": phrase,
                "context": context,
                "prototype_uuid": prototype_uuid,
            },
            llm_embedding=embedding,
        )
        self.memory.upsert(concept, provenance, embedding_request=True)
        edge = Edge(
            from_node=prototype_uuid,
            to_node=concept.uuid,
            rel="instantiates",
            props={},
        )
        self.memory.upsert(edge, provenance, embedding_request=False)
        return concept

    def get_prototype(self, prototype_uuid: str) -> Optional[Node]:
        return self._get_node_by_uuid(prototype_uuid)

    def get_concept(self, concept_uuid: str) -> Optional[Node]:
        return self._get_node_by_uuid(concept_uuid)

    def _get_node_by_uuid(self, node_uuid: str) -> Optional[Node]:
        # Try direct access if the memory exposes a node map
        nodes = getattr(self.memory, "nodes", None)
        if isinstance(nodes, dict) and node_uuid in nodes:
            return nodes[node_uuid]
        # Fallback to a filtered search if supported
        try:
            results = self.memory.search(
                query_text="",
                top_k=1,
                filters={"uuid": node_uuid},
                query_embedding=None,
            )
            if results:
                # MemoryTools may return dicts
                data = results[0]
                if isinstance(data, Node):
                    return data
                if isinstance(data, dict) and "uuid" in data:
                    return Node(
                        kind=data.get("kind", ""),
                        labels=data.get("labels", []),
                        props=data.get("props", {}),
                        uuid=data.get("uuid"),
                        llm_embedding=data.get("llm_embedding"),
                        status=data.get("status"),
                    )
        except Exception:
            return None
        return None
