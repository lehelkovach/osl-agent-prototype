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
        self.queue_manager.enqueue(task_b, self.provenance)

        items = self.queue_manager.list_items(self.provenance)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["task_uuid"], task_b.uuid)  # higher priority (1) first

    def test_update_status(self):
        task = Node(kind="Task", labels=["A"], props={"title": "A", "priority": 1, "due": None})
        self.queue_manager.enqueue(task, self.provenance)
        items = self.queue_manager.list_items(self.provenance)
        self.assertEqual(items[0]["status"], "queued")
        self.queue_manager.update_status(task.uuid, "done", self.provenance)
        items = self.queue_manager.list_items(self.provenance)
        self.assertEqual(items[0]["status"], "done")

    def test_update_items(self):
        task_a = Node(kind="Task", labels=["A"], props={"title": "A", "priority": 2, "due": "2025-01-02"})
        task_b = Node(kind="Task", labels=["B"], props={"title": "B", "priority": 3, "due": "2025-01-03"})
        self.queue_manager.enqueue(task_a, self.provenance)
        self.queue_manager.enqueue(task_b, self.provenance)
        updates = [{"task_uuid": task_b.uuid, "priority": 1, "status": "in-progress"}]
        self.queue_manager.update_items(updates, self.provenance)
        items = self.queue_manager.list_items(self.provenance)
        self.assertEqual(items[0]["task_uuid"], task_b.uuid)
        self.assertEqual(items[0]["priority"], 1)
        self.assertEqual(items[0]["status"], "in-progress")

    def test_queue_embedding_and_kind(self):
        queue = self.queue_manager.ensure_queue(self.provenance)
        self.assertEqual(queue.kind, "topic")  # KnowShowGo uses topic kind
        self.assertIsNotNone(queue.llm_embedding)

    def test_enqueue_node_and_dequeue_with_edge(self):
        node = Node(kind="Procedure", labels=["proc"], props={"title": "My Proc"})
        self.queue_manager.enqueue_node(node, self.provenance, priority=5)
        items = self.queue_manager.list_items(self.provenance)
        self.assertEqual(items[0]["task_uuid"], node.uuid)
        # Edge from queue to queue_item should exist
        queue = self.queue_manager.ensure_queue(self.provenance)
        edges = list(self.memory.edges.values())
        queue_item_edges = [e for e in edges if e.from_node == queue.uuid and e.rel == "contains"]
        self.assertGreater(len(queue_item_edges), 0)
        # Dequeue returns the same item and marks it as running
        item = self.queue_manager.dequeue(self.provenance)
        self.assertEqual(item["task_uuid"], node.uuid)
        items_after = self.queue_manager.list_items(self.provenance, status="queued")
        self.assertEqual(len(items_after), 0)  # Item is now "running", not "queued"

    def test_enqueue_payload_with_delay_and_not_before_sorting(self):
        early_time = "2024-01-01T00:00:00+00:00"
        later_time = "2024-02-01T00:00:00+00:00"
        self.queue_manager.enqueue_payload(
            provenance=self.provenance,
            title="Delayed later",
            priority=1,
            not_before=later_time,
        )
        self.queue_manager.enqueue_payload(
            provenance=self.provenance,
            title="Delayed earlier",
            priority=1,
            not_before=early_time,
        )
        items = self.queue_manager.list_items(self.provenance)
        self.assertEqual(len(items), 2)
        # Same priority: earlier not_before should come first
        self.assertEqual(items[0]["title"], "Delayed earlier")
        self.assertEqual(items[0]["not_before"], early_time)


if __name__ == "__main__":
    unittest.main()
