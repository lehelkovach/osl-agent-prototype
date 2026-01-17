# Queue KnowShowGo Integration

## Overview

The task queue has been refactored to store queue items as **QueueItem concepts** in KnowShowGo semantic memory, rather than as JSON dictionaries in the queue node's props. This enables semantic search, better relationships, and proper integration with the knowledge graph.

## Changes Made

### TaskQueueManager Refactoring

**Before:**
- Queue items stored as JSON dictionaries in `queue.props["items"]`
- No semantic search capability
- No relationships to procedures/tasks
- Not part of the knowledge graph

**After:**
- Queue items stored as **QueueItem concepts** using the QueueItem prototype
- Semantic search via embeddings
- Proper edge relationships:
  - `queue -> queue_item` (contains edge)
  - `queue_item -> task/procedure` (references edge)
  - `queue_item -> procedure` (runsProcedure edge, when applicable)
- Full KnowShowGo integration

### Implementation Details

1. **QueueItem Prototype**
   - Uses KnowShowGo QueueItem prototype
   - Properties: `enqueuedAt`, `priority`, `state` (queued|running|done|failed), `context`
   - Supports `runsProcedure` relationship to procedures

2. **Queue Node**
   - Changed from `kind="Queue"` to `kind="topic"` for KnowShowGo compatibility
   - No longer stores items in props
   - Acts as a container linked to QueueItem concepts via edges

3. **New Methods**
   - `list_items()`: Retrieve queue items as concepts with semantic search
   - `_get_queue_item_prototype_uuid()`: Get or create QueueItem prototype
   - `_sort_queue_items()`: Sort QueueItem nodes by priority/due/not_before

4. **State Management**
   - Queue items have proper state: `queued|running|done|failed`
   - State updates persist in the knowledge graph
   - Dequeue marks item as "running"

## Benefits

1. **Semantic Search**: Queue items are searchable via embeddings
2. **Better Relationships**: Queue items can link to procedures via `runsProcedure` edges
3. **KnowShowGo Integration**: Queue items are part of the semantic knowledge graph
4. **Knowledge Graph**: Queue items participate in the agent's knowledge representation
5. **State Management**: Proper state tracking with persistence

## Design Alignment

Aligned with **KnowShowGo v0.1** design:
- QueueItem prototype with properties: `enqueuedAt`, `priority`, `state`, `runsProcedure`, `context`
- Queue items stored as `topic` kind with `isPrototype=False`
- Proper edge relationships following KnowShowGo patterns

## API Changes

### Before
```python
queue = queue_manager.enqueue(task_node, provenance)
items = queue.props["items"]  # JSON dictionaries
```

### After
```python
queue = queue_manager.enqueue(task_node, provenance)
items = queue_manager.list_items(provenance)  # QueueItem concepts
```

## Migration

All existing code has been updated:
- `agent.py`: Updated to use `list_items()` instead of `queue.props["items"]`
- `scheduler.py`: Works with new queue API
- Tests: Updated to use new API

## Tests

All queue tests pass:
- `test_enqueue_and_sort`
- `test_enqueue_node_and_dequeue_with_edge`
- `test_enqueue_payload_with_delay_and_not_before_sorting`
- `test_queue_embedding_and_kind`
- `test_update_items`
- `test_update_status`

## Future Enhancements

Potential improvements:
- Semantic search for queue items by description
- Queue item relationships to other concepts
- Queue item history and provenance tracking
- Multi-queue support with semantic routing

