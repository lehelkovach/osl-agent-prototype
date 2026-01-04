from typing import Dict, Any, List, Optional, Callable
from collections import deque
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

    def load_dag_from_concept(self, concept_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Load a DAG structure from a concept node.
        Returns the DAG structure with nodes and edges, or None if not found.
        """
        # Find the concept node
        concept_node = None
        if hasattr(self.memory, "nodes"):
            concept_node = self.memory.nodes.get(concept_uuid)
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
        if hasattr(self.memory, "edges"):
            child_edges = [
                e for e in self.memory.edges.values()
                if e.from_node == concept_uuid and e.rel in ("has_step", "has_child")
            ]
            if child_edges:
                nodes = []
                for edge in child_edges:
                    child_node = self.memory.nodes.get(edge.to_node) if hasattr(self.memory, "nodes") else None
                    if child_node:
                        if isinstance(child_node, dict):
                            nodes.append(child_node)
                        else:
                            nodes.append(child_node.__dict__)
                return {
                    "concept_uuid": concept_uuid,
                    "nodes": nodes,
                    "edges": [{"from": e.from_node, "to": e.to_node, "rel": e.rel} for e in child_edges],
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
            node_uuid = node.get("uuid") or node.get("id") or str(idx)
            node_map[node_uuid] = node
            node_deps[node_uuid] = []

        # Process edges to build dependency map
        for edge in edges:
            from_node = edge.get("from") or edge.get("from_node")
            to_node = edge.get("to") or edge.get("to_node")
            rel = edge.get("rel", "depends_on")
            if rel == "depends_on":
                # to_node depends on from_node
                if to_node in node_deps:
                    node_deps[to_node].append(from_node)

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

        # Find initial bottom nodes
        bottom_nodes = self.find_bottom_nodes(dag)
        queue = deque(bottom_nodes)

        while queue:
            node = queue.popleft()
            node_uuid = node.get("uuid") or node.get("id") or "unknown"

            # Evaluate guard
            if not self.evaluate_node_guard(node, context):
                pending.append(node_uuid)
                continue

            # Extract tool command
            cmd = self.extract_tool_command(node)
            if not cmd:
                errors.append(f"Node {node_uuid} has no tool command")
                continue

            # Handle nested DAG execution
            if cmd.get("nested"):
                nested_uuid = cmd.get("concept_uuid")
                nested_result = self.execute_dag(nested_uuid, context, enqueue_fn)
                executed.append({"node": node_uuid, "nested": nested_uuid, "result": nested_result})
            else:
                # Enqueue or execute tool command
                if enqueue_fn:
                    enqueue_fn(cmd)
                executed.append({"node": node_uuid, "command": cmd})

            # After executing, check if any dependent nodes are now ready
            # (This is simplified - in a full implementation, we'd track dependencies)
            # For now, we'll just mark this node as done and continue

        return {
            "status": "completed" if not errors else "partial",
            "executed": executed,
            "pending": pending,
            "errors": errors,
            "concept_uuid": concept_uuid,
        }

