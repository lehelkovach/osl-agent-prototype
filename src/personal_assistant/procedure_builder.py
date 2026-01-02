from typing import List, Dict, Any, Tuple, Callable, Optional

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


EmbedFn = Callable[[str], List[float]]


class ProcedureBuilder:
    """
    Helper to persist Procedure + Step nodes with embeddings and dependency edges.
    Enforces acyclic dependencies (DAG).
    """

    def __init__(self, memory: MemoryTools, embed_fn: EmbedFn):
        self.memory = memory
        self.embed_fn = embed_fn

    def create_procedure(
        self,
        title: str,
        description: str,
        steps: List[Dict[str, Any]],
        dependencies: Optional[List[Tuple[int, int]]] = None,
        guards: Optional[Dict[int, str]] = None,
        provenance: Optional[Provenance] = None,
        extra_props: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a Procedure node, its Step nodes, and dependency edges.

        steps: list of dicts with at least "title"; optional "payload" and "order".
        dependencies: list of (prereq_index, step_index) pairs (0-based indices into steps).
        guards: optional map of step_index -> guard text (stored on Step props as guard_text).
        """
        dependencies = dependencies or []
        guards = guards or {}
        prov = provenance or Provenance(source="user", ts="now", confidence=1.0, trace_id="procedure")

        # Validate dependency indices
        max_idx = len(steps) - 1
        for a, b in dependencies:
            if a < 0 or a > max_idx or b < 0 or b > max_idx:
                raise ValueError("Dependency index out of range")

        if self._has_cycle(len(steps), dependencies):
            raise ValueError("Procedure dependencies must be acyclic")

        proc_props = {"title": title, "description": description}
        if extra_props:
            proc_props.update(extra_props)
        proc_node = Node(kind="Procedure", labels=["procedure"], props=proc_props)
        proc_node.llm_embedding = self.embed_fn(title)
        self.memory.upsert(proc_node, prov, embedding_request=True)

        step_nodes: List[Node] = []
        for idx, step in enumerate(steps):
            node = Node(
                kind="Step",
                labels=["step"],
                props={
                    "title": step.get("title"),
                    "payload": step.get("payload"),
                    "tool": step.get("tool"),
                    "order": step.get("order", idx),
                    "guard_text": guards.get(idx),
                    "guard": step.get("guard"),
                    "on_fail": step.get("on_fail"),
                    "procedure_uuid": proc_node.uuid,
                },
            )
            node.llm_embedding = self.embed_fn(step.get("title", "") or "")
            self.memory.upsert(node, prov, embedding_request=True)
            step_nodes.append(node)
            # Link procedure -> step
            self.memory.upsert(
                Edge(from_node=proc_node.uuid, to_node=node.uuid, rel="has_step", props={"order": idx}),
                prov,
                embedding_request=False,
            )

        # Dependency edges
        for prereq_idx, step_idx in dependencies:
            prereq = step_nodes[prereq_idx]
            dep = step_nodes[step_idx]
            self.memory.upsert(
                Edge(
                    from_node=dep.uuid,
                    to_node=prereq.uuid,
                    rel="depends_on",
                    props={"from_order": dep.props.get("order"), "to_order": prereq.props.get("order")},
                ),
                prov,
                embedding_request=False,
            )

        return {
            "procedure_uuid": proc_node.uuid,
            "step_uuids": [n.uuid for n in step_nodes],
        }

    def search_procedures(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Retrieve procedures by embedding similarity. Falls back to text-only if embedding_fn fails.
        """
        try:
            embedding = self.embed_fn(query)
        except Exception:
            embedding = None
        results = self.memory.search(query, top_k=top_k, filters={"kind": "Procedure"}, query_embedding=embedding)
        # Normalize to dicts for the caller
        normalized = []
        for r in results:
            if isinstance(r, dict):
                normalized.append(r)
            elif hasattr(r, "__dict__"):
                normalized.append(r.__dict__)
        return normalized

    def _has_cycle(self, n_steps: int, deps: List[Tuple[int, int]]) -> bool:
        adj: Dict[int, List[int]] = {i: [] for i in range(n_steps)}
        indegree = [0] * n_steps
        for prereq, step in deps:
            adj[prereq].append(step)
            indegree[step] += 1
        # Kahn's algorithm
        queue = [i for i in range(n_steps) if indegree[i] == 0]
        visited = 0
        while queue:
            cur = queue.pop(0)
            visited += 1
            for nei in adj[cur]:
                indegree[nei] -= 1
                if indegree[nei] == 0:
                    queue.append(nei)
        return visited != n_steps
