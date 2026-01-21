import unittest

from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.procedure_manager import ProcedureManager


class TestProcedureGraphSchema(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemoryTools()
        self.manager = ProcedureManager(memory=self.memory, embed_fn=lambda text: [0.1, 0.2])

    def test_graph_schema_exposed(self):
        schema = self.manager.get_graph_schema()
        self.assertEqual(schema.get("type"), "object")
        self.assertIn("nodes", schema.get("properties", {}))
        self.assertIn("edges", schema.get("properties", {}))

    def test_graph_procedure_creates_nodes_edges_and_schema_token(self):
        proc = {
            "schema_version": "ksg-procedure-0.2",
            "name": "Main Flow",
            "description": "Graph procedure with control flow",
            "nodes": [
                {
                    "id": "get_dom",
                    "type": "operation",
                    "tool": "web.get_dom",
                    "params": {"url": "https://example.com/login"},
                },
                {
                    "id": "check_login",
                    "type": "conditional",
                    "condition": "page_has_login_form",
                },
                {
                    "id": "call_login",
                    "type": "procedure_call",
                    "procedure": "LoginSub",
                },
                {
                    "id": "retry_loop",
                    "type": "loop",
                    "condition": "not_logged_in",
                    "body": ["get_dom", "call_login"],
                    "max_iterations": 2,
                },
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

        result = self.manager.create_from_json(proc)
        proc_uuid = result.get("procedure_uuid")
        self.assertIsNotNone(proc_uuid)

        proc_node = self.memory.nodes.get(proc_uuid)
        self.assertIsNotNone(proc_node)
        schema_uuid = proc_node.props.get("schema_uuid")
        self.assertIsNotNone(schema_uuid)

        schema_node = self.memory.nodes.get(schema_uuid)
        self.assertIsNotNone(schema_node)
        self.assertEqual(schema_node.props.get("schema_version"), "ksg-procedure-0.2")

        rels = [e.rel for e in self.memory.edges.values()]
        self.assertIn("has_subprocedure", rels)
        self.assertIn("calls_procedure", rels)
        self.assertIn("has_node", rels)
        self.assertIn("has_step", rels)
        self.assertIn("branch_true", rels)
        self.assertIn("loop_back", rels)
        self.assertIn("conforms_to", rels)


if __name__ == "__main__":
    unittest.main()
