import unittest
from datetime import datetime

from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.task_queue import TaskQueueManager


class TestTaskQueue(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemoryTools()
        self.queue_manager = TaskQueueManager(self.memory)
        self.provenance = Provenance("user", datetime.utcnow().isoformat(), 1.0, "trace-queue")

    def test_enqueue_and_sort(self):
        task_a = Node(kind="Task", labels=["A"], props={"title": "A", "priority": 2, "due": "2025-01-02"})
        task_b = Node(kind="Task", labels=["B"], props={"title": "B", "priority": 1, "due": "2025-01-03"})
        self.queue_manager.enqueue(task_a, self.provenance)
        queue = self.queue_manager.enqueue(task_b, self.provenance)

        items = queue.props["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["task_uuid"], task_b.uuid)  # higher priority (1) first

    def test_update_status(self):
        task = Node(kind="Task", labels=["A"], props={"title": "A", "priority": 1, "due": None})
        queue = self.queue_manager.enqueue(task, self.provenance)
        self.assertEqual(queue.props["items"][0]["status"], "pending")
        queue = self.queue_manager.update_status(task.uuid, "done", self.provenance)
        self.assertEqual(queue.props["items"][0]["status"], "done")


if __name__ == "__main__":
    unittest.main()
