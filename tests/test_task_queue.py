import unittest
from datetime import datetime, timezone

from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.task_queue import TaskQueueManager


class TestTaskQueue(unittest.TestCase):
    def setUp(self):
        self.memory = MockMemoryTools()
        self.queue_manager = TaskQueueManager(self.memory, embed_fn=lambda text: [float(len(text)), 0.1])
        self.provenance = Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "trace-queue")

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

    def test_update_items(self):
        task_a = Node(kind="Task", labels=["A"], props={"title": "A", "priority": 2, "due": "2025-01-02"})
        task_b = Node(kind="Task", labels=["B"], props={"title": "B", "priority": 3, "due": "2025-01-03"})
        self.queue_manager.enqueue(task_a, self.provenance)
        queue = self.queue_manager.enqueue(task_b, self.provenance)
        updates = [{"task_uuid": task_b.uuid, "priority": 1, "status": "in-progress"}]
        queue = self.queue_manager.update_items(updates, self.provenance)
        items = queue.props["items"]
        self.assertEqual(items[0]["task_uuid"], task_b.uuid)
        self.assertEqual(items[0]["priority"], 1)
        self.assertEqual(items[0]["status"], "in-progress")

    def test_queue_embedding_and_kind(self):
        queue = self.queue_manager.ensure_queue(self.provenance)
        self.assertEqual(queue.kind, "Queue")
        self.assertIsNotNone(queue.llm_embedding)

    def test_enqueue_node_and_dequeue_with_edge(self):
        node = Node(kind="Procedure", labels=["proc"], props={"title": "My Proc"})
        queue = self.queue_manager.enqueue_node(node, self.provenance, priority=5)
        self.assertEqual(queue.props["items"][0]["task_uuid"], node.uuid)
        # Edge from queue to node should exist
        edges = list(self.memory.edges.values())
        self.assertTrue(any(e.from_node == queue.uuid and e.to_node == node.uuid and e.rel == "contains" for e in edges))
        # Dequeue returns the same item and removes it
        item = self.queue_manager.dequeue(self.provenance)
        self.assertEqual(item["task_uuid"], node.uuid)
        queue_after = self.queue_manager.ensure_queue(self.provenance)
        self.assertEqual(queue_after.props["items"], [])

    def test_enqueue_payload_with_delay_and_not_before_sorting(self):
        early_time = "2024-01-01T00:00:00+00:00"
        later_time = "2024-02-01T00:00:00+00:00"
        q1 = self.queue_manager.enqueue_payload(
            provenance=self.provenance,
            title="Delayed later",
            priority=1,
            not_before=later_time,
        )
        q2 = self.queue_manager.enqueue_payload(
            provenance=self.provenance,
            title="Delayed earlier",
            priority=1,
            not_before=early_time,
        )
        items = q2.props["items"]
        self.assertEqual(len(items), 2)
        # Same priority: earlier not_before should come first
        self.assertEqual(items[0]["title"], "Delayed earlier")
        self.assertEqual(items[0]["not_before"], early_time)


if __name__ == "__main__":
    unittest.main()
