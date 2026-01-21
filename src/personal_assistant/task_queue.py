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

    def _node_props(self, node: Any) -> Dict[str, Any]:
        if isinstance(node, dict):
            return node.get("props", {}) or {}
        return getattr(node, "props", {}) or {}

    def _node_uuid(self, node: Any) -> Optional[str]:
        if isinstance(node, dict):
            return node.get("uuid") or node.get("_key")
        return getattr(node, "uuid", None)

    def _node_kind(self, node: Any) -> Optional[str]:
        if isinstance(node, dict):
            return node.get("kind")
        return getattr(node, "kind", None)

    def _edge_from(self, edge: Any) -> Optional[str]:
        if isinstance(edge, dict):
            val = edge.get("from_node") or edge.get("_from")
        else:
            val = getattr(edge, "from_node", None)
        if isinstance(val, str) and "/" in val:
            return val.split("/")[-1]
        return val

    def _edge_to(self, edge: Any) -> Optional[str]:
        if isinstance(edge, dict):
            val = edge.get("to_node") or edge.get("_to")
        else:
            val = getattr(edge, "to_node", None)
        if isinstance(val, str) and "/" in val:
            return val.split("/")[-1]
        return val

    def _edge_rel(self, edge: Any) -> Optional[str]:
        if isinstance(edge, dict):
            return edge.get("rel")
        return getattr(edge, "rel", None)

    def _iter_nodes(self) -> List[Any]:
        if hasattr(self.memory, "iter_nodes"):
            return list(self.memory.iter_nodes())
        nodes_attr = getattr(self.memory, "nodes", None)
        if isinstance(nodes_attr, dict):
            return list(nodes_attr.values())
        if hasattr(nodes_attr, "all"):
            return list(nodes_attr.all())
        return []

    def _get_node(self, uuid: Optional[str]) -> Optional[Any]:
        if not uuid:
            return None
        if hasattr(self.memory, "get_node"):
            return self.memory.get_node(uuid)
        nodes_attr = getattr(self.memory, "nodes", None)
        if hasattr(nodes_attr, "get"):
            return nodes_attr.get(uuid)
        return None

    def _iter_edges(self, from_node: Optional[str] = None, rel: Optional[str] = None) -> List[Any]:
        if hasattr(self.memory, "get_edges"):
            return self.memory.get_edges(from_node=from_node, rel=rel)
        edges_attr = getattr(self.memory, "edges", None)
        if isinstance(edges_attr, dict):
            edges = list(edges_attr.values())
        elif hasattr(edges_attr, "all"):
            edges = list(edges_attr.all())
        else:
            return []
        filtered = []
        for edge in edges:
            if rel and self._edge_rel(edge) != rel:
                continue
            if from_node and self._edge_from(edge) != from_node:
                continue
            filtered.append(edge)
        return filtered

    def _get_queue_item_prototype_uuid(self) -> str:
        """Get QueueItem prototype UUID, creating it if needed."""
        if self._queue_item_prototype_uuid is None:
            # Search for QueueItem prototype
            for node in self._iter_nodes():
                if (
                    self._node_kind(node) == "topic"
                    and self._node_props(node).get("isPrototype") is True
                    and self._node_props(node).get("label") == "QueueItem"
                ):
                    self._queue_item_prototype_uuid = self._node_uuid(node)
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
        for node in self._iter_nodes():
            props = self._node_props(node)
            if (
                self._node_kind(node) in ("Concept", "topic")
                and props.get("isPrototype") is not True
                and props.get("task_uuid") == task_uuid
            ):
                # Check if it's linked to this queue
                for edge in self._iter_edges(from_node=queue.uuid, rel="contains"):
                    if self._edge_to(edge) == self._node_uuid(node):
                        queue_item_node = node
                        break
                if queue_item_node:
                    break
        
        if queue_item_node:
            # Update state
            props = self._node_props(queue_item_node)
            props["state"] = status
            props["updated_at"] = datetime.now(timezone.utc).isoformat()
            if isinstance(queue_item_node, dict):
                queue_item_node["props"] = props
            else:
                queue_item_node.props = props
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
        for edge in self._iter_edges(from_node=queue.uuid, rel="contains"):
            queue_item = self._get_node(self._edge_to(edge))
            if queue_item:
                queue_items.append(queue_item)
        
        # Update matching items
        for upd in updates:
            task_uuid = upd.get("task_uuid")
            for item in queue_items:
                props = self._node_props(item)
                if props.get("task_uuid") == task_uuid:
                    if "priority" in upd:
                        props["priority"] = upd["priority"]
                    if "due" in upd:
                        props["due"] = upd["due"]
                    if "status" in upd:
                        props["state"] = upd["status"]
                    props["updated_at"] = datetime.now(timezone.utc).isoformat()
                    if isinstance(item, dict):
                        item["props"] = props
                    else:
                        item.props = props
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
        for edge in self._iter_edges(from_node=queue.uuid, rel="contains"):
            queue_item = self._get_node(self._edge_to(edge))
            if queue_item and self._node_props(queue_item).get("state") == "queued":
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
        props = self._node_props(queue_item)
        props["state"] = "running"
        props["updated_at"] = datetime.now(timezone.utc).isoformat()
        if isinstance(queue_item, dict):
            queue_item["props"] = props
        else:
            queue_item.props = props
        self.memory.upsert(queue_item, provenance)
        
        # Return task reference
        task_uuid = props.get("task_uuid")
        task_node = self._get_node(task_uuid) if task_uuid else None
        
        return {
            "queue_item_uuid": self._node_uuid(queue_item),
            "task_uuid": task_uuid,
            "title": props.get("label") or props.get("name"),
            "priority": props.get("priority"),
            "due": props.get("due"),
            "status": props.get("state"),
            "kind": props.get("kind"),
            "created_at": props.get("enqueuedAt"),
            "not_before": props.get("not_before"),
            "task_node": task_node,
        }

    def _sort_queue_items(self, queue_items: List[Node]) -> List[Node]:
        """Sort QueueItem nodes by priority, not_before, due, created_at."""
        def sort_key(item: Node):
            props = self._node_props(item)
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
        for edge in self._iter_edges(from_node=queue.uuid, rel="contains"):
            queue_item = self._get_node(self._edge_to(edge))
            if queue_item:
                props = self._node_props(queue_item)
                item_state = props.get("state", "queued")
                if status is None or item_state == status:
                    task_uuid = props.get("task_uuid")
                    task_node = self._get_node(task_uuid) if task_uuid else None
                    queue_items.append({
                        "queue_item_uuid": self._node_uuid(queue_item),
                        "task_uuid": task_uuid,
                        "title": props.get("label") or props.get("name"),
                        "priority": props.get("priority"),
                        "due": props.get("due"),
                        "status": item_state,
                        "kind": props.get("kind"),
                        "created_at": props.get("enqueuedAt"),
                        "not_before": props.get("not_before"),
                        "task_node": task_node,
                    })
        
        # Sort by priority
        return sorted(queue_items, key=lambda x: (
            x.get("priority") if x.get("priority") is not None else 999,
            x.get("not_before") or x.get("due") or "",
            x.get("due") or "",
            x.get("created_at") or "",
        ))
