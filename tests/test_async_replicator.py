"""Tests for AsyncReplicator - background persistence worker."""
import pytest
import asyncio
from src.personal_assistant.async_replicator import AsyncReplicator, EdgeUpdate

pytestmark = pytest.mark.asyncio(loop_scope="function")


class MockGraphClient:
    """Mock client that records calls for testing."""
    
    def __init__(self, delay: float = 0.0, fail_on: set = None):
        self.calls = []
        self.delay = delay
        self.fail_on = fail_on or set()
    
    async def increment_edge_weight(
        self, source: str, target: str, delta: float, max_weight: float
    ) -> None:
        if self.delay > 0:
            await asyncio.sleep(self.delay)
        if (source, target) in self.fail_on:
            raise Exception(f"Simulated failure for {source}->{target}")
        self.calls.append({
            "source": source,
            "target": target,
            "delta": delta,
            "max_weight": max_weight,
        })


async def test_start_stop_lifecycle():
    """Test clean start/stop without processing."""
    client = MockGraphClient()
    replicator = AsyncReplicator(client)
    
    await replicator.start()
    assert replicator._running is True
    assert replicator._task is not None
    
    await replicator.stop()
    assert replicator._running is False
    assert replicator._task is None


async def test_enqueue_and_process():
    """Test enqueueing and processing updates."""
    client = MockGraphClient()
    replicator = AsyncReplicator(client)
    
    await replicator.start()
    
    await replicator.enqueue(EdgeUpdate("a", "b", delta=1.0, max_weight=100.0))
    await replicator.enqueue(EdgeUpdate("b", "c", delta=2.0, max_weight=50.0))
    
    await replicator.flush()  # Wait for processing
    
    assert len(client.calls) == 2
    assert client.calls[0] == {"source": "a", "target": "b", "delta": 1.0, "max_weight": 100.0}
    assert client.calls[1] == {"source": "b", "target": "c", "delta": 2.0, "max_weight": 50.0}
    
    await replicator.stop()


async def test_enqueue_nowait_success():
    """Test non-blocking enqueue when queue has space."""
    client = MockGraphClient()
    replicator = AsyncReplicator(client, max_queue_size=10)
    
    success = replicator.enqueue_nowait(EdgeUpdate("a", "b", delta=1.0, max_weight=100.0))
    assert success is True
    assert replicator.pending_count() == 1


async def test_enqueue_nowait_full():
    """Test non-blocking enqueue when queue is full."""
    client = MockGraphClient(delay=1.0)  # Slow processing so queue stays full
    replicator = AsyncReplicator(client, max_queue_size=2)
    
    # Start replicator but with slow processing
    await replicator.start()
    
    # Fill the queue quickly
    assert replicator.enqueue_nowait(EdgeUpdate("a", "b", delta=1.0, max_weight=100.0)) is True
    assert replicator.enqueue_nowait(EdgeUpdate("b", "c", delta=1.0, max_weight=100.0)) is True
    
    # This should fail because queue is full and worker is slow
    success = replicator.enqueue_nowait(EdgeUpdate("c", "d", delta=1.0, max_weight=100.0))
    assert success is False
    
    await replicator.stop()


async def test_pending_count():
    """Test pending count tracking."""
    client = MockGraphClient()
    replicator = AsyncReplicator(client)
    
    assert replicator.pending_count() == 0
    
    replicator.enqueue_nowait(EdgeUpdate("a", "b", delta=1.0, max_weight=100.0))
    assert replicator.pending_count() == 1
    
    replicator.enqueue_nowait(EdgeUpdate("b", "c", delta=1.0, max_weight=100.0))
    assert replicator.pending_count() == 2


async def test_error_handling_continues_processing():
    """Test that errors don't stop the worker."""
    client = MockGraphClient(fail_on={("fail", "me")})
    replicator = AsyncReplicator(client)
    
    await replicator.start()
    
    # Queue a mix of good and bad updates
    await replicator.enqueue(EdgeUpdate("a", "b", delta=1.0, max_weight=100.0))
    await replicator.enqueue(EdgeUpdate("fail", "me", delta=1.0, max_weight=100.0))  # Will fail
    await replicator.enqueue(EdgeUpdate("c", "d", delta=1.0, max_weight=100.0))
    
    # Give worker time to process all items
    await asyncio.sleep(0.1)
    await replicator.flush()
    
    # Should have processed the successful ones
    assert len(client.calls) == 2
    assert client.calls[0]["source"] == "a"
    assert client.calls[1]["source"] == "c"
    
    await replicator.stop()


async def test_flush_waits_for_completion():
    """Test that flush blocks until all updates are processed."""
    client = MockGraphClient(delay=0.01)  # Small delay
    replicator = AsyncReplicator(client)
    
    await replicator.start()
    
    for i in range(5):
        await replicator.enqueue(EdgeUpdate(f"s{i}", f"t{i}", delta=1.0, max_weight=100.0))
    
    await replicator.flush()
    
    # All should be processed
    assert len(client.calls) == 5
    assert replicator.pending_count() == 0
    
    await replicator.stop()


async def test_stop_without_start():
    """Test that stop is safe to call without start."""
    client = MockGraphClient()
    replicator = AsyncReplicator(client)
    
    # Should not raise
    await replicator.stop()
    assert replicator._task is None


async def test_multiple_start_calls():
    """Test that multiple start calls don't create multiple workers."""
    client = MockGraphClient()
    replicator = AsyncReplicator(client)
    
    await replicator.start()
    task1 = replicator._task
    
    await replicator.start()  # Second call
    task2 = replicator._task
    
    assert task1 is task2  # Same task
    
    await replicator.stop()
