import unittest

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.events import EventBus
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.openai_client import FakeOpenAIClient


class TestAgentEvents(unittest.TestCase):
    def test_events_emitted_through_lifecycle(self):
        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        contacts = MockContactsTools()
        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "event test",
                "due": null,
                "priority": 1,
                "notes": "Event bus coverage",
                "links": []
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.4, 0.5, 0.6])

        events = []

        async def listener(event):
            events.append(event)

        bus = EventBus()
        bus.on("*", listener)

        agent = PersonalAssistantAgent(
            memory,
            calendar,
            tasks,
            web=web,
            contacts=contacts,
            openai_client=openai_client,
            event_bus=bus,
        )

        result = agent.execute_request("remind me to cover events")

        self.assertEqual(result["execution_results"]["status"], "completed")
        # Events captured for request, plan, execution
        event_types = [e.type for e in events]
        self.assertIn("request_received", event_types)
        self.assertIn("plan_ready", event_types)
        self.assertIn("execution_completed", event_types)

        # History captured with embeddings
        history = [n for n in memory.nodes.values() if n.kind == "Message"]
        self.assertEqual(len(history), 2)
        for h in history:
            self.assertEqual(h.llm_embedding, [0.4, 0.5, 0.6])


if __name__ == "__main__":
    unittest.main()
