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


class TestServiceRuns(unittest.TestCase):
    def test_runs_capture_trace(self):
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

        resp = client.post("/chat", json={"message": "hello"})
        self.assertEqual(resp.status_code, 200)

        runs = client.get("/runs").json()
        self.assertGreaterEqual(len(runs), 1)
        trace_id = runs[0]["trace_id"]
        detail = client.get(f"/runs/{trace_id}").json()
        self.assertEqual(detail.get("plan", {}).get("trace_id"), trace_id)
        self.assertEqual(detail.get("results", {}).get("trace_id"), trace_id)


if __name__ == "__main__":
    unittest.main()
