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


class TestAgentFallback(unittest.TestCase):
    def test_fallback_plan_creates_task_on_bad_llm_output(self):
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        contacts = MockContactsTools()

        # Invalid JSON response triggers fallback
        fake_plan = "not-json"
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.0, 0.0, 0.0])
        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=contacts,
            openai_client=openai_client,
        )

        result = agent.execute_request("remind me to test fallback")

        self.assertEqual(result["execution_results"]["status"], "completed")
        self.assertEqual(len(tasks.tasks), 1)
        self.assertTrue(result["plan"].get("fallback"))
        self.assertEqual(tasks.tasks[0]["title"], "remind me to test fallback")


if __name__ == "__main__":
    unittest.main()
