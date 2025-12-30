from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.tools import MemoryTools


class TaskQueueManager:
    """
    Maintains a simple task queue stored as a Node in memory.
    Tasks are ordered by priority (lower is higher priority), due date, then created_at.
    """

    def __init__(self, memory: MemoryTools, name: str = "default"):
        self.memory = memory
        self.name = name
        self.queue_node: Optional[Node] = None

    def ensure_queue(self, provenance: Provenance) -> Node:
        if self.queue_node is None:
            self.queue_node = Node(
                kind="TaskQueue",
                labels=["task_queue", self.name],
                props={
                    "name": self.name,
                    "items": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            self.memory.upsert(self.queue_node, provenance)
        return self.queue_node

    def enqueue(self, task_node: Node, provenance: Provenance) -> Node:
        queue = self.ensure_queue(provenance)
        items = queue.props.get("items", [])
        items.append(
            {
                "task_uuid": task_node.uuid,
                "title": task_node.props.get("title"),
                "priority": task_node.props.get("priority"),
                "due": task_node.props.get("due"),
                "status": task_node.props.get("status", "pending"),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        queue.props["items"] = self._sort_items(items)
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        return queue

    def update_status(self, task_uuid: str, status: str, provenance: Provenance) -> Node:
        queue = self.ensure_queue(provenance)
        for item in queue.props.get("items", []):
            if item["task_uuid"] == task_uuid:
                item["status"] = status
                break
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        return queue

    def _sort_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def sort_key(item: Dict[str, Any]):
            priority = item.get("priority") if item.get("priority") is not None else 999
            due = item.get("due") or ""
            created_at = item.get("created_at") or ""
            return (priority, due, created_at)

        return sorted(items, key=sort_key)
