# Enhanced Learning System

## Overview

The agent now includes an enhanced learning engine that enables continual improvement through:
- **LLM reasoning** about failures and successes
- **Transfer learning** from similar cases
- **Knowledge accumulation** and pattern recognition
- **Learning from user feedback** and corrections

## Key Components

### 1. LearningEngine (`src/personal_assistant/learning_engine.py`)

The `LearningEngine` provides four core capabilities:

#### `analyze_failure()`
- Uses LLM reasoning to analyze why something failed
- Identifies root causes and lessons learned
- Suggests fixes with reasoning
- Extracts transferable knowledge

#### `extract_transferable_knowledge()`
- Analyzes similar successful cases
- Identifies common patterns and strategies
- Extracts reusable approaches
- Provides guidance for current task

#### `learn_from_success()`
- Extracts lessons from successful executions
- Identifies what worked and why
- Stores reusable patterns and best practices
- Builds up knowledge base over time

#### `learn_from_user_feedback()`
- Learns from user corrections and feedback
- Identifies what was wrong
- Stores correct approaches
- Provides future guidance

#### `find_similar_knowledge()`
- Searches for similar knowledge/lessons from past experiences
- Uses semantic search with embeddings
- Returns relevant knowledge nodes

## Integration with Agent

The learning engine is integrated into the agent's execution loop:

### During Adaptation (Failure Recovery)

When execution fails, the agent:
1. Finds similar successful cases using `find_similar_knowledge()`
2. Analyzes the failure using `analyze_failure()` with LLM reasoning
3. Extracts transferable knowledge from similar cases
4. Uses this knowledge to build a better adaptation request
5. Retries with enhanced context

### After Success

When execution succeeds, the agent:
1. Extracts lessons using `learn_from_success()`
2. Stores knowledge for future reference
3. Auto-generalizes if multiple similar procedures worked

### User Feedback

Users can provide feedback via the `/chat` endpoint:
```json
{
  "message": "The selector should be #username, not #email",
  "feedback": "The selector should be #username, not #email",
  "trace_id": "agent-12345-..."
}
```

The agent will:
1. Learn from the feedback using `learn_from_user_feedback()`
2. Store the correction as knowledge
3. Apply it in future similar cases

## Example Workflow

1. **User**: "Login to example.com"
2. **Agent**: Attempts login, fails with "Selector not found"
3. **Learning Engine**: 
   - Analyzes failure: "Root cause: Wrong selector used"
   - Finds similar cases: "Previous login used #email selector"
   - Extracts knowledge: "Login forms typically use #email or input[type='email']"
4. **Agent**: Adapts plan with correct selector, retries
5. **Success**: Agent learns what worked and stores it

## Benefits

- **Continual Improvement**: Agent gets better over time
- **Transfer Learning**: Applies knowledge from similar cases
- **LLM Reasoning**: Uses AI to understand failures, not just templates
- **User Feedback Integration**: Learns from corrections
- **Knowledge Accumulation**: Builds up patterns and strategies

## Configuration

The learning engine is automatically initialized with the agent. No additional configuration needed.

## Testing

See `tests/test_agent_enhanced_learning.py` for comprehensive tests covering:
- LLM reasoning about failures
- Transfer learning from similar cases
- Learning from success
- Learning from user feedback

