import json
import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockWebTools, MockContactsTools
from src.personal_assistant.openai_client import FakeOpenAIClient


class TestAgentWebDom(unittest.TestCase):
    def test_executes_dom_fetch_and_xpath_click(self):
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        tasks.create(
            title="Existing Task",
            due=None,
            priority=3,
            notes="",
            links=[],
        )
        calendar.create_event(
            title="Existing Event",
            start="2025-01-01T10:00:00Z",
            end="2025-01-01T11:00:00Z",
            attendees=[],
            location="Virtual",
            notes="",
        )
        web = MockWebTools()
        contacts = MockContactsTools()
        contacts.create(
            name="Jane Example",
            emails=["jane@example.com"],
            phones=[],
            org="ExampleCo",
            notes="",
            tags=[],
        )
        fake_plan = """
        {
          "intent": "web_io",
          "steps": [
            {"tool": "web.get_dom", "params": {"url": "https://example.com"}},
            {"tool": "web.locate_bounding_box", "params": {"url": "https://example.com", "query": "password input"}},
            {"tool": "web.click_xpath", "params": {"url": "https://example.com", "xpath": "//button[@id='ok']"}}
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.0, 0.0, 1.0])
        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=contacts,
            openai_client=openai_client,
        )

        result = agent.execute_request("Inspect the login page and click submit")

        # Plan executed with web steps
        self.assertEqual(result["plan"]["intent"], "web_io")
        self.assertEqual(result["execution_results"]["status"], "completed")
        self.assertEqual(len(web.history), 3)
        self.assertEqual(web.history[0]["method"], "GET_DOM")
        self.assertEqual(web.history[1]["method"], "LOCATE_BBOX")
        self.assertEqual(web.history[2]["method"], "CLICK_XPATH")

        # RAG context was passed into the prompt
        self.assertIsNotNone(openai_client.last_messages)
        serialized_messages = " ".join(m["content"] for m in openai_client.last_messages)
        self.assertIn("Tasks context", serialized_messages)
        self.assertIn("Calendar context", serialized_messages)


if __name__ == "__main__":
    unittest.main()
