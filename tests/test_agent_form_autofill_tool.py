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
from src.personal_assistant.models import Node, Provenance


class TestAgentFormAutofillTool(unittest.TestCase):
    def test_autofill_uses_memory_formdata(self):
        memory = MockMemoryTools()
        prov = Provenance("user", "2024-01-01T00:00:00Z", 1.0, "trace")
        form_node = Node(
            kind="FormData",
            labels=["vault"],
            props={"username": "ada", "password": "hunter2", "givenName": "Ada"},
        )
        memory.upsert(form_node, prov)

        plan = """
        {
          "intent": "inform",
          "steps": [
            {
              "tool": "form.autofill",
              "params": {
                "url": "https://example.com/form",
                "selectors": {
                  "username": "#user",
                  "password": "#pass"
                },
                "required_fields": ["username", "password"]
              }
            }
          ]
        }
        """
        web = MockWebTools()
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=web,
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.2, 0.1]),
        )
        res = agent.execute_request("fill form")
        self.assertEqual(res["execution_results"]["status"], "completed")
        # Ensure web.fill was called with the values from memory
        fills = [h for h in web.history if h.get("method") == "FILL"]
        self.assertEqual(len(fills), 2)
        values = {f["selector"]: f["text"] for f in fills}
        self.assertEqual(values["#user"], "ada")
        self.assertEqual(values["#pass"], "hunter2")
        filled_fields = res["execution_results"]["steps"][0]["filled"]
        self.assertEqual({f["field"] for f in filled_fields}, {"username", "password"})

    def test_autofill_without_web_returns_error(self):
        memory = MockMemoryTools()
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=None,
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[{"tool":"form.autofill","params":{"selectors":{},"url":"x"}}]}', embedding=[0.1, 0.1]),
        )
        res = agent.execute_request("fill form")
        self.assertEqual(res["execution_results"]["steps"][0]["status"], "error")

    def test_autofill_missing_fields_prompts_user(self):
        memory = MockMemoryTools()
        plan = """
        {
          "intent": "inform",
          "steps": [
            {
              "tool": "form.autofill",
              "params": {
                "url": "https://example.com/login",
                "selectors": {
                  "username": "#user",
                  "password": "#pass"
                },
                "required_fields": ["username", "password"],
                "form_type": "login"
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
            openai_client=FakeOpenAIClient(chat_response=plan, embedding=[0.2, 0.1]),
        )

        res = agent.execute_request("fill login form")
        step = res["execution_results"]["steps"][0]
        self.assertEqual(step["status"], "ask_user")
        self.assertIn("username", step.get("prompt", "").lower())
        self.assertIn("password", step.get("prompt", "").lower())


if __name__ == "__main__":
    unittest.main()
