import json
import unittest

from fastapi.testclient import TestClient

from src.personal_assistant.service import build_app, default_agent_from_env
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.openai_client import FakeOpenAIClient


class TestServiceUISmoke(unittest.TestCase):
    def test_ui_endpoints(self):
        memory = MockMemoryTools()
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}', embedding=[0.1, 0.2]),
        )
        app = build_app(agent)
        client = TestClient(app)

        # health
        resp = client.get("/health")
        self.assertEqual(resp.status_code, 200)
        # ui html
        resp = client.get("/ui")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<html>", resp.text)

        # chat
        resp = client.post("/chat", json={"message": "hello"})
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("plan", body)
        self.assertIn("events", body)

        # history/logs/runs
        self.assertEqual(client.get("/history").status_code, 200)
        self.assertEqual(client.get("/logs").status_code, 200)
        runs = client.get("/runs")
        self.assertEqual(runs.status_code, 200)
        # if a run exists, can fetch it
        data = runs.json()
        if data:
            run_detail = client.get(f"/runs/{data[0]['trace_id']}")
            self.assertEqual(run_detail.status_code, 200)


if __name__ == "__main__":
    unittest.main()
