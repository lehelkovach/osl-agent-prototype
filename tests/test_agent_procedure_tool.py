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
                "title": "LinkedIn check",
                "description": "Check messages and create follow-ups",
                "steps": [
                  {"title": "Open LinkedIn"},
                  {"title": "Open messages"},
                  {"title": "Create follow-up task"}
                ],
                "dependencies": [[0,1],[1,2]],
                "guards": {"2": "only if recruiter messages"}
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
        proc_nodes = [n for n in memory.nodes.values() if n.kind == "Procedure"]
        step_nodes = [n for n in memory.nodes.values() if n.kind == "Step"]
        self.assertEqual(len(proc_nodes), 1)
        self.assertEqual(len(step_nodes), 3)
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
