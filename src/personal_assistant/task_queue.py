from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools
from src.personal_assistant.knowshowgo import KnowShowGoAPI


class TaskQueueManager:
    """
    Maintains a task queue stored in KnowShowGo semantic memory.
    Queue items are stored as QueueItem concepts (not just JSON in props).
    Tasks are ordered by priority (lower is higher priority), due date, then created_at.
    """

    def __init__(self, memory: MemoryTools, name: str = "default", embed_fn=None, ksg: Optional[KnowShowGoAPI] = None):
        self.memory = memory
        self.name = name
        self.queue_node: Optional[Node] = None
        self.embed_fn = embed_fn
        self.ksg = ksg or KnowShowGoAPI(memory, embed_fn=embed_fn)
        self._queue_item_prototype_uuid: Optional[str] = None

    def _get_queue_item_prototype_uuid(self) -> str:
        """Get QueueItem prototype UUID, creating it if needed."""
        if self._queue_item_prototype_uuid is None:
            # Search for QueueItem prototype
            for node in self.memory.nodes.values():
                if (node.kind == "topic" and 
                    node.props.get("isPrototype") is True and
                    node.props.get("label") == "QueueItem"):
                    self._queue_item_prototype_uuid = node.uuid
                    break
            
            # If not found, create it
            if self._queue_item_prototype_uuid is None:
                self._queue_item_prototype_uuid = self.ksg.create_prototype(
                    name="QueueItem",
                    description="Item in a priority queue",
                    context="assistant",
                    labels=["QueueItem"],
                    embedding=self.embed_fn("QueueItem") if self.embed_fn else None,
                )
        return self._queue_item_prototype_uuid

    def ensure_queue(self, provenance: Provenance) -> Node:
        """Ensure queue node exists. Queue items are stored as QueueItem concepts, not in props."""
        if self.queue_node is None:
            # Use topic kind for KnowShowGo compatibility
            self.queue_node = Node(
                kind="topic",
                labels=["Queue", "task_queue", self.name],
                props={
                    "label": f"Queue: {self.name}",
                    "name": self.name,
                    "isPrototype": False,
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
            status=task_node.props.get("status", "queued"),
            title=task_node.props.get("title"),
        )

    def update_status(self, task_uuid: str, status: str, provenance: Provenance) -> Node:
        """Update QueueItem state by finding it via the task_uuid reference."""
        queue = self.ensure_queue(provenance)
        
        # Find QueueItem that references this task_uuid
        # QueueItems are created as Concept nodes with task_uuid prop
        queue_item_node = None
        for node in self.memory.nodes.values():
            if (node.kind in ("Concept", "topic") and 
                node.props.get("isPrototype") is not True and
                node.props.get("task_uuid") == task_uuid):
                # Check if it's linked to this queue
                for edge in self.memory.edges.values():
                    if (edge.from_node == queue.uuid and 
                        edge.to_node == node.uuid and 
                        edge.rel == "contains"):
                        queue_item_node = node
                        break
                if queue_item_node:
                    break
        
        if queue_item_node:
            # Update state
            queue_item_node.props["state"] = status
            queue_item_node.props["updated_at"] = datetime.now(timezone.utc).isoformat()
            self.memory.upsert(queue_item_node, provenance)
        
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        return queue

    def update_items(self, updates: List[Dict[str, Any]], provenance: Provenance) -> Node:
        """
        Update QueueItems' priority/due/state by task_uuid.
        """
        queue = self.ensure_queue(provenance)
        
        # Find all QueueItems linked to this queue
        queue_items = []
        for edge in self.memory.edges.values():
            if edge.from_node == queue.uuid and edge.rel == "contains":
                queue_item = self.memory.nodes.get(edge.to_node)
                if queue_item:
                    queue_items.append(queue_item)
        
        # Update matching items
        for upd in updates:
            task_uuid = upd.get("task_uuid")
            for item in queue_items:
                if item.props.get("task_uuid") == task_uuid:
                    if "priority" in upd:
                        item.props["priority"] = upd["priority"]
                    if "due" in upd:
                        item.props["due"] = upd["due"]
                    if "status" in upd:
                        item.props["state"] = upd["status"]
                    item.props["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self.memory.upsert(item, provenance)
        
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        return queue

    def enqueue_node(
        self,
        node: Node,
        provenance: Provenance,
        priority: Optional[int] = None,
        due: Optional[str] = None,
        status: str = "queued",
        title: Optional[str] = None,
        create_edge: bool = True,
        not_before: Optional[str] = None,
        procedure_uuid: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Node:
        """
        Enqueue any concept node by creating a QueueItem concept in KnowShowGo.
        The QueueItem links to the task/procedure node and the queue.
        """
        queue = self.ensure_queue(provenance)
        
        # Get QueueItem prototype
        queue_item_proto_uuid = self._get_queue_item_prototype_uuid()
        
        # Determine priority, due, title
        final_priority = priority if priority is not None else node.props.get("priority")
        final_due = due if due is not None else node.props.get("due")
        final_title = title or node.props.get("title") or node.props.get("name") or node.props.get("label") or "Untitled"
        
        # Create QueueItem concept
        enqueued_at = datetime.now(timezone.utc).isoformat()
        queue_item_json = {
            "label": final_title,
            "name": final_title,
            "priority": final_priority,
            "due": final_due,
            "state": status,  # queued|running|done|failed
            "enqueuedAt": enqueued_at,
            "not_before": not_before or node.props.get("not_before"),
            "context": context or {},
            "task_uuid": node.uuid,  # Reference to the actual task/procedure
            "kind": node.kind,
        }
        
        # Generate embedding for semantic search
        embedding = None
        if self.embed_fn:
            try:
                embedding = self.embed_fn(f"{final_title} {node.kind}")
            except Exception:
                pass
        
        # Create QueueItem concept
        queue_item_uuid = self.ksg.create_concept(
            prototype_uuid=queue_item_proto_uuid,
            json_obj=queue_item_json,
            embedding=embedding,
        )
        
        # Link queue -> queue_item
        queue_to_item_edge = Edge(
            from_node=queue.uuid,
            to_node=queue_item_uuid,
            rel="contains",
            props={
                "enqueued_at": enqueued_at,
                "priority": final_priority,
            },
        )
        self.memory.upsert(queue_to_item_edge, provenance)
        
        # Link queue_item -> task/procedure node
        if create_edge:
            item_to_task_edge = Edge(
                from_node=queue_item_uuid,
                to_node=node.uuid,
                rel="references",
                props={"kind": node.kind},
            )
            self.memory.upsert(item_to_task_edge, provenance)
        
        # Link queue_item -> procedure if provided
        if procedure_uuid:
            runs_procedure_edge = Edge(
                from_node=queue_item_uuid,
                to_node=procedure_uuid,
                rel="runsProcedure",
                props={},
            )
            self.memory.upsert(runs_procedure_edge, provenance)
        
        # Update queue node's updated_at
        queue.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue, provenance)
        
        return queue

    def enqueue_payload(
        self,
        provenance: Provenance,
        title: str,
        kind: str = "Task",
        labels: Optional[List[str]] = None,
        priority: Optional[int] = None,
        due: Optional[str] = None,
        status: str = "queued",
        not_before: Optional[str] = None,
        props: Optional[Dict[str, Any]] = None,
        create_edge: bool = True,
    ) -> Node:
        """
        Convenience to create a node from payload and enqueue it.
        """
        node_props = {
            "title": title,
            "priority": priority,
            "due": due,
            "status": status,
            "not_before": not_before,
        }
        if props:
            node_props.update(props)
        node = Node(kind=kind, labels=labels or [kind], props=node_props)
        if self.embed_fn:
            try:
                node.llm_embedding = self.embed_fn(title)
            except Exception:
                node.llm_embedding = None
        self.memory.upsert(node, provenance, embedding_request=True)
        return self.enqueue_node(
            node,
            provenance,
            priority=priority,
            due=due,
            status=status,
            title=title,
            create_edge=create_edge,
            not_before=not_before,
        )

    def dequeue(self, provenance: Provenance) -> Optional[Dict[str, Any]]:
        """Dequeue the highest priority QueueItem and return its task reference."""
        queue = self.ensure_queue(provenance)
        
        # Find all QueueItems linked to this queue
        queue_items = []
        for edge in self.memory.edges.values():
            if edge.from_node == queue.uuid and edge.rel == "contains":
                queue_item = self.memory.nodes.get(edge.to_node)
                if queue_item and queue_item.props.get("state") == "queued":
                    queue_items.append(queue_item)
        
        if not queue_items:
            return None
        
        # Sort by priority, not_before, due, created_at
        sorted_items = self._sort_queue_items(queue_items)
        if not sorted_items:
            return None
        
        # Get the first item
        queue_item = sorted_items[0]
        
        # Update state to running
        queue_item.props["state"] = "running"
        queue_item.props["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.memory.upsert(queue_item, provenance)
        
        # Return task reference
        task_uuid = queue_item.props.get("task_uuid")
        task_node = self.memory.nodes.get(task_uuid) if task_uuid else None
        
        return {
            "queue_item_uuid": queue_item.uuid,
            "task_uuid": task_uuid,
            "title": queue_item.props.get("label") or queue_item.props.get("name"),
            "priority": queue_item.props.get("priority"),
            "due": queue_item.props.get("due"),
            "status": queue_item.props.get("state"),
            "kind": queue_item.props.get("kind"),
            "created_at": queue_item.props.get("enqueuedAt"),
            "not_before": queue_item.props.get("not_before"),
            "task_node": task_node,
        }

    def _sort_queue_items(self, queue_items: List[Node]) -> List[Node]:
        """Sort QueueItem nodes by priority, not_before, due, created_at."""
        def sort_key(item: Node):
            props = item.props
            priority = props.get("priority") if props.get("priority") is not None else 999
            not_before = props.get("not_before") or ""
            due = props.get("due") or ""
            created_at = props.get("enqueuedAt") or props.get("created_at") or ""
            return (priority, not_before or due, due, created_at)

        return sorted(queue_items, key=sort_key)
    
    def list_items(self, provenance: Provenance, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all QueueItems in the queue, optionally filtered by state."""
        queue = self.ensure_queue(provenance)
        
        # Find all QueueItems linked to this queue
        queue_items = []
        for edge in self.memory.edges.values():
            if edge.from_node == queue.uuid and edge.rel == "contains":
                queue_item = self.memory.nodes.get(edge.to_node)
                if queue_item:
                    item_state = queue_item.props.get("state", "queued")
                    if status is None or item_state == status:
                        task_uuid = queue_item.props.get("task_uuid")
                        task_node = self.memory.nodes.get(task_uuid) if task_uuid else None
                        queue_items.append({
                            "queue_item_uuid": queue_item.uuid,
                            "task_uuid": task_uuid,
                            "title": queue_item.props.get("label") or queue_item.props.get("name"),
                            "priority": queue_item.props.get("priority"),
                            "due": queue_item.props.get("due"),
                            "status": item_state,
                            "kind": queue_item.props.get("kind"),
                            "created_at": queue_item.props.get("enqueuedAt"),
                            "not_before": queue_item.props.get("not_before"),
                            "task_node": task_node,
                        })
        
        # Sort by priority
        return sorted(queue_items, key=lambda x: (
            x.get("priority") if x.get("priority") is not None else 999,
            x.get("not_before") or x.get("due") or "",
            x.get("due") or "",
            x.get("created_at") or "",
        ))
