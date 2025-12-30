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

if __name__ == '__main__':
    unittest.main()
