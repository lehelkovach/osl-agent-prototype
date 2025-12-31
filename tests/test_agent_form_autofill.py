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
from src.personal_assistant.form_filler import FormDataRetriever


class TestAgentFormAutofill(unittest.TestCase):
    def test_remember_formdata_and_autofill(self):
        memory = MockMemoryTools()
        plan = """
        {
          "intent": "inform",
          "steps": [
            {
              "tool": "memory.remember",
              "params": {
                "text": "My name is Ada Lovelace and my address is 123 Code St London SW1A UK",
                "kind": "FormData",
                "props": {
                  "givenName": "Ada",
                  "familyName": "Lovelace",
                  "address": "123 Code St",
                  "city": "London",
                  "postalCode": "SW1A",
                  "country": "UK"
                }
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
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.3, 0.2]),
        )

        agent.execute_request("remember my address")
        retriever = FormDataRetriever(memory)
        required = ["givenName", "familyName", "address", "city", "postalCode", "country"]
        fill = retriever.build_autofill(required_fields=required)
        for f in required:
            self.assertIn(f, fill)
        self.assertEqual(fill["givenName"], "Ada")
        # ensure embedding was set on stored node
        form_nodes = [n for n in memory.nodes.values() if n.kind == "FormData"]
        self.assertEqual(len(form_nodes), 1)
        self.assertIsNotNone(form_nodes[0].llm_embedding)


if __name__ == "__main__":
    unittest.main()
