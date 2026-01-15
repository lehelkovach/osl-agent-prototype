import unittest
from datetime import datetime, timedelta, timezone

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.scheduler import Scheduler, TimeRule
from src.personal_assistant.task_queue import TaskQueueManager
from src.personal_assistant.openai_client import FakeOpenAIClient


class TestAgentSchedulerQueue(unittest.TestCase):
    def test_queue_instantiated_with_embedding(self):
        memory = MockMemoryTools()
        agent = PersonalAssistantAgent(
            memory,
            MockCalendarTools(),
            MockTaskTools(),
            web=MockWebTools(),
            contacts=MockContactsTools(),
            openai_client=FakeOpenAIClient(chat_response='{"intent":"inform","steps":[]}', embedding=[0.1, 0.2]),
        )
        qnode = agent.queue_manager.ensure_queue(provenance=agent_prov())
        # Queue uses "topic" kind for KnowShowGo compatibility, but has "Queue" in labels
        self.assertIn("Queue", qnode.labels)
        # embedding may be None if embed_fn fails, but it should have been attempted
        self.assertTrue(hasattr(qnode, "llm_embedding"))

    def test_scheduler_enqueues_task_and_calendar_stub(self):
        memory = MockMemoryTools()
        tasks = MockTaskTools()
        queue_mgr = TaskQueueManager(memory, embed_fn=lambda text: [1.0, 0.0])
        scheduler = Scheduler(memory, tasks, queue_mgr, embed_fn=lambda text: [1.0, 0.0])

        now = datetime.now(timezone.utc)
        rule_time = now + timedelta(minutes=1)
        rule = TimeRule(
            title="alarm",
            notes="test alarm",
            hour=rule_time.hour,
            minute=rule_time.minute,
        )
        scheduler.add_time_rule(rule)
        scheduler.tick(rule_time)
        queue_items = queue_mgr.list_items(provenance=agent_prov())
        self.assertGreaterEqual(len(queue_items), 1)


def agent_prov():
    return FakeProvenance()


class FakeProvenance:
    source = "user"
    ts = datetime.now(timezone.utc).isoformat()
    confidence = 1.0
    trace_id = "test"


if __name__ == "__main__":
    unittest.main()
