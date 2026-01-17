import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.procedure_builder import ProcedureBuilder


class TestAgentProcedureTool(unittest.TestCase):
    def test_procedure_create_tool_builds_steps(self):
        memory = MockMemoryTools()
        builder = ProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.2])
        plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "procedure.create",
              "params": {
                "name": "LinkedIn check",
                "description": "Check messages and create follow-ups",
                "steps": [
                  {"id": "step_1", "name": "Open LinkedIn", "tool": "web.get", "params": {"url": "https://www.linkedin.com"}, "depends_on": []},
                  {"id": "step_2", "name": "Open messages", "tool": "web.get_dom", "params": {"url": "https://www.linkedin.com/messaging"}, "depends_on": ["step_1"]},
                  {"id": "step_3", "name": "Create follow-up task", "tool": "tasks.create", "params": {"title": "Follow up on recruiter messages", "priority": 3, "due": null, "notes": "", "links": []}, "depends_on": ["step_2"]}
                ],
                "tags": ["web", "linkedin"]
              }
            }
          ]
        }
        """
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=builder,
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.3, 0.1]),
        )

        result = agent.execute_request("create linkedin procedure")
        self.assertEqual(result["execution_results"]["status"], "completed")
        # Canonical persistence: ProcedureManager DAG (Procedure + Step nodes + has_step/depends_on edges)
        create_step = result["execution_results"]["steps"][0]
        proc_uuid = create_step.get("procedure", {}).get("procedure_uuid")
        self.assertIsNotNone(proc_uuid)
        proc_node = memory.nodes.get(proc_uuid)
        self.assertIsNotNone(proc_node)
        self.assertEqual(getattr(proc_node, "kind", None), "Procedure")
        self.assertIn("LinkedIn check", (proc_node.props or {}).get("title", "") or (proc_node.props or {}).get("name", ""))

        has_step_edges = [e for e in memory.edges.values() if e.rel == "has_step" and e.from_node == proc_uuid]
        self.assertGreaterEqual(len(has_step_edges), 3)
        self.assertTrue(any(e.rel == "depends_on" for e in memory.edges.values()))

    def test_procedure_search_tool(self):
        memory = MockMemoryTools()
        builder = ProcedureBuilder(memory, embed_fn=lambda text: [float(len(text)), 0.2])
        # Seed a procedure
        builder.create_procedure(
            title="LinkedIn check",
            description="Check messages and create follow-ups",
            steps=[{"title": "Open LinkedIn"}],
        )
        plan = """
        {
          "intent": "inform",
          "steps": [
            {
              "tool": "procedure.search",
              "params": {"query": "LinkedIn", "top_k": 1}
            }
          ]
        }
        """
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            procedure_builder=builder,
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.4, 0.2]),
        )
        result = agent.execute_request("find linkedin procedure")
        self.assertEqual(result["execution_results"]["status"], "completed")
        step_res = result["execution_results"]["steps"][0]
        self.assertIn("procedures", step_res)
        self.assertGreaterEqual(len(step_res["procedures"]), 1)


if __name__ == "__main__":
    unittest.main()
