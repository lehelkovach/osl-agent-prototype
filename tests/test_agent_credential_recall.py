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


class TestAgentCredentialRecall(unittest.TestCase):
    def test_remember_and_recall_linkedin_credentials(self):
        memory = MockMemoryTools()
        # Step 1: remember credentials
        remember_plan = """
        {
          "intent": "remember",
          "steps": [
            {
              "tool": "memory.remember",
              "params": {
                "text": "linkedin.com credentials",
                "kind": "Credential",
                "props": {
                  "appName": "LinkedIn",
                  "url": "https://linkedin.com",
                  "username": "ada",
                  "password": "hunter2"
                }
              }
            }
          ]
        }
        """
        remember_agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response=remember_plan, embedding=[0.9, 0.1, 0.0]),
        )
        remember_agent.execute_request("remember my linkedin login")

        # Verify stored credential node with embedding
        cred_nodes = [n for n in memory.nodes.values() if n.kind == "Credential"]
        self.assertEqual(len(cred_nodes), 1)
        self.assertEqual(cred_nodes[0].props["appName"], "LinkedIn")
        self.assertIsNotNone(cred_nodes[0].llm_embedding)

        # Step 2: new agent reuses memory and queries
        query_agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}', embedding=[0.9, 0.1, 0.0]),
        )
        results = query_agent.memory.search("linkedin credentials", top_k=5, query_embedding=[0.9, 0.1, 0.0])
        self.assertGreaterEqual(len(results), 1)
        cred = next((r for r in results if r.get("kind") == "Credential"), None)
        self.assertIsNotNone(cred)
        self.assertEqual(cred["props"]["username"], "ada")
        self.assertEqual(cred["props"]["url"], "https://linkedin.com")


if __name__ == "__main__":
    unittest.main()
