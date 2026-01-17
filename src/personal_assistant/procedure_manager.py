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
    
    def get_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for procedure generation."""
        return PROCEDURE_JSON_SCHEMA
    
    def get_example(self) -> Dict[str, Any]:
        """Get an example procedure JSON."""
        return PROCEDURE_JSON_EXAMPLE
    
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
        
        # Create procedure node
        proc_props = {
            "name": procedure_json["name"],
            "title": procedure_json["name"],
            "description": procedure_json["description"],
            "goal": procedure_json.get("goal", procedure_json["description"]),
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
            raise ValueError(f"Procedure {procedure_uuid} not found")
        
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


def create_procedure_manager(
    memory: MemoryTools,
    embed_fn: Optional[EmbedFn] = None,
) -> ProcedureManager:
    """Factory function to create a ProcedureManager."""
    return ProcedureManager(memory=memory, embed_fn=embed_fn)
