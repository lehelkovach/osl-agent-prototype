from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


class KnowShowGoAPI:
    """
    Thin abstraction over MemoryTools to create concepts and link them to prototypes.
    """

    def __init__(self, memory: MemoryTools):
        self.memory = memory

    def create_concept(
        self,
        prototype_uuid: str,
        json_obj: Dict[str, Any],
        embedding: List[float],
        provenance: Optional[Provenance] = None,
    ) -> str:
        prov = provenance or Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="knowshowgo",
        )
        concept = Node(
            kind="Concept",
            labels=[json_obj.get("name", "concept")],
            props={**json_obj, "prototype_uuid": prototype_uuid},
            llm_embedding=embedding,
        )
        self.memory.upsert(concept, prov, embedding_request=True)
        edge = Edge(
            from_node=concept.uuid,
            to_node=prototype_uuid,
            rel="instantiates",
            props={"prototype_uuid": prototype_uuid},
        )
        self.memory.upsert(edge, prov, embedding_request=False)
        return concept.uuid
