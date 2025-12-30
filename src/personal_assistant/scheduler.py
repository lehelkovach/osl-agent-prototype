from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, List, Dict, Any, Set, Optional

from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.task_queue import TaskQueueManager
from src.personal_assistant.tools import MemoryTools, TaskTools


EmbedFn = Callable[[str], List[float]]


@dataclass
class TimeRule:
    title: str
    notes: str
    hour: int
    minute: int
    priority: int = 1
    labels: List[str] = field(default_factory=lambda: ["Task", "DAG"])
    dag: Optional[Dict[str, Any]] = None  # optional DAG payload to persist on the task


class Scheduler:
    """
    Minimal scheduler that evaluates time-based rules and enqueues tasks when conditions match.
    Intended to be invoked from the agent loop (e.g., periodic tick).
    """

    def __init__(
        self,
        memory: MemoryTools,
        tasks: TaskTools,
        queue_manager: TaskQueueManager,
        embed_fn: EmbedFn,
    ):
        self.memory = memory
        self.tasks = tasks
        self.queue_manager = queue_manager
        self.embed_fn = embed_fn
        self.rules: List[TimeRule] = []
        self._fired_keys: Set[str] = set()

    def add_time_rule(self, rule: TimeRule):
        self.rules.append(rule)

    def tick(self, now: datetime):
        """Evaluate rules against current time and enqueue matching tasks."""
        for rule in self.rules:
            if now.hour == rule.hour and now.minute == rule.minute:
                key = f"{rule.title}:{now.isoformat(timespec='minutes')}"
                if key in self._fired_keys:
                    continue
                self._fire_rule(rule, now)
                self._fired_keys.add(key)

    def _fire_rule(self, rule: TimeRule, now: datetime):
        prov = Provenance("user", now.astimezone(timezone.utc).isoformat(), 1.0, "scheduler")
        # Create task via TaskTools
        res = self.tasks.create(
            title=rule.title,
            due=None,
            priority=rule.priority,
            notes=rule.notes,
            links=[],
        )
        task_data = res.get("task", {"title": rule.title, "priority": rule.priority, "notes": rule.notes, "status": "pending"})
        task_node = Node(
            kind="Task",
            labels=rule.labels,
            props={**task_data, "dag": rule.dag} if rule.dag else task_data,
        )
        try:
            task_node.llm_embedding = self.embed_fn(rule.title)
        except Exception:
            task_node.llm_embedding = None
        self.memory.upsert(task_node, prov, embedding_request=True)
        self.queue_manager.enqueue(task_node, prov)
