import unittest
from datetime import datetime, timezone
from src.personal_assistant.models import Provenance

from src.personal_assistant.scheduler import Scheduler, TimeRule
from src.personal_assistant.mock_tools import MockMemoryTools, MockTaskTools
from src.personal_assistant.task_queue import TaskQueueManager


class TestScheduler(unittest.TestCase):
    def test_time_rule_enqueues_task_with_dag(self):
        memory = MockMemoryTools()
        tasks = MockTaskTools()
        queue_manager = TaskQueueManager(memory)

        def embed(text):
            return [0.3, 0.3]

        scheduler = Scheduler(memory, tasks, queue_manager, embed)
        rule = TimeRule(
            title="start alarm playback service",
            notes="Daily alarm",
            hour=8,
            minute=0,
            priority=1,
            dag={"nodes": [{"id": "start", "op": "play_alarm"}], "edges": []},
        )
        scheduler.add_time_rule(rule)

        now = datetime(2025, 1, 1, 8, 0, tzinfo=timezone.utc)
        scheduler.tick(now)

        # Task created and enqueued
        self.assertEqual(len(tasks.tasks), 1)
        self.assertEqual(tasks.tasks[0]["title"], "start alarm playback service")
        queue = queue_manager.ensure_queue(
            provenance=Provenance("user", datetime.now(timezone.utc).isoformat(), 1.0, "trace")
        )
        self.assertEqual(len(queue.props["items"]), 1)
        # Memory node stored with DAG and embedding
        task_nodes = [n for n in memory.nodes.values() if n.kind == "Task"]
        self.assertEqual(len(task_nodes), 1)
        self.assertEqual(task_nodes[0].props.get("dag")["nodes"][0]["op"], "play_alarm")
        self.assertEqual(task_nodes[0].llm_embedding, [0.3, 0.3])


if __name__ == "__main__":
    unittest.main()
