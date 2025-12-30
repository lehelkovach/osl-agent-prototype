import unittest

from datetime import datetime, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient


class TestAgentContacts(unittest.TestCase):
    def test_create_contact_and_embed(self):
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        contacts = MockContactsTools()
        fake_plan = """
        {
          "intent": "remember",
          "steps": [
            {
              "tool": "contacts.create",
              "params": {
                "name": "Grace Hopper",
                "emails": ["grace@navy.mil"],
                "phones": ["+1-222-222-2222"],
                "org": "US Navy",
                "notes": "COBOL pioneer",
                "tags": ["vip"]
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.9, 0.1, 0.0])
        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=contacts,
            openai_client=openai_client,
        )

        result = agent.execute_request("Remember Grace Hopper's contact info")

        self.assertEqual(result["execution_results"]["status"], "completed")
        self.assertEqual(len(contacts.contacts), 1)
        contact = contacts.contacts[0]
        self.assertEqual(contact["name"], "Grace Hopper")
        nodes = [n for n in memory.nodes.values() if n.kind == "Person"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0].llm_embedding, [0.9, 0.1, 0.0])


if __name__ == "__main__":
    unittest.main()
