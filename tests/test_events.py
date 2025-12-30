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
            },
            {
              "tool": "calendar.create_event",
              "params": {
                "title": "Event Bus Meeting",
                "start": "2025-01-01T10:00:00Z",
                "end": "2025-01-01T11:00:00Z",
                "attendees": [],
                "location": "Virtual",
                "notes": "Event bus calendar create"
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
        self.assertIn("message_logged", event_types)
        self.assertIn("tool_invoked", event_types)
        self.assertIn("memory_upsert", event_types)
        self.assertIn("rag_query", event_types)
        self.assertIn("queue_updated", event_types)
        self.assertIn("calendar_event_created", event_types)

        # History captured with embeddings
        history = [n for n in memory.nodes.values() if n.kind == "Message"]
        self.assertEqual(len(history), 2)
        for h in history:
            self.assertEqual(h.llm_embedding, [0.4, 0.5, 0.6])

        # Raw LLM text present in plan_ready payload
        plan_event = next(e for e in events if e.type == "plan_ready")
        self.assertIn("raw_llm", plan_event.payload)
        self.assertIn("event test", plan_event.payload["raw_llm"])

        # Tool invocation payload contains tool and params
        tool_event = next(e for e in events if e.type == "tool_invoked")
        self.assertEqual(tool_event.payload["tool"], "tasks.create")
        self.assertIn("params", tool_event.payload)

        # Memory upsert happened for task node
        mem_event = next(e for e in events if e.type == "memory_upsert")
        self.assertEqual(mem_event.payload["kind"], "Task")

        # RAG query event captured
        rag_event = next(e for e in events if e.type == "rag_query")
        self.assertEqual(rag_event.payload["query"], "remind me to cover events")

        # Queue and calendar events captured
        queue_event = next(e for e in events if e.type == "queue_updated")
        self.assertIn("items", queue_event.payload)
        cal_event = next(e for e in events if e.type == "calendar_event_created")
        self.assertEqual(cal_event.payload["event"]["title"], "Event Bus Meeting")


if __name__ == "__main__":
    unittest.main()
