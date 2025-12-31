import unittest

from fastapi.testclient import TestClient

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.service import build_app


class TestServiceUIChatFlow(unittest.TestCase):
    def test_chat_round_trip_updates_history_and_logs(self):
        memory = MockMemoryTools()
        # Fake plan with no steps to keep simple
        fake_plan = '{"intent":"inform","steps":[]}'
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response=fake_plan, embedding=[0.1, 0.2]),
        )
        client = TestClient(build_app(agent))

        # Initial history/logs empty
        assert client.get("/history").json() == []
        assert client.get("/logs").json() == []

        resp = client.post("/chat", json={"message": "hello"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("plan", body)

        history = client.get("/history").json()
        self.assertGreaterEqual(len(history), 2)
        # Last assistant message should contain the plan string
        self.assertEqual(history[-2]["role"], "user")
        self.assertEqual(history[-2]["content"], "hello")
        self.assertEqual(history[-1]["role"], "assistant")
        self.assertTrue(history[-1]["content"])
        self.assertIn("Hello", history[-1]["content"])

        logs = client.get("/logs").json()
        self.assertIsInstance(logs, list)
        # At least one tool_invoked or rag_query should be present
        self.assertTrue(any(isinstance(entry, dict) for entry in logs))

        runs = client.get("/runs").json()
        self.assertGreaterEqual(len(runs), 1)


if __name__ == "__main__":
    unittest.main()
