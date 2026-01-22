from typing import Dict, Any, List, Optional, Callable, Tuple
from datetime import datetime, timezone

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


class DAGExecutor:
    """
    Executes DAG structures stored as concepts in KnowShowGo.
    Loads DAG, evaluates bottom nodes (leaf nodes with no dependencies),
    makes decisions based on guards/rules, and enqueues tool commands.
    """

    def __init__(self, memory: MemoryTools, queue_manager=None):
        self.memory = memory
        self.queue_manager = queue_manager

    def _get_node(self, uuid: str) -> Optional[Dict[str, Any]]:
        if hasattr(self.memory, "get_node"):
            return self.memory.get_node(uuid)
        nodes_attr = getattr(self.memory, "nodes", None)
        if nodes_attr is None:
            return None
        if hasattr(nodes_attr, "get"):
            return nodes_attr.get(uuid)
        return None

    def _get_edges(
        self,
        from_node: Optional[str] = None,
        rel: Optional[str] = None,
    ) -> List[Any]:
        if hasattr(self.memory, "get_edges"):
            return self.memory.get_edges(from_node=from_node, rel=rel)
        edges_attr = getattr(self.memory, "edges", None)
        if edges_attr is None:
            return []
        if hasattr(edges_attr, "values"):
            edges_iter = edges_attr.values()
        elif hasattr(edges_attr, "all"):
            edges_iter = edges_attr.all()
        else:
            return []
        edges: List[Any] = []
        for edge in edges_iter:
            if rel and self._edge_rel(edge) != rel:
                continue
            if from_node and self._edge_from(edge) != from_node:
                continue
            edges.append(edge)
        return edges

    def _edge_from(self, edge: Any) -> Optional[str]:
        if isinstance(edge, dict):
            val = edge.get("from_node") or edge.get("_from")
        else:
            val = getattr(edge, "from_node", None)
        if isinstance(val, str) and "/" in val:
            return val.split("/")[-1]
        return val

    def _edge_to(self, edge: Any) -> Optional[str]:
        if isinstance(edge, dict):
            val = edge.get("to_node") or edge.get("_to")
        else:
            val = getattr(edge, "to_node", None)
        if isinstance(val, str) and "/" in val:
            return val.split("/")[-1]
        return val

    def _edge_rel(self, edge: Any) -> Optional[str]:
        if isinstance(edge, dict):
            return edge.get("rel")
        return getattr(edge, "rel", None)

    def _node_id(self, node: Dict[str, Any], idx: int) -> str:
        props = node.get("props", {}) if isinstance(node, dict) else {}
        return (
            node.get("id")
            or node.get("step_id")
            or props.get("step_id")
            or props.get("id")
            or node.get("uuid")
            or str(idx)
        )

    def _node_order(self, node: Dict[str, Any], idx: int) -> int:
        if "order" in node:
            return int(node.get("order") or 0)
        props = node.get("props", {}) if isinstance(node, dict) else {}
        return int(props.get("order") or idx)

    def load_dag_from_concept(self, concept_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Load a DAG structure from a concept node.
        Returns the DAG structure with nodes and edges, or None if not found.
        """
        # Find the concept node
        concept_node = None
        if hasattr(self.memory, "get_node"):
            concept_node = self.memory.get_node(concept_uuid)
        elif hasattr(self.memory, "nodes"):
            concept_node = self.memory.nodes.get(concept_uuid) if hasattr(self.memory.nodes, "get") else None
        else:
            # Fallback: search for it
            results = self.memory.search("", top_k=1000, filters={"kind": "Concept"})
            for r in results:
                uuid_val = r.get("uuid") if isinstance(r, dict) else getattr(r, "uuid", None)
                if uuid_val == concept_uuid:
                    concept_node = r
                    break

        if not concept_node:
            return None

        # Extract DAG structure from concept props
        if isinstance(concept_node, dict):
            props = concept_node.get("props", {})
        else:
            props = getattr(concept_node, "props", {})

        # DAG can be stored in various formats:
        # 1. Direct in props: props["dag"] or props["steps"]
        # 2. As child concepts linked via edges
        dag_structure = props.get("dag") or props.get("steps") or props.get("children")
        if dag_structure:
            return {
                "concept_uuid": concept_uuid,
                "nodes": dag_structure if isinstance(dag_structure, list) else dag_structure.get("nodes", []),
                "edges": dag_structure.get("edges", []) if isinstance(dag_structure, dict) else [],
                "metadata": props,
            }

        # Alternative: load from child concepts via edges
        child_edges = self._get_edges(from_node=concept_uuid)
        child_edges = [e for e in child_edges if self._edge_rel(e) in ("has_step", "has_child")]
        if child_edges:
            nodes = []
            step_ids = set()
            for edge in child_edges:
                to_uuid = self._edge_to(edge)
                child_node = self._get_node(to_uuid) if to_uuid else None
                if child_node:
                    if isinstance(child_node, dict):
                        nodes.append(child_node)
                        if child_node.get("uuid"):
                            step_ids.add(child_node.get("uuid"))
                    else:
                        nodes.append(child_node.__dict__)
                        if getattr(child_node, "uuid", None):
                            step_ids.add(child_node.uuid)
            dep_edges = [e for e in self._get_edges(rel="depends_on") if self._edge_from(e) in step_ids]
            dep_edges = [e for e in dep_edges if self._edge_to(e) in step_ids]
            edges = []
            for edge in child_edges + dep_edges:
                edges.append(
                    {
                        "from": self._edge_from(edge),
                        "to": self._edge_to(edge),
                        "rel": self._edge_rel(edge),
                    }
                )
            return {
                "concept_uuid": concept_uuid,
                "nodes": nodes,
                "edges": edges,
                "metadata": props,
            }

        return None

    def find_bottom_nodes(self, dag: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Find bottom nodes (leaf nodes with no dependencies) in the DAG.
        Returns list of node dicts that are ready to execute.
        """
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])

        if not nodes:
            return []

        # Build dependency graph
        # Map node UUID/index to list of dependencies
        node_deps = {}
        node_map = {}

        # Index nodes by UUID or order
        for idx, node in enumerate(nodes):
            node_uuid = self._node_id(node, idx)
            node_map[node_uuid] = node
            node_deps[node_uuid] = []
        uuid_to_id = {}
        for node_id, node in node_map.items():
            node_uuid = node.get("uuid") or node.get("props", {}).get("uuid")
            if node_uuid:
                uuid_to_id[node_uuid] = node_id

        # Process edges to build dependency map
        for edge in edges:
            if isinstance(edge, dict):
                from_node = edge.get("from") or edge.get("from_node")
                to_node = edge.get("to") or edge.get("to_node")
                rel = edge.get("rel", "depends_on")
            else:
                from_node = getattr(edge, "from_node", None)
                to_node = getattr(edge, "to_node", None)
                rel = getattr(edge, "rel", "depends_on")
            if from_node in uuid_to_id:
                from_node = uuid_to_id[from_node]
            if to_node in uuid_to_id:
                to_node = uuid_to_id[to_node]
            if rel == "depends_on":
                # from_node depends on to_node
                if from_node in node_deps and to_node:
                    node_deps[from_node].append(to_node)

        # Include inline depends_on from node properties
        for node_uuid, node in node_map.items():
            deps = node.get("depends_on") or node.get("props", {}).get("depends_on") or []
            for dep in deps:
                mapped = uuid_to_id.get(dep, dep)
                if mapped in node_deps:
                    node_deps[node_uuid].append(mapped)

        # Find nodes with no dependencies
        bottom_nodes = []
        for node_uuid, deps in node_deps.items():
            if not deps:
                bottom_nodes.append(node_map[node_uuid])

        return bottom_nodes

    def evaluate_node_guard(self, node: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate a node's guard condition to determine if it should execute.
        Returns True if the node should execute, False otherwise.
        """
        guard = node.get("guard") or node.get("guard_text") or node.get("props", {}).get("guard")
        if not guard:
            return True  # No guard means always execute

        # Simple guard evaluation (can be extended with more sophisticated logic)
        # For now, just check if guard is a boolean or simple condition
        if isinstance(guard, bool):
            return guard
        if isinstance(guard, str):
            # Simple string-based guards (can be extended)
            if guard.lower() in ("true", "always", "yes"):
                return True
            if guard.lower() in ("false", "never", "no"):
                return False
            # Default: execute if guard exists (can be made more sophisticated)
            return True

        return True

    def extract_tool_command(self, node: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Extract tool command from a node.
        Returns dict with tool name and params, or None if not a tool command.
        """
        # Check various formats for tool commands
        tool = node.get("tool") or node.get("commandtype") or node.get("command")
        if not tool and isinstance(node.get("props"), dict):
            tool = node["props"].get("tool") or node["props"].get("commandtype")
        if not tool:
            # Check if it's a nested concept that needs to be loaded
            concept_uuid = node.get("concept_uuid") or node.get("uuid")
            if concept_uuid:
                # This is a reference to another concept - load it recursively
                nested_dag = self.load_dag_from_concept(concept_uuid)
                if nested_dag:
                    # Return a special marker for nested execution
                    return {"tool": "dag.execute", "concept_uuid": concept_uuid, "nested": True}
            return None

        params = node.get("params") or node.get("metadata") or node.get("props", {})
        # Clean up params to remove non-tool-specific fields
        clean_params = {k: v for k, v in params.items() if k not in ("uuid", "id", "order", "guard", "guard_text")}

        return {"tool": tool, "params": clean_params}

    def _topological_order(self, dag: Dict[str, Any]) -> Tuple[List[str], Dict[str, Dict[str, Any]]]:
        nodes = dag.get("nodes", [])
        edges = dag.get("edges", [])
        node_map: Dict[str, Dict[str, Any]] = {}
        order_map: Dict[str, int] = {}

        for idx, node in enumerate(nodes):
            node_id = self._node_id(node, idx)
            node_map[node_id] = node
            order_map[node_id] = self._node_order(node, idx)
        uuid_to_id = {}
        for node_id, node in node_map.items():
            node_uuid = node.get("uuid") or node.get("props", {}).get("uuid")
            if node_uuid:
                uuid_to_id[node_uuid] = node_id

        deps: Dict[str, set] = {nid: set() for nid in node_map}
        for edge in edges:
            if isinstance(edge, dict):
                rel = edge.get("rel", "depends_on")
                from_node = edge.get("from") or edge.get("from_node")
                to_node = edge.get("to") or edge.get("to_node")
            else:
                rel = getattr(edge, "rel", "depends_on")
                from_node = getattr(edge, "from_node", None)
                to_node = getattr(edge, "to_node", None)
            if rel != "depends_on":
                continue
            if from_node in uuid_to_id:
                from_node = uuid_to_id[from_node]
            if to_node in uuid_to_id:
                to_node = uuid_to_id[to_node]
            if from_node in deps and to_node:
                deps[from_node].add(to_node)

        for node_id, node in node_map.items():
            node_deps = node.get("depends_on") or node.get("props", {}).get("depends_on") or []
            for dep in node_deps:
                mapped = uuid_to_id.get(dep, dep)
                if mapped in deps:
                    deps[node_id].add(mapped)

        adjacency: Dict[str, set] = {nid: set() for nid in node_map}
        in_degree: Dict[str, int] = {nid: len(dep_set) for nid, dep_set in deps.items()}
        for node_id, dep_set in deps.items():
            for dep in dep_set:
                if dep in adjacency:
                    adjacency[dep].add(node_id)

        ready = [nid for nid, deg in in_degree.items() if deg == 0]
        ready.sort(key=lambda nid: order_map.get(nid, 0))
        order: List[str] = []

        while ready:
            current = ready.pop(0)
            order.append(current)
            for child in sorted(adjacency.get(current, set()), key=lambda nid: order_map.get(nid, 0)):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    ready.append(child)
                    ready.sort(key=lambda nid: order_map.get(nid, 0))

        if len(order) < len(node_map):
            remaining = [nid for nid in node_map if nid not in order]
            remaining.sort(key=lambda nid: order_map.get(nid, 0))
            order.extend(remaining)

        return order, node_map

    def execute_dag(
        self,
        concept_uuid: str,
        context: Optional[Dict[str, Any]] = None,
        enqueue_fn: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """
        Execute a DAG structure loaded from a concept.
        Evaluates bottom nodes, checks guards, and enqueues tool commands.
        Returns execution results.
        """
        dag = self.load_dag_from_concept(concept_uuid)
        if not dag:
            return {"status": "error", "error": f"DAG not found for concept {concept_uuid}"}

        executed = []
        pending = []
        errors = []
        skipped = []

        execution_order, node_map = self._topological_order(dag)

        for node_id in execution_order:
            node = node_map[node_id]

            # Evaluate guard
            if not self.evaluate_node_guard(node, context):
                pending.append(node_id)
                skipped.append(node_id)
                continue

            # Extract tool command
            cmd = self.extract_tool_command(node)
            if not cmd:
                errors.append(f"Node {node_id} has no tool command")
                continue

            # Handle nested DAG execution
            if cmd.get("nested"):
                nested_uuid = cmd.get("concept_uuid")
                nested_result = self.execute_dag(nested_uuid, context, enqueue_fn)
                executed.append({"node": node_id, "nested": nested_uuid, "result": nested_result})
            else:
                # Enqueue or execute tool command
                if enqueue_fn:
                    enqueue_fn(cmd)
                executed.append({"node": node_id, "command": cmd})

        return {
            "status": "completed" if not errors else "partial",
            "executed": executed,
            "pending": pending,
            "skipped": skipped,
            "errors": errors,
            "concept_uuid": concept_uuid,
            "execution_order": execution_order,
        }

