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


class TestAgentHTTPService(unittest.TestCase):
    def test_service_lifecycle_and_events(self):
        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "http task",
                "due": null,
                "priority": 1,
                "notes": "from http",
                "links": []
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.7, 0.1, 0.2])
        agent = PersonalAssistantAgent(
            memory=MockMemoryTools(),
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=openai_client,
        )
        app = build_app(agent)
        client = TestClient(app)

        # Service health
        res = client.get("/health")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "ok")

        # Post a chat message
        res = client.post("/chat", json={"message": "remind me via http"})
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["results"]["status"], "completed")
        self.assertEqual(data["plan"]["intent"], "task")
        events = data["events"]
        types = [e["type"] for e in events]
        # Ensure lifecycle events and tool invocation present
        for expected in ["request_received", "plan_ready", "tool_invoked", "execution_completed", "message_logged"]:
            self.assertIn(expected, types)
        # Verify tool invocation payload
        tool_event = next(e for e in events if e["type"] == "tool_invoked")
        self.assertEqual(tool_event["payload"]["tool"], "tasks.create")

        # History/logs endpoints
        res_hist = client.get("/history")
        res_logs = client.get("/logs")
        self.assertEqual(res_hist.status_code, 200)
        self.assertGreaterEqual(len(res_hist.json()), 2)
        self.assertEqual(res_logs.status_code, 200)


if __name__ == "__main__":
    unittest.main()
