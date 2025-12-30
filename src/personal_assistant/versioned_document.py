from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


@dataclass
class VersionedDocument:
    store: "VersionedDocumentStore"
    doc_id: str
    version: int
    data: Dict[str, Any]
    embedding: List[float]
    node_uuid: str
    concept_uuid: Optional[str]

    def save(self, data: Dict[str, Any], embedding: Optional[List[float]], provenance: Provenance) -> "VersionedDocument":
        """Create a new version with updated data/embedding."""
        new_embedding = embedding if embedding is not None else self.embedding
        return self.store._create_version(
            doc_id=self.doc_id,
            data=data,
            embedding=new_embedding,
            provenance=provenance,
            base_version=self.version,
            concept_uuid=self.concept_uuid,
        )


class VersionedDocumentStore:
    """
    Abstraction over MemoryTools to store versioned JSON metadata associated to a concept node.
    Each version is a Node(kind="DocumentVersion") with props {doc_id, version, data, concept_uuid}.
    An edge `next_version` links versions; optionally link version -> concept with `describes`.
    """

    def __init__(self, memory: MemoryTools):
        self.memory = memory

    def create(
        self,
        doc_id: str,
        data: Dict[str, Any],
        embedding: List[float],
        provenance: Provenance,
        concept_uuid: Optional[str] = None,
    ) -> VersionedDocument:
        return self._create_version(doc_id, data, embedding, provenance, base_version=0, concept_uuid=concept_uuid)

    def load(self, doc_id: str, version: Optional[int] = None) -> Optional[VersionedDocument]:
        versions = self._all_versions(doc_id)
        if not versions:
            return None
        if version is None:
            version_node = max(versions, key=lambda n: n.props.get("version", 0))
        else:
            candidates = [n for n in versions if n.props.get("version") == version]
            if not candidates:
                return None
            version_node = candidates[0]
        return self._to_versioned_document(version_node)

    def from_similarity(self, query_embedding: List[float], top_k: int = 1) -> Optional[VersionedDocument]:
        results = self.memory.search("", top_k=top_k, query_embedding=query_embedding)
        if not results:
            return None
        first = results[0]
        node = self._dict_to_node(first) if isinstance(first, dict) else first
        if node.kind != "DocumentVersion":
            return None
        return self._to_versioned_document(node)

    def _create_version(
        self,
        doc_id: str,
        data: Dict[str, Any],
        embedding: List[float],
        provenance: Provenance,
        base_version: int,
        concept_uuid: Optional[str],
    ) -> VersionedDocument:
        next_version = base_version + 1
        node = Node(
            kind="DocumentVersion",
            labels=["history", doc_id],
            props={
                "doc_id": doc_id,
                "version": next_version,
                "data": data,
                "concept_uuid": concept_uuid,
                "ts": datetime.now(timezone.utc).isoformat(),
            },
            llm_embedding=embedding,
        )
        self.memory.upsert(node, provenance, embedding_request=True)
        if base_version > 0:
            # Link previous -> new
            prev = self.load(doc_id, base_version)
            if prev:
                edge = Edge(
                    from_node=prev.node_uuid,
                    to_node=node.uuid,
                    rel="next_version",
                    props={"doc_id": doc_id},
                )
                self.memory.upsert(edge, provenance, embedding_request=False)
        if concept_uuid:
            edge = Edge(
                from_node=node.uuid,
                to_node=concept_uuid,
                rel="describes",
                props={"doc_id": doc_id, "version": next_version},
            )
            self.memory.upsert(edge, provenance, embedding_request=False)
        return VersionedDocument(
            store=self,
            doc_id=doc_id,
            version=next_version,
            data=data,
            embedding=embedding,
            node_uuid=node.uuid,
            concept_uuid=concept_uuid,
        )

    def _all_versions(self, doc_id: str) -> List[Node]:
        # Prefer direct access when available (MockMemoryTools)
        nodes_attr = getattr(self.memory, "nodes", None)
        if isinstance(nodes_attr, dict):
            return [n for n in nodes_attr.values() if n.kind == "DocumentVersion" and n.props.get("doc_id") == doc_id]
        # Fallback to filtered search
        results = self.memory.search("", top_k=100, filters={"doc_id": doc_id}, query_embedding=None)
        nodes: List[Node] = []
        for r in results:
            nodes.append(self._dict_to_node(r) if isinstance(r, dict) else r)
        return nodes

    def _to_versioned_document(self, node: Node) -> VersionedDocument:
        return VersionedDocument(
            store=self,
            doc_id=node.props.get("doc_id"),
            version=node.props.get("version", 0),
            data=node.props.get("data", {}),
            embedding=node.llm_embedding or [],
            node_uuid=node.uuid,
            concept_uuid=node.props.get("concept_uuid"),
        )

    def _dict_to_node(self, data: Dict[str, Any]) -> Node:
        return Node(
            kind=data.get("kind", "DocumentVersion"),
            labels=data.get("labels", []),
            props=data.get("props", {}),
            uuid=data.get("uuid"),
            llm_embedding=data.get("llm_embedding"),
            status=data.get("status"),
        )
