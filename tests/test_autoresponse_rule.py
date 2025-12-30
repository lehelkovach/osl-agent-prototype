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


class EventCollector(EventBus):
    def __init__(self):
        super().__init__()
        self.events = []

    async def emit(self, event_type, payload):
        self.events.append({"type": event_type, "payload": payload})
        await super().emit(event_type, payload)


class TestAutoResponseRule(unittest.TestCase):
    def test_autoresponse_instruction_creates_rule_and_events(self):
        # Preload a known contact to match recruiter emails
        contacts = MockContactsTools()
        contacts.create(
            name="Recruiter Contact",
            emails=["recruiter@example.com"],
            phones=[],
            org="RecruitCo",
            notes="Known recruiter",
            tags=["recruiter"],
        )

        fake_plan = """
        {
          "intent": "task",
          "steps": [
            {
              "tool": "tasks.create",
              "params": {
                "title": "Auto-respond to recruiter emails",
                "due": null,
                "priority": 1,
                "notes": "Poll inbox; if sender email matches known contact, draft LLM reply and store email embedding + metadata as Email node.",
                "links": []
              }
            }
          ]
        }
        """
        openai_client = FakeOpenAIClient(chat_response=fake_plan, embedding=[0.9, 0.8, 0.7])
        bus = EventCollector()

        agent = PersonalAssistantAgent(
            memory=MockMemoryTools(),
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=MockWebTools(),
            contacts=contacts,
            openai_client=openai_client,
            event_bus=bus,
        )

        user_message = (
            "Please set up auto-responses for job recruiter emails: poll inbox, if sender matches a known contact email,"
            " draft a reply using the email body, store the email embedding as a record linked to the email prototype."
        )
        result = agent.execute_request(user_message)

        self.assertEqual(result["execution_results"]["status"], "completed")
        self.assertEqual(result["plan"]["intent"], "task")
        self.assertEqual(len(agent.tasks.tasks), 1)
        self.assertEqual(agent.tasks.tasks[0]["title"], "Auto-respond to recruiter emails")

        # Task embedding stored in memory
        task_nodes = [n for n in agent.memory.nodes.values() if n.kind == "Task"]
        self.assertEqual(len(task_nodes), 1)
        self.assertEqual(task_nodes[0].llm_embedding, [0.9, 0.8, 0.7])

        # History messages logged with embeddings
        history_nodes = [n for n in agent.memory.nodes.values() if n.kind == "Message"]
        self.assertEqual(len(history_nodes), 2)
        for msg in history_nodes:
            self.assertEqual(msg.llm_embedding, [0.9, 0.8, 0.7])

        # Events include tool invocation, queue update, plan ready, rag query, and memory upsert
        types = [e["type"] for e in bus.events]
        for expected in [
            "request_received",
            "plan_ready",
            "tool_invoked",
            "execution_completed",
            "memory_upsert",
            "queue_updated",
            "message_logged",
            "rag_query",
        ]:
            self.assertIn(expected, types)


if __name__ == "__main__":
    unittest.main()
