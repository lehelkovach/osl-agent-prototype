# Procedure Graph Schema (KSG)

This project supports a **graph-based procedure schema** that models control-flow
in KnowShowGo as explicit nodes and edges. The schema is **hosted in-repo** at:

```
config/procedure_graph_schema.json
```

When a graph procedure is created, the schema is **stored in KnowShowGo** as a
`ProcedureSchema` concept. The resulting `schema_uuid` is saved on the procedure
node and linked via a `conforms_to` edge so the schema can be referenced later.

## Schema version

- Current version: `ksg-procedure-0.2`
- The schema concept stores:
  - `schema_version`
  - `schema_hash`
  - `schema_source` (path to the schema file)
  - `schema_json` (stringified JSON Schema)

## Graph shape

Top-level fields:

- `name`, `description`, `goal`, `tags`
- `nodes`: list of node objects (operations, conditionals, loops, procedure calls)
- `edges`: list of control-flow edges (e.g., `depends_on`, `branch_true`, `loop_back`)
- `subprocedures`: list of nested procedures (each with its own `nodes`/`edges`)
- `schema_version` (optional; default `ksg-procedure-0.2`)

Node types:

- `operation` (tool invocation)
- `procedure_call` (call a subprocedure)
- `conditional` (branching based on `condition`)
- `loop` (iteration based on `condition`, `body`, `max_iterations`)
- `return` / `noop`

## Example

```json
{
  "schema_version": "ksg-procedure-0.2",
  "name": "Login Flow",
  "description": "Login with retry",
  "nodes": [
    {"id": "get_dom", "type": "operation", "tool": "web.get_dom", "params": {"url": "https://example.com/login"}},
    {"id": "check_login", "type": "conditional", "condition": "page_has_login_form"},
    {"id": "call_login", "type": "procedure_call", "procedure": "LoginSub"},
    {"id": "retry_loop", "type": "loop", "condition": "not_logged_in", "body": ["get_dom", "call_login"], "max_iterations": 2}
  ],
  "edges": [
    {"from": "get_dom", "to": "check_login", "rel": "depends_on"},
    {"from": "check_login", "to": "call_login", "rel": "branch_true"},
    {"from": "retry_loop", "to": "get_dom", "rel": "loop_back"}
  ],
  "subprocedures": [
    {
      "name": "LoginSub",
      "description": "Subprocedure for login",
      "nodes": [
        {"id": "fill_login", "type": "operation", "tool": "form.autofill", "params": {"url": "https://example.com/login", "form_type": "login"}}
      ],
      "edges": []
    }
  ]
}
```

## Graph storage in KnowShowGo

When a graph procedure is stored:

- A `Procedure` node represents the master procedure.
- Each `node` becomes a `ProcedureNode` concept.
- `has_node` edges link the procedure to its nodes.
- For `operation` nodes, a `has_step` edge is also created for compatibility.
- Control-flow edges are persisted using the `rel` field (e.g., `depends_on`, `branch_true`).
- `subprocedures` are stored as separate `Procedure` nodes and linked with `has_subprocedure`.
- `procedure_call` nodes link to subprocedures via `calls_procedure`.

This provides a full graph representation that can later be traversed by a runtime
capable of control-flow execution (loops, recursion, branches).
