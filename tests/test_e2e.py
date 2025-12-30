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
from src.personal_assistant.events import EventBus


class EventCollector(EventBus):
    def __init__(self):
        super().__init__()
        self.events = []

    async def emit(self, event_type, payload):
        self.events.append({"type": event_type, "payload": payload})
        await super().emit(event_type, payload)


class TestEndToEndAgent(unittest.TestCase):
    def test_full_agent_flow_with_multiple_tools_and_events(self):
        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "end-to-end task",
                "due": "2025-12-31",
                "priority": 2,
                "notes": "E2E flow",
                "links": []
              }
            },
            {
              "tool": "contacts.create",
              "params": {
                "name": "E2E User",
                "emails": ["e2e@example.com"],
                "phones": ["+1-333-333-3333"],
                "org": "E2E Org",
                "notes": "contact created in e2e",
                "tags": ["test"]
              }
            },
            {
              "tool": "calendar.create_event",
              "params": {
                "title": "E2E Meeting",
                "start": "2026-01-01T10:00:00Z",
                "end": "2026-01-01T11:00:00Z",
                "attendees": ["e2e@example.com"],
                "location": "Virtual",
                "notes": "E2E calendar event"
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.8, 0.1, 0.1])
        bus = EventCollector()

        memory = MockMemoryTools()
        calendar = MockCalendarTools()
        tasks = MockTaskTools()
        web = MockWebTools()
        contacts = MockContactsTools()

        agent = PersonalAssistantAgent(
            memory=memory,
            calendar=calendar,
            tasks=tasks,
            web=web,
            contacts=contacts,
            openai_client=openai_client,
            event_bus=bus,
        )

        result = agent.execute_request("run end-to-end scenario")

        self.assertEqual(result["execution_results"]["status"], "completed")
        self.assertEqual(result["plan"]["intent"], "task")

        # Task created and embedded
        self.assertEqual(len(tasks.tasks), 1)
        self.assertEqual(tasks.tasks[0]["title"], "end-to-end task")
        task_nodes = [n for n in memory.nodes.values() if n.kind == "Task"]
        self.assertEqual(len(task_nodes), 1)
        self.assertEqual(task_nodes[0].llm_embedding, [0.8, 0.1, 0.1])

        # Contact created and embedded
        self.assertEqual(len(contacts.contacts), 1)
        contact_nodes = [n for n in memory.nodes.values() if n.kind == "Person"]
        self.assertEqual(len(contact_nodes), 1)

        # Calendar event created and embedded
        self.assertEqual(len(calendar.events), 1)
        event_nodes = [n for n in memory.nodes.values() if n.kind == "Event"]
        self.assertEqual(len(event_nodes), 1)

        # Queue updated and memory upserts emitted
        types = [e["type"] for e in bus.events]
        for expected in [
            "request_received",
            "plan_ready",
            "execution_completed",
            "tool_invoked",
            "memory_upsert",
            "queue_updated",
            "calendar_event_created",
            "message_logged",
            "rag_query",
        ]:
            self.assertIn(expected, types)


if __name__ == "__main__":
    unittest.main()
