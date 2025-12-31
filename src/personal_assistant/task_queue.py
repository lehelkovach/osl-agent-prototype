from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools


class TaskQueueManager:
    """
    Maintains a simple task queue stored as a Node in memory.
    Tasks are ordered by priority (lower is higher priority), due date, then created_at.
    """

    def __init__(self, memory: MemoryTools, name: str = "default", embed_fn=None):
        self.memory = memory
        self.name = name
        self.queue_node: Optional[Node] = None
        self.embed_fn = embed_fn

    def ensure_queue(self, provenance: Provenance) -> Node:
        if self.queue_node is None:
            self.queue_node = Node(
                kind="Queue",
                labels=["Queue", "task_queue", self.name],
                props={
                    "name": self.name,
                    "items": [],
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            if self.embed_fn:
                try:
                    self.queue_node.llm_embedding = self.embed_fn(f"queue {self.name}")
                except Exception:
                    self.queue_node.llm_embedding = None
            self.memory.upsert(self.queue_node, provenance, embedding_request=True)
        return self.queue_node

    def enqueue(self, task_node: Node, provenance: Provenance) -> Node:
        return self.enqueue_node(
            task_node,
            provenance,
            priority=task_node.props.get("priority"),
            due=task_node.props.get("due"),
            status=task_node.props.get("status", "pending"),
            title=task_node.props.get("title"),
        )

    def update_status(self, task_uuid: str, status: str, provenance: Provenance) -> Node:
        queue = self.ensure_queue(provenance)
        for item in queue.props.get("items", []):
            if item["task_uuid"] == task_uuid:
                item["status"] = status
                break
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        return queue

    def update_items(self, updates: List[Dict[str, Any]], provenance: Provenance) -> Node:
        """
        Update items' priority/due/status by task_uuid, then re-sort.
        """
        queue = self.ensure_queue(provenance)
        items = queue.props.get("items", [])
        for upd in updates:
            for item in items:
                if item.get("task_uuid") == upd.get("task_uuid"):
                    if "priority" in upd:
                        item["priority"] = upd["priority"]
                    if "due" in upd:
                        item["due"] = upd["due"]
                    if "status" in upd:
                        item["status"] = upd["status"]
        queue.props["items"] = self._sort_items(items)
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        return queue

    def enqueue_node(
        self,
        node: Node,
        provenance: Provenance,
        priority: Optional[int] = None,
        due: Optional[str] = None,
        status: str = "pending",
        title: Optional[str] = None,
        create_edge: bool = True,
    ) -> Node:
        """
        Enqueue any concept node, optionally linking the queue to the node via an edge.
        """
        queue = self.ensure_queue(provenance)
        items = queue.props.get("items", [])
        items.append(
            {
                "task_uuid": node.uuid,
                "title": title or node.props.get("title") or node.props.get("name"),
                "priority": priority if priority is not None else node.props.get("priority"),
                "due": due if due is not None else node.props.get("due"),
                "status": status,
                "kind": node.kind,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        queue.props["items"] = self._sort_items(items)
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        if create_edge:
            edge = Edge(
                from_node=queue.uuid,
                to_node=node.uuid,
                rel="contains",
                props={"kind": node.kind, "enqueued_at": datetime.now(timezone.utc).isoformat()},
            )
            self.memory.upsert(edge, provenance)
        return queue

    def dequeue(self, provenance: Provenance) -> Optional[Dict[str, Any]]:
        queue = self.ensure_queue(provenance)
        items = queue.props.get("items", [])
        if not items:
            return None
        item = items.pop(0)
        queue.props["items"] = items
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        return item

    def _sort_items(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        def sort_key(item: Dict[str, Any]):
            priority = item.get("priority") if item.get("priority") is not None else 999
            due = item.get("due") or ""
            created_at = item.get("created_at") or ""
            return (priority, due, created_at)

        return sorted(items, key=sort_key)
