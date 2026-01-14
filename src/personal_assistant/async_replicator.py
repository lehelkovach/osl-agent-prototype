"""
Async Replicator: Background worker for persisting activation updates.

Ported from deprecated knowshowgo repository.
Decouples hot path from database writes for better latency.

Usage:
    replicator = AsyncReplicator(arango_graph_client)
    await replicator.start()
    
    # Fire-and-forget from agent loop
    await replicator.enqueue(EdgeUpdate("a", "b", delta=1.0, max_weight=100.0))
    
    # Graceful shutdown with flush
    await replicator.queue.join()  # Wait for pending writes
    await replicator.stop()
"""

import asyncio
from dataclasses import dataclass
from typing import Protocol, Optional
from src.personal_assistant.logging_setup import get_logger

log = get_logger(__name__)


@dataclass
class EdgeUpdate:
    """Represents a weight update to persist."""
    source: str
    target: str
    delta: float
    max_weight: float


class GraphClient(Protocol):
    """Protocol for persistence backends that support edge weight updates."""
    
    async def increment_edge_weight(
        self, source: str, target: str, delta: float, max_weight: float
    ) -> None:
        """Atomically increment edge weight with cap."""
        ...


class AsyncReplicator:
    """Background worker to push edge-weight updates to long-term store.
    
    Features:
    - Async queue with backpressure
    - Clean start/stop lifecycle
    - Flush semantics via queue.join()
    - Pluggable backend via GraphClient protocol
    """

    def __init__(self, client: GraphClient, max_queue_size: int = 1000) -> None:
        self.client = client
        self.queue: asyncio.Queue[EdgeUpdate] = asyncio.Queue(maxsize=max_queue_size)
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start the background worker."""
        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self._worker())
            log.info("async_replicator_started")

    async def stop(self) -> None:
        """Stop the worker gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            log.info("async_replicator_stopped")

    async def enqueue(self, update: EdgeUpdate) -> None:
        """Queue an update for background persistence."""
        await self.queue.put(update)

    def enqueue_nowait(self, update: EdgeUpdate) -> bool:
        """Non-blocking enqueue. Returns False if queue is full."""
        try:
            self.queue.put_nowait(update)
            return True
        except asyncio.QueueFull:
            log.warning("async_replicator_queue_full", source=update.source, target=update.target)
            return False

    async def flush(self, timeout: float = 5.0) -> bool:
        """Wait for all pending updates to be processed.
        
        Args:
            timeout: Maximum seconds to wait (default 5.0)
            
        Returns:
            True if flushed successfully, False if timed out
        """
        try:
            await asyncio.wait_for(self.queue.join(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            log.warning("async_replicator_flush_timeout", pending=self.pending_count())
            return False

    def pending_count(self) -> int:
        """Return number of pending updates in queue."""
        return self.queue.qsize()

    async def _worker(self) -> None:
        """Worker loop: consume updates and persist."""
        while self._running:
            try:
                update = await asyncio.wait_for(self.queue.get(), timeout=1.0)
                try:
                    await self.client.increment_edge_weight(
                        source=update.source,
                        target=update.target,
                        delta=update.delta,
                        max_weight=update.max_weight,
                    )
                except Exception as e:
                    log.error("async_replicator_persist_error", error=str(e), source=update.source, target=update.target)
                finally:
                    self.queue.task_done()
            except asyncio.TimeoutError:
                continue  # Check _running flag periodically
            except asyncio.CancelledError:
                break
