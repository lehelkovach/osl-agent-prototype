import os
import unittest
from unittest import mock

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient


class TestAgentLocalEmbedding(unittest.TestCase):
    def test_task_embedding_with_local_backend(self):
        with mock.patch.dict(os.environ, {"EMBEDDING_BACKEND": "local", "USE_FAKE_OPENAI": "1"}):
            memory = MockMemoryTools()
            plan = """
            {
              "intent": "task",
              "steps": [
                {
                  "tool": "tasks.create",
                  "params": {
                    "title": "local embed task",
                    "due": null,
                    "priority": 1,
                    "notes": "test",
                    "links": []
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
                openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.1, 0.2]),
            )
            agent.execute_request("create task")
            task_nodes = [n for n in memory.nodes.values() if n.kind == "Task"]
            self.assertEqual(len(task_nodes), 1)
            self.assertIsNotNone(task_nodes[0].llm_embedding)
            self.assertGreater(len(task_nodes[0].llm_embedding), 0)


if __name__ == "__main__":
    unittest.main()
