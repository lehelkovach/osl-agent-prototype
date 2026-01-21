"""
Procedure Manager - LLM JSON to KnowShowGo DAG conversion.

This module handles:
1. Defining JSON schemas for LLM-generated procedures
2. Validating procedure JSON from LLM
3. Converting validated JSON to KnowShowGo DAG structure
4. Storing and retrieving procedures with proper graph relationships
"""
import json
import logging
import os
import hashlib
from typing import Any, Callable, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools

logger = logging.getLogger(__name__)

EmbedFn = Callable[[str], List[float]]


# =============================================================================
# JSON Schema for LLM-Generated Procedures
# =============================================================================

PROCEDURE_JSON_SCHEMA = {
    "type": "object",
    "required": ["name", "description", "steps"],
    "properties": {
        "name": {
            "type": "string",
            "description": "Short name for the procedure (e.g., 'LinkedIn Login')"
        },
        "description": {
            "type": "string",
            "description": "Detailed description of what this procedure does"
        },
        "goal": {
            "type": "string",
            "description": "The goal this procedure achieves"
        },
        "tags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Tags for categorization (e.g., ['web', 'login', 'automation'])"
        },
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "tool", "params"],
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique identifier for this step (e.g., 'step_1')"
                    },
                    "name": {
                        "type": "string",
                        "description": "Human-readable name for this step"
                    },
                    "tool": {
                        "type": "string",
                        "description": "Tool to execute (e.g., 'web.fill', 'memory.remember')"
                    },
                    "params": {
                        "type": "object",
                        "description": "Parameters for the tool"
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of step IDs this step depends on"
                    },
                    "guard": {
                        "type": "string",
                        "description": "Condition that must be true to execute this step"
                    },
                    "on_fail": {
                        "type": "string",
                        "enum": ["stop", "skip", "retry", "ask_user"],
                        "description": "What to do if this step fails"
                    },
                    "retries": {
                        "type": "integer",
                        "description": "Number of retries if step fails"
                    }
                }
            }
        },
        "metadata": {
            "type": "object",
            "properties": {
                "version": {"type": "string"},
                "author": {"type": "string"},
                "created_at": {"type": "string"},
                "domain": {"type": "string"},
                "url_pattern": {"type": "string"}
            }
        }
    }
}

# Example procedure JSON for LLM reference
PROCEDURE_JSON_EXAMPLE = {
    "name": "LinkedIn Login",
    "description": "Log into LinkedIn using stored credentials",
    "goal": "Authenticate user on LinkedIn",
    "tags": ["web", "login", "linkedin"],
    "steps": [
        {
            "id": "step_1",
            "name": "Navigate to login page",
            "tool": "web.get_dom",
            "params": {"url": "https://www.linkedin.com/login"},
            "depends_on": [],
            "on_fail": "stop"
        },
        {
            "id": "step_2",
            "name": "Fill email field",
            "tool": "web.fill",
            "params": {
                "url": "https://www.linkedin.com/login",
                "selector": "#username",
                "text": "${credentials.email}"
            },
            "depends_on": ["step_1"],
            "on_fail": "ask_user"
        },
        {
            "id": "step_3",
            "name": "Fill password field",
            "tool": "web.fill",
            "params": {
                "url": "https://www.linkedin.com/login",
                "selector": "#password",
                "text": "${credentials.password}"
            },
            "depends_on": ["step_1"],
            "on_fail": "ask_user"
        },
        {
            "id": "step_4",
            "name": "Click sign in button",
            "tool": "web.click_selector",
            "params": {
                "url": "https://www.linkedin.com/login",
                "selector": "button[type='submit']"
            },
            "depends_on": ["step_2", "step_3"],
            "on_fail": "retry",
            "retries": 2
        },
        {
            "id": "step_5",
            "name": "Verify login success",
            "tool": "web.screenshot",
            "params": {"url": "https://www.linkedin.com/feed/"},
            "depends_on": ["step_4"],
            "on_fail": "skip"
        }
    ],
    "metadata": {
        "version": "1.0",
        "domain": "linkedin.com",
        "url_pattern": "linkedin.com/login"
    }
}

PROCEDURE_GRAPH_SCHEMA_VERSION = "ksg-procedure-0.2"
PROCEDURE_GRAPH_SCHEMA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "config", "procedure_graph_schema.json")
)
PROCEDURE_GRAPH_SCHEMA_FALLBACK = {
    "type": "object",
    "hint": "Fallback schema: see config/procedure_graph_schema.json",
    "properties": {"nodes": {}, "edges": {}, "subprocedures": {}},
}
PROCEDURE_GRAPH_JSON_EXAMPLE = {
    "schema_version": PROCEDURE_GRAPH_SCHEMA_VERSION,
    "name": "Login Flow",
    "description": "Login with retry loop",
    "nodes": [
        {"id": "get_dom", "type": "operation", "tool": "web.get_dom", "params": {"url": "https://example.com/login"}},
        {"id": "check_login", "type": "conditional", "condition": "page_has_login_form"},
        {"id": "call_login", "type": "procedure_call", "procedure": "LoginSub"},
        {"id": "retry_loop", "type": "loop", "condition": "not_logged_in", "body": ["get_dom", "call_login"], "max_iterations": 2},
    ],
    "edges": [
        {"from": "get_dom", "to": "check_login", "rel": "depends_on"},
        {"from": "check_login", "to": "call_login", "rel": "branch_true"},
        {"from": "retry_loop", "to": "get_dom", "rel": "loop_back"},
    ],
    "subprocedures": [
        {
            "name": "LoginSub",
            "description": "Subprocedure for login",
            "nodes": [
                {
                    "id": "fill_login",
                    "type": "operation",
                    "tool": "form.autofill",
                    "params": {"url": "https://example.com/login", "form_type": "login"},
                }
            ],
            "edges": [],
        }
    ],
}


@dataclass
class ValidationError:
    """Validation error for procedure JSON."""
    path: str
    message: str
    value: Any = None


@dataclass
class ValidationResult:
    """Result of validating procedure JSON."""
    valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ProcedureManager:
    """
    Manages LLM-generated procedures as DAGs in KnowShowGo memory.
    
    Flow:
    1. LLM generates procedure JSON following the schema
    2. JSON is validated against schema
    3. Valid JSON is converted to KnowShowGo DAG:
       - Procedure node (root)
       - Step nodes (children)
       - depends_on edges (DAG relationships)
    4. DAG is stored in memory with embeddings for retrieval
    """
    
    def __init__(
        self,
        memory: MemoryTools,
        embed_fn: Optional[EmbedFn] = None,
        ksg: Optional[Any] = None,  # KnowShowGoAPI or KnowShowGoAdapter
    ):
        self.memory = memory
        self.embed_fn = embed_fn
        self.ksg = ksg
        self._graph_schema_cache: Optional[Dict[str, Any]] = None
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for procedure generation."""
        return PROCEDURE_JSON_SCHEMA
    
    def get_example(self) -> Dict[str, Any]:
        """Get an example procedure JSON."""
        return PROCEDURE_JSON_EXAMPLE

    def get_graph_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for graph-based procedures."""
        if self._graph_schema_cache is not None:
            return self._graph_schema_cache
        try:
            with open(PROCEDURE_GRAPH_SCHEMA_PATH, "r", encoding="utf-8") as f:
                self._graph_schema_cache = json.load(f)
        except Exception:
            self._graph_schema_cache = PROCEDURE_GRAPH_SCHEMA_FALLBACK
        return self._graph_schema_cache

    def get_graph_example(self) -> Dict[str, Any]:
        """Get an example graph procedure JSON."""
        return PROCEDURE_GRAPH_JSON_EXAMPLE
    
    def get_prompt_instructions(self) -> str:
        """Get instructions for LLM to generate procedures."""
        return f"""
When creating a procedure, generate JSON following this structure:

```json
{json.dumps(PROCEDURE_JSON_EXAMPLE, indent=2)}
```

Key requirements:
1. Each step must have a unique 'id' (e.g., 'step_1', 'step_2')
2. Use 'depends_on' to specify which steps must complete first
3. Steps form a DAG (no circular dependencies)
4. Available tools: web.get_dom, web.fill, web.click_selector, web.screenshot, 
   memory.remember, memory.search, shell.run, calendar.create_event, etc.
5. Use ${{variable}} syntax for dynamic values (e.g., ${{credentials.email}})
6. Set 'on_fail' to control error handling: stop, skip, retry, ask_user

For more complex control flow (loops, conditionals, recursion), you may use the
graph-based schema (nodes/edges/subprocedures). Schema file:
  {PROCEDURE_GRAPH_SCHEMA_PATH}

Example:
```json
{json.dumps(PROCEDURE_GRAPH_JSON_EXAMPLE, indent=2)}
```
"""
    
    def validate(self, procedure_json: Union[str, Dict]) -> ValidationResult:
        """
        Validate procedure JSON against the schema.
        
        Returns ValidationResult with errors if invalid.
        """
        errors = []
        warnings = []
        
        # Parse JSON string if needed
        if isinstance(procedure_json, str):
            try:
                procedure_json = json.loads(procedure_json)
            except json.JSONDecodeError as e:
                return ValidationResult(
                    valid=False,
                    errors=[ValidationError(path="$", message=f"Invalid JSON: {e}")]
                )

        if self._is_graph_schema(procedure_json):
            return self._validate_graph(procedure_json)
        
        # Check required fields
        for field in ["name", "description", "steps"]:
            if field not in procedure_json:
                errors.append(ValidationError(
                    path=f"$.{field}",
                    message=f"Required field '{field}' is missing"
                ))
        
        if errors:
            return ValidationResult(valid=False, errors=errors)
        
        # Validate steps
        steps = procedure_json.get("steps", [])
        if not isinstance(steps, list):
            errors.append(ValidationError(
                path="$.steps",
                message="'steps' must be an array"
            ))
            return ValidationResult(valid=False, errors=errors)
        
        if len(steps) == 0:
            errors.append(ValidationError(
                path="$.steps",
                message="Procedure must have at least one step"
            ))
        
        # Collect step IDs for dependency validation
        step_ids = set()
        for idx, step in enumerate(steps):
            path = f"$.steps[{idx}]"
            
            # Check required step fields
            if "id" not in step:
                errors.append(ValidationError(
                    path=f"{path}.id",
                    message="Step must have an 'id'"
                ))
            else:
                step_id = step["id"]
                if step_id in step_ids:
                    errors.append(ValidationError(
                        path=f"{path}.id",
                        message=f"Duplicate step ID: {step_id}"
                    ))
                step_ids.add(step_id)
            
            if "tool" not in step:
                errors.append(ValidationError(
                    path=f"{path}.tool",
                    message="Step must have a 'tool'"
                ))
            
            if "params" not in step:
                warnings.append(f"Step {step.get('id', idx)} has no params")
        
        # Validate dependencies
        for idx, step in enumerate(steps):
            depends_on = step.get("depends_on", [])
            for dep_id in depends_on:
                if dep_id not in step_ids:
                    errors.append(ValidationError(
                        path=f"$.steps[{idx}].depends_on",
                        message=f"Unknown dependency: {dep_id}",
                        value=dep_id
                    ))
        
        # Check for cycles
        if not errors:
            has_cycle, cycle_path = self._detect_cycle(steps)
            if has_cycle:
                errors.append(ValidationError(
                    path="$.steps",
                    message=f"Circular dependency detected: {' -> '.join(cycle_path)}"
                ))
        
        return ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _is_graph_schema(self, procedure_json: Dict[str, Any]) -> bool:
        if not isinstance(procedure_json, dict):
            return False
        if isinstance(procedure_json.get("nodes"), list):
            return True
        schema_version = str(procedure_json.get("schema_version") or "")
        return schema_version.startswith("ksg-procedure")

    def _validate_graph(self, procedure_json: Dict[str, Any]) -> ValidationResult:
        errors: List[ValidationError] = []
        warnings: List[str] = []

        if not procedure_json.get("name"):
            errors.append(ValidationError(path="$.name", message="Missing name"))
        if not procedure_json.get("description"):
            errors.append(ValidationError(path="$.description", message="Missing description"))

        nodes = procedure_json.get("nodes") or []
        if not isinstance(nodes, list) or not nodes:
            errors.append(ValidationError(path="$.nodes", message="nodes must be a non-empty list"))
            return ValidationResult(valid=False, errors=errors, warnings=warnings)

        node_ids = set()
        for idx, node in enumerate(nodes):
            if not isinstance(node, dict):
                errors.append(ValidationError(path=f"$.nodes[{idx}]", message="Node must be an object"))
                continue
            node_id = node.get("id")
            node_type = node.get("type") or node.get("node_type")
            if not node_id:
                errors.append(ValidationError(path=f"$.nodes[{idx}].id", message="Node id required"))
            if not node_type:
                errors.append(ValidationError(path=f"$.nodes[{idx}].type", message="Node type required"))
            if node_id:
                if node_id in node_ids:
                    errors.append(ValidationError(path=f"$.nodes[{idx}].id", message="Duplicate node id", value=node_id))
                node_ids.add(node_id)
            if node_type == "operation" and not node.get("tool"):
                errors.append(ValidationError(path=f"$.nodes[{idx}].tool", message="Operation nodes require tool"))
            if node_type == "procedure_call" and not (node.get("procedure") or node.get("procedure_ref")):
                errors.append(ValidationError(path=f"$.nodes[{idx}].procedure", message="Procedure call requires procedure/procedure_ref"))
            if node_type in ("conditional", "loop") and not node.get("condition"):
                errors.append(ValidationError(path=f"$.nodes[{idx}].condition", message="Conditional/loop requires condition"))

        edges = procedure_json.get("edges") or []
        if edges and not isinstance(edges, list):
            errors.append(ValidationError(path="$.edges", message="edges must be a list"))
        for idx, edge in enumerate(edges):
            if not isinstance(edge, dict):
                errors.append(ValidationError(path=f"$.edges[{idx}]", message="Edge must be an object"))
                continue
            from_id = edge.get("from")
            to_id = edge.get("to")
            rel = edge.get("rel")
            if not from_id or not to_id or not rel:
                errors.append(ValidationError(path=f"$.edges[{idx}]", message="Edge requires from/to/rel"))
            if from_id and from_id not in node_ids:
                errors.append(ValidationError(path=f"$.edges[{idx}].from", message="Unknown node id", value=from_id))
            if to_id and to_id not in node_ids:
                errors.append(ValidationError(path=f"$.edges[{idx}].to", message="Unknown node id", value=to_id))

        subprocedures = procedure_json.get("subprocedures") or []
        names = set()
        for idx, sub in enumerate(subprocedures):
            if not isinstance(sub, dict):
                errors.append(ValidationError(path=f"$.subprocedures[{idx}]", message="Subprocedure must be an object"))
                continue
            name = sub.get("name")
            if not name:
                errors.append(ValidationError(path=f"$.subprocedures[{idx}].name", message="Subprocedure name required"))
            elif name in names:
                errors.append(ValidationError(path=f"$.subprocedures[{idx}].name", message="Duplicate subprocedure name"))
            names.add(name)
            if not sub.get("nodes"):
                errors.append(ValidationError(path=f"$.subprocedures[{idx}].nodes", message="Subprocedure nodes required"))

        # Soft check: procedure_call node references
        for node in nodes:
            if node.get("type") == "procedure_call":
                proc_name = node.get("procedure")
                if proc_name and proc_name not in names and proc_name != procedure_json.get("name"):
                    warnings.append(f"procedure_call references unknown subprocedure '{proc_name}'")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
    
    def _detect_cycle(self, steps: List[Dict]) -> Tuple[bool, List[str]]:
        """Detect cycles in step dependencies using DFS."""
        # Build adjacency list
        graph: Dict[str, List[str]] = {}
        for step in steps:
            step_id = step.get("id", "")
            graph[step_id] = step.get("depends_on", [])
        
        visited = set()
        rec_stack = set()
        path = []
        
        def dfs(node: str) -> bool:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if dfs(neighbor):
                        return True
                elif neighbor in rec_stack:
                    path.append(neighbor)
                    return True
            
            path.pop()
            rec_stack.remove(node)
            return False
        
        for node in graph:
            if node not in visited:
                if dfs(node):
                    # Find the cycle in path
                    cycle_start = path[-1]
                    cycle_idx = path.index(cycle_start)
                    return True, path[cycle_idx:]
        
        return False, []
    
    def create_from_json(
        self,
        procedure_json: Union[str, Dict],
        provenance: Optional[Provenance] = None,
        validate_first: bool = True,
    ) -> Dict[str, Any]:
        """
        Create a procedure DAG in KnowShowGo from LLM-generated JSON.
        
        Args:
            procedure_json: JSON string or dict from LLM
            provenance: Provenance for tracking
            validate_first: Whether to validate before creating
            
        Returns:
            Dict with procedure_uuid and step_uuids
        """
        # Parse JSON if string
        if isinstance(procedure_json, str):
            procedure_json = json.loads(procedure_json)
        
        # Validate
        if validate_first:
            validation = self.validate(procedure_json)
            if not validation.valid:
                raise ValueError(f"Invalid procedure JSON: {validation.errors}")
        
        prov = provenance or Provenance(
            source="llm",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="procedure-create"
        )

        if self._is_graph_schema(procedure_json):
            return self._create_graph_procedure(
                procedure_json=procedure_json,
                provenance=prov,
                schema_uuid=procedure_json.get("schema_uuid"),
                parent_procedure_uuid=None,
            )
        
        # Create procedure node
        proc_name = procedure_json.get("name") or "Procedure"
        proc_description = procedure_json.get("description") or proc_name
        proc_props = {
            "name": proc_name,
            "title": proc_name,
            "description": proc_description,
            "goal": procedure_json.get("goal", proc_description),
            "tags": procedure_json.get("tags", []),
            "step_count": len(procedure_json["steps"]),
            "is_dag": True,
            "created_at": prov.ts,
        }
        
        if "metadata" in procedure_json:
            proc_props["metadata"] = procedure_json["metadata"]
        
        proc_node = Node(
            kind="Procedure",
            labels=["procedure", "dag"] + procedure_json.get("tags", []),
            props=proc_props
        )
        
        # Generate embedding
        if self.embed_fn:
            embed_text = f"{proc_props['name']} {proc_props['description']}"
            proc_node.llm_embedding = self.embed_fn(embed_text)
        
        self.memory.upsert(proc_node, prov, embedding_request=True)
        
        # Create step nodes
        step_nodes: Dict[str, Node] = {}
        for idx, step in enumerate(procedure_json["steps"]):
            step_props = {
                "step_id": step["id"],
                "name": step.get("name", f"Step {idx + 1}"),
                "tool": step["tool"],
                "params": step.get("params", {}),
                "order": idx,
                "depends_on": step.get("depends_on", []),
                "guard": step.get("guard"),
                "on_fail": step.get("on_fail", "stop"),
                "retries": step.get("retries", 0),
                "procedure_uuid": proc_node.uuid,
            }
            
            step_node = Node(
                kind="Step",
                labels=["step", step["tool"].split(".")[0]],
                props=step_props
            )
            
            if self.embed_fn:
                step_text = f"{step_props['name']} {step['tool']}"
                step_node.llm_embedding = self.embed_fn(step_text)
            
            self.memory.upsert(step_node, prov, embedding_request=True)
            step_nodes[step["id"]] = step_node
            
            # Create has_step edge
            has_step_edge = Edge(
                from_node=proc_node.uuid,
                to_node=step_node.uuid,
                rel="has_step",
                props={"order": idx}
            )
            self.memory.upsert(has_step_edge, prov)
        
        # Create dependency edges
        for step in procedure_json["steps"]:
            step_node = step_nodes[step["id"]]
            for dep_id in step.get("depends_on", []):
                dep_node = step_nodes[dep_id]
                dep_edge = Edge(
                    from_node=step_node.uuid,
                    to_node=dep_node.uuid,
                    rel="depends_on",
                    props={
                        "from_step": step["id"],
                        "to_step": dep_id
                    }
                )
                self.memory.upsert(dep_edge, prov)
        
        return {
            "procedure_uuid": proc_node.uuid,
            "step_uuids": [n.uuid for n in step_nodes.values()],
            "step_ids": list(step_nodes.keys()),
            "dag_edges": sum(len(s.get("depends_on", [])) for s in procedure_json["steps"]),
        }
    
    def get_procedure(self, procedure_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a procedure and its steps from memory.
        
        Returns the procedure as JSON-like dict.
        """
        # Get procedure node
        proc_node = self.memory.get_node(procedure_uuid) if hasattr(self.memory, 'get_node') else None
        if not proc_node:
            # Try searching
            results = self.memory.search(
                procedure_uuid,
                top_k=1,
                filters={"kind": "Procedure"}
            )
            if results:
                proc_node = results[0] if isinstance(results[0], Node) else None
        
        if not proc_node:
            return None
        
        # Get steps
        if hasattr(self.memory, 'get_edges'):
            edges = self.memory.get_edges(from_node=procedure_uuid, rel="has_step")
        else:
            edges = []
        
        steps = []
        for edge in edges:
            step_uuid = edge.to_node if isinstance(edge, Edge) else edge.get("to_node")
            if hasattr(self.memory, 'get_node'):
                step_node = self.memory.get_node(step_uuid)
                if step_node:
                    steps.append({
                        "id": step_node.props.get("step_id"),
                        "name": step_node.props.get("name"),
                        "tool": step_node.props.get("tool"),
                        "params": step_node.props.get("params", {}),
                        "depends_on": step_node.props.get("depends_on", []),
                        "guard": step_node.props.get("guard"),
                        "on_fail": step_node.props.get("on_fail"),
                        "order": step_node.props.get("order", 0),
                    })
        
        # Sort by order
        steps.sort(key=lambda s: s.get("order", 0))
        
        return {
            "uuid": procedure_uuid,
            "name": proc_node.props.get("name") or proc_node.props.get("title"),
            "description": proc_node.props.get("description"),
            "goal": proc_node.props.get("goal"),
            "tags": proc_node.props.get("tags", []),
            "steps": steps,
            "metadata": proc_node.props.get("metadata", {}),
        }
    
    def search_procedures(
        self,
        query: str,
        top_k: int = 5,
        tags: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for procedures by semantic similarity.
        
        Returns list of matching procedures.
        """
        # Generate query embedding
        embedding = None
        if self.embed_fn:
            try:
                embedding = self.embed_fn(query)
            except Exception:
                pass
        
        # Search
        filters = {"kind": "Procedure"}
        if tags:
            filters["tags"] = tags
        
        results = self.memory.search(
            query,
            top_k=top_k,
            filters=filters,
            query_embedding=embedding
        )
        
        # Convert to dicts
        procedures = []
        for r in results:
            if isinstance(r, dict):
                procedures.append({
                    "uuid": r.get("uuid"),
                    "name": r.get("props", {}).get("name") or r.get("props", {}).get("title"),
                    "description": r.get("props", {}).get("description"),
                    "score": r.get("score", 0),
                })
            elif hasattr(r, "props"):
                procedures.append({
                    "uuid": r.uuid,
                    "name": r.props.get("name") or r.props.get("title"),
                    "description": r.props.get("description"),
                    "score": getattr(r, "_score", 0),
                })
        
        return procedures
    
    def to_execution_plan(self, procedure_uuid: str) -> Dict[str, Any]:
        """
        Convert a stored procedure to an execution plan for the DAG executor.
        
        Returns plan dict compatible with DAGExecutor.
        """
        procedure = self.get_procedure(procedure_uuid)
        if not procedure:
            # Fallback for graph schema: collect operation nodes by procedure_uuid
            nodes = []
            try:
                results = self.memory.search("", top_k=200, filters=None)
            except Exception:
                results = []
            for node in results:
                props = node.get("props", {}) if isinstance(node, dict) else getattr(node, "props", {})
                if props.get("procedure_uuid") != procedure_uuid:
                    continue
                if props.get("node_type") != "operation":
                    continue
                nodes.append({
                    "id": props.get("node_id"),
                    "tool": props.get("tool"),
                    "params": props.get("params", {}),
                    "depends_on": props.get("depends_on", []),
                    "order": props.get("order", 0),
                })
            nodes.sort(key=lambda n: n.get("order", 0))
            return {
                "procedure_uuid": procedure_uuid,
                "goal": "graph procedure",
                "steps": [
                    {
                        "id": step.get("id"),
                        "tool": step.get("tool"),
                        "params": step.get("params", {}),
                        "depends_on": step.get("depends_on", []),
                    }
                    for step in nodes
                ],
                "reuse": True,
            }
        
        # Convert to execution plan format
        plan_steps = []
        for step in procedure.get("steps", []):
            plan_step = {
                "id": step["id"],
                "tool": step["tool"],
                "params": step.get("params", {}),
                "depends_on": step.get("depends_on", []),
            }
            
            if step.get("guard"):
                plan_step["guard"] = step["guard"]
            if step.get("on_fail"):
                plan_step["on_fail"] = step["on_fail"]
            
            plan_steps.append(plan_step)
        
        return {
            "procedure_uuid": procedure_uuid,
            "goal": procedure.get("goal") or procedure.get("description"),
            "steps": plan_steps,
            "reuse": True,  # Mark as reused procedure
        }

    def _ensure_schema_prototype(self, provenance: Provenance) -> Optional[str]:
        # Try to find existing prototype
        nodes_attr = getattr(self.memory, "nodes", None)
        if isinstance(nodes_attr, dict):
            for node in nodes_attr.values():
                if node.kind == "Prototype" and node.props.get("name") == "ProcedureSchema":
                    return node.uuid
        try:
            results = self.memory.search("ProcedureSchema", top_k=5, filters={"kind": "Prototype"})
            for r in results:
                props = r.get("props", {}) if isinstance(r, dict) else getattr(r, "props", {})
                if props.get("name") == "ProcedureSchema":
                    return r.get("uuid") if isinstance(r, dict) else getattr(r, "uuid", None)
        except Exception:
            pass

        proto = Node(
            kind="Prototype",
            labels=["prototype", "procedure_schema"],
            props={
                "name": "ProcedureSchema",
                "description": "Schema definition for procedure graphs",
                "context": "procedure schema",
            },
        )
        if self.embed_fn:
            try:
                proto.llm_embedding = self.embed_fn("ProcedureSchema procedure graph schema")
            except Exception:
                proto.llm_embedding = None
        try:
            self.memory.upsert(proto, provenance, embedding_request=True)
        except Exception:
            return None
        return proto.uuid

    def _find_schema_concept(self, schema_hash: str, schema_version: str) -> Optional[str]:
        nodes_attr = getattr(self.memory, "nodes", None)
        if isinstance(nodes_attr, dict):
            for node in nodes_attr.values():
                if node.kind in ("Concept", "topic") and node.props.get("schema_hash") == schema_hash:
                    return node.uuid
        try:
            results = self.memory.search("ProcedureSchema", top_k=20, filters={"kind": "Concept"})
            for r in results:
                props = r.get("props", {}) if isinstance(r, dict) else getattr(r, "props", {})
                if props.get("schema_hash") == schema_hash or props.get("schema_version") == schema_version:
                    return r.get("uuid") if isinstance(r, dict) else getattr(r, "uuid", None)
        except Exception:
            pass
        return None

    def _ensure_schema_concept(
        self,
        schema: Dict[str, Any],
        schema_version: str,
        provenance: Provenance,
        schema_uuid: Optional[str] = None,
    ) -> Optional[str]:
        if schema_uuid:
            return schema_uuid
        schema_json = json.dumps(schema, sort_keys=True)
        schema_hash = hashlib.sha256(schema_json.encode("utf-8")).hexdigest()
        existing = self._find_schema_concept(schema_hash, schema_version)
        if existing:
            return existing

        proto_uuid = None
        if self.ksg and hasattr(self.ksg, "ensure_prototype"):
            try:
                proto_uuid = self.ksg.ensure_prototype(
                    name="ProcedureSchema",
                    description="Schema definition for procedure graphs",
                    context="procedure schema",
                    labels=["prototype", "procedure_schema"],
                    provenance=provenance,
                )
            except Exception:
                proto_uuid = None
        if not proto_uuid:
            proto_uuid = self._ensure_schema_prototype(provenance)

        concept_props = {
            "name": f"ProcedureSchema {schema_version}",
            "schema_version": schema_version,
            "schema_hash": schema_hash,
            "schema_source": PROCEDURE_GRAPH_SCHEMA_PATH,
            "schema_json": schema_json,
        }

        if self.ksg and proto_uuid:
            try:
                embedding = self.embed_fn(f"ProcedureSchema {schema_version}") if self.embed_fn else []
                return self.ksg.create_concept(
                    prototype_uuid=proto_uuid,
                    json_obj=concept_props,
                    embedding=embedding or [0.0, 0.0],
                    provenance=provenance,
                )
            except Exception:
                pass

        concept_node = Node(
            kind="Concept",
            labels=["ProcedureSchema", schema_version],
            props={**concept_props, "prototype_uuid": proto_uuid},
        )
        if self.embed_fn:
            try:
                concept_node.llm_embedding = self.embed_fn(f"ProcedureSchema {schema_version}")
            except Exception:
                concept_node.llm_embedding = None
        try:
            self.memory.upsert(concept_node, provenance, embedding_request=True)
        except Exception:
            return None
        if proto_uuid:
            try:
                self.memory.upsert(
                    Edge(
                        from_node=concept_node.uuid,
                        to_node=proto_uuid,
                        rel="instantiates",
                        props={"prototype_uuid": proto_uuid},
                    ),
                    provenance,
                    embedding_request=False,
                )
            except Exception:
                pass
        return concept_node.uuid

    def _resolve_procedure_uuid(self, name_or_uuid: str) -> Optional[str]:
        if not name_or_uuid:
            return None
        nodes_attr = getattr(self.memory, "nodes", None)
        if isinstance(nodes_attr, dict) and name_or_uuid in nodes_attr:
            node = nodes_attr[name_or_uuid]
            if getattr(node, "kind", None) == "Procedure":
                return node.uuid
        try:
            results = self.memory.search(name_or_uuid, top_k=5, filters={"kind": "Procedure"})
            for r in results:
                props = r.get("props", {}) if isinstance(r, dict) else getattr(r, "props", {})
                if props.get("name") == name_or_uuid or props.get("title") == name_or_uuid:
                    return r.get("uuid") if isinstance(r, dict) else getattr(r, "uuid", None)
        except Exception:
            pass
        return None

    def _create_graph_procedure(
        self,
        procedure_json: Dict[str, Any],
        provenance: Provenance,
        schema_uuid: Optional[str],
        parent_procedure_uuid: Optional[str],
    ) -> Dict[str, Any]:
        schema_version = procedure_json.get("schema_version") or PROCEDURE_GRAPH_SCHEMA_VERSION
        schema = self.get_graph_schema()
        schema_uuid = self._ensure_schema_concept(schema, schema_version, provenance, schema_uuid=schema_uuid)

        nodes = procedure_json.get("nodes") or []
        edges = procedure_json.get("edges") or []
        subprocedures = procedure_json.get("subprocedures") or []

        proc_name = procedure_json.get("name") or "Procedure"
        proc_description = procedure_json.get("description") or proc_name
        operation_count = sum(
            1
            for n in nodes
            if isinstance(n, dict) and (n.get("type") or n.get("node_type")) == "operation"
        )
        proc_props = {
            "name": proc_name,
            "title": proc_name,
            "description": proc_description,
            "goal": procedure_json.get("goal", proc_description),
            "tags": procedure_json.get("tags", []),
            "node_count": len(nodes),
            "step_count": operation_count,
            "edge_count": len(edges),
            "subprocedure_count": len(subprocedures),
            "is_graph": True,
            "schema_version": schema_version,
            "schema_uuid": schema_uuid,
            "created_at": provenance.ts,
        }
        if parent_procedure_uuid:
            proc_props["parent_procedure_uuid"] = parent_procedure_uuid
            proc_props["is_subprocedure"] = True
        if "metadata" in procedure_json:
            proc_props["metadata"] = procedure_json["metadata"]

        proc_node = Node(
            kind="Procedure",
            labels=["procedure", "graph"] + procedure_json.get("tags", []),
            props=proc_props,
        )
        if self.embed_fn:
            embed_text = f"{proc_props['name']} {proc_props['description']}"
            proc_node.llm_embedding = self.embed_fn(embed_text)
        self.memory.upsert(proc_node, provenance, embedding_request=True)

        if schema_uuid:
            try:
                self.memory.upsert(
                    Edge(
                        from_node=proc_node.uuid,
                        to_node=schema_uuid,
                        rel="conforms_to",
                        props={"schema_version": schema_version},
                    ),
                    provenance,
                    embedding_request=False,
                )
            except Exception:
                pass

        subprocedure_uuids: Dict[str, str] = {}
        for sub in subprocedures:
            try:
                sub_result = self._create_graph_procedure(
                    procedure_json=sub,
                    provenance=provenance,
                    schema_uuid=schema_uuid,
                    parent_procedure_uuid=proc_node.uuid,
                )
                sub_uuid = sub_result.get("procedure_uuid")
                if sub_uuid:
                    subprocedure_uuids[sub.get("name")] = sub_uuid
                    self.memory.upsert(
                        Edge(
                            from_node=proc_node.uuid,
                            to_node=sub_uuid,
                            rel="has_subprocedure",
                            props={"name": sub.get("name")},
                        ),
                        provenance,
                        embedding_request=False,
                    )
            except Exception:
                continue

        node_uuid_map: Dict[str, str] = {}
        for idx, node in enumerate(nodes):
            node_id = node.get("id") or f"node_{idx + 1}"
            node_type = node.get("type") or node.get("node_type") or "operation"
            target_uuid = None
            if node_type == "procedure_call":
                target_name = node.get("procedure") or node.get("procedure_ref")
                if target_name in subprocedure_uuids:
                    target_uuid = subprocedure_uuids[target_name]
                elif target_name == procedure_json.get("name"):
                    target_uuid = proc_node.uuid
                else:
                    target_uuid = self._resolve_procedure_uuid(target_name)
            node_props = {
                "node_id": node_id,
                "node_type": node_type,
                "name": node.get("name") or node_id,
                "description": node.get("description"),
                "procedure_uuid": proc_node.uuid,
                "order": node.get("order", idx),
                "tool": node.get("tool"),
                "params": node.get("params", {}),
                "condition": node.get("condition"),
                "body": node.get("body"),
                "max_iterations": node.get("max_iterations"),
                "depends_on": node.get("depends_on", []),
                "procedure": node.get("procedure") or node.get("procedure_ref"),
                "procedure_uuid": target_uuid,
                "metadata": node.get("metadata", {}),
            }

            node_labels = ["procedure_node", node_type]
            node_obj = Node(kind="ProcedureNode", labels=node_labels, props=node_props)
            if self.embed_fn:
                try:
                    node_obj.llm_embedding = self.embed_fn(f"{node_props.get('name')} {node_type} {node_props.get('tool')}")
                except Exception:
                    node_obj.llm_embedding = None
            self.memory.upsert(node_obj, provenance, embedding_request=True)
            node_uuid_map[node_id] = node_obj.uuid

            # Link procedure -> node
            self.memory.upsert(
                Edge(
                    from_node=proc_node.uuid,
                    to_node=node_obj.uuid,
                    rel="has_node",
                    props={"order": node_props.get("order", idx), "node_type": node_type},
                ),
                provenance,
                embedding_request=False,
            )

            # For operation nodes, also store has_step for compatibility
            if node_type == "operation":
                self.memory.upsert(
                    Edge(
                        from_node=proc_node.uuid,
                        to_node=node_obj.uuid,
                        rel="has_step",
                        props={"order": node_props.get("order", idx)},
                    ),
                    provenance,
                    embedding_request=False,
                )

            # Link procedure_call nodes to their targets
            if node_type == "procedure_call":
                if target_uuid:
                    try:
                        self.memory.upsert(
                            Edge(
                                from_node=node_obj.uuid,
                                to_node=target_uuid,
                                rel="calls_procedure",
                                props={"name": node.get("procedure") or node.get("procedure_ref")},
                            ),
                            provenance,
                            embedding_request=False,
                        )
                    except Exception:
                        pass

        for edge in edges:
            if not isinstance(edge, dict):
                continue
            from_id = edge.get("from")
            to_id = edge.get("to")
            rel = edge.get("rel") or "depends_on"
            if from_id not in node_uuid_map or to_id not in node_uuid_map:
                continue
            edge_props = edge.get("metadata", {})
            self.memory.upsert(
                Edge(
                    from_node=node_uuid_map[from_id],
                    to_node=node_uuid_map[to_id],
                    rel=rel,
                    props=edge_props,
                ),
                provenance,
                embedding_request=False,
            )

        return {
            "procedure_uuid": proc_node.uuid,
            "node_uuids": list(node_uuid_map.values()),
            "node_ids": list(node_uuid_map.keys()),
            "subprocedure_uuids": list(subprocedure_uuids.values()),
            "schema_uuid": schema_uuid,
        }


def create_procedure_manager(
    memory: MemoryTools,
    embed_fn: Optional[EmbedFn] = None,
) -> ProcedureManager:
    """Factory function to create a ProcedureManager."""
    return ProcedureManager(memory=memory, embed_fn=embed_fn)
