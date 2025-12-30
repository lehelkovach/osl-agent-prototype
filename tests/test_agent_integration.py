import unittest
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockWebTools, MockContactsTools
from src.personal_assistant.openai_client import FakeOpenAIClient

class TestAgentIntegration(unittest.TestCase):

    def test_create_task_workflow(self):
        """
        Tests the full agent workflow for a 'remind me to' request.
        """
        # Setup
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        contacts = MockContactsTools()
        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "test the agent",
                "due": null,
                "priority": 1,
                "notes": "Created from user request",
                "links": []
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.1, 0.2, 0.3])
        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=contacts,
            openai_client=openai_client,
        )

        # Execution
        user_request = "remind me to test the agent"
        result = agent.execute_request(user_request)

        # Verification
        # 1. Check that a task was created
        self.assertEqual(len(tasks.tasks), 1)
        self.assertEqual(tasks.tasks[0]['title'], "test the agent")

        # 2. Check that a node representing the task was stored in memory
        task_nodes = [n for n in memory.nodes.values() if n.kind == "Task"]
        self.assertEqual(len(task_nodes), 1)
        task_node = task_nodes[0]
        self.assertEqual(task_node.props['title'], "test the agent")
        self.assertEqual(task_node.llm_embedding, [0.1, 0.2, 0.3])
        
        # 3. Check the returned results
        self.assertEqual(result['plan']['intent'], 'task')
        self.assertEqual(result['execution_results']['status'], 'completed')

    def test_openai_json_plan_parsed_and_used(self):
        """Ensure a valid JSON response from OpenAI is parsed and executed (no fallback)."""
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "parse plan success",
                "due": null,
                "priority": 2,
                "notes": "LLM provided JSON plan",
                "links": []
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.2, 0.3, 0.5])
        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=MockContactsTools(),
            openai_client=openai_client,
        )

        result = agent.execute_request("remind me to parse plan success")

        self.assertFalse(result["plan"].get("fallback"))
        self.assertEqual(result["execution_results"]["status"], "completed")
        self.assertEqual(len(tasks.tasks), 1)
        self.assertEqual(tasks.tasks[0]["title"], "parse plan success")
        task_nodes = [n for n in memory.nodes.values() if n.kind == "Task"]
        self.assertEqual(len(task_nodes), 1)
        self.assertEqual(task_nodes[0].llm_embedding, [0.2, 0.3, 0.5])
        # History messages (user + assistant) captured with embeddings
        history = [n for n in memory.nodes.values() if n.kind == "Message"]
        self.assertEqual(len(history), 2)
        for msg in history:
            self.assertEqual(msg.llm_embedding, [0.2, 0.3, 0.5])

    def test_openai_json_plan_parsed_and_used(self):
        """Ensure a valid JSON response from OpenAI is parsed and executed (no fallback)."""
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "parse plan success",
                "due": null,
                "priority": 2,
                "notes": "LLM provided JSON plan",
                "links": []
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.2, 0.3, 0.5])
        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=MockContactsTools(),
            openai_client=openai_client,
        )

        result = agent.execute_request("remind me to parse plan success")

        self.assertFalse(result["plan"].get("fallback"))
        self.assertEqual(result["execution_results"]["status"], "completed")
        self.assertEqual(len(tasks.tasks), 1)
        self.assertEqual(tasks.tasks[0]["title"], "parse plan success")
        task_nodes = [n for n in memory.nodes.values() if n.kind == "Task"]
        self.assertEqual(len(task_nodes), 1)
        self.assertEqual(task_nodes[0].llm_embedding, [0.2, 0.3, 0.5])

if __name__ == '__main__':
    unittest.main()
