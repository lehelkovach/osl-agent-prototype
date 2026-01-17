# End-to-End Continual Learning Tests

## Overview

The `tests/test_e2e_continual_learning.py` file contains comprehensive end-to-end tests that demonstrate the agent's continual learning capabilities. These tests verify that the agent can:

1. Learn from failures using LLM reasoning
2. Transfer knowledge across similar tasks
3. Learn from user feedback
4. Reuse survey answers across different forms
5. Complete full learning cycles (learn → fail → adapt → succeed → generalize)
6. Improve through multiple feedback cycles

## Test Suite

### `TestE2EContinualLearning`

#### `test_e2e_learn_from_failure_with_reasoning`
Demonstrates the agent learning from execution failures:
- Agent attempts a task with incorrect selectors
- Execution fails
- Learning engine analyzes the failure
- Agent adapts and retries with correct selectors
- Procedure is stored for future use

**Key Verification:**
- Learning engine is invoked
- Procedure is stored after successful adaptation
- Agent can recover from failures autonomously

#### `test_e2e_transfer_learning_across_sites`
Demonstrates knowledge transfer between similar tasks:
- Agent learns login procedure for site1.com
- Agent applies similar knowledge to site2.com
- Similar knowledge is found and reused

**Key Verification:**
- First login procedure is stored
- Second login uses transferred knowledge
- Similar knowledge is retrievable via semantic search

#### `test_e2e_learn_from_user_feedback`
Demonstrates learning from explicit user corrections:
- Agent attempts a task
- User provides feedback about correct selectors
- Feedback is stored as knowledge
- Corrections are retrievable for future tasks

**Key Verification:**
- User feedback is stored as knowledge
- Corrections can be found via semantic search
- Feedback improves future task execution

#### `test_e2e_survey_answer_reuse_workflow`
Demonstrates survey form recognition and answer reuse:
- Agent fills first survey and stores answers
- Agent recognizes similar survey form
- Agent reuses stored answers for similar questions

**Key Verification:**
- Survey responses are stored with question-answer pairs
- Similar questions are matched semantically
- Answers are reused across different forms

#### `test_e2e_full_learning_cycle`
Demonstrates the complete learning cycle:
1. **Learn**: Agent learns initial procedure
2. **Fail**: Agent attempts similar task, fails initially
3. **Adapt**: Agent adapts based on failure
4. **Succeed**: Agent succeeds with adapted procedure
5. **Generalize**: Multiple successes enable generalization

**Key Verification:**
- Procedures are learned and stored
- Failures trigger adaptation
- Successful adaptations are stored
- Knowledge accumulates over time

#### `test_e2e_continual_improvement_through_feedback`
Demonstrates iterative improvement through feedback:
- Initial attempt fails
- User provides feedback
- Second attempt uses learned knowledge
- Knowledge accumulates across multiple cycles

**Key Verification:**
- Feedback is incorporated into knowledge base
- Subsequent attempts use learned knowledge
- Knowledge accumulates and improves over time

### `TestE2ELiveLearning`

These tests are gated by the `TEST_LIVE_LEARNING=1` environment variable and can run with real services:

#### `test_live_learn_from_failure`
Live test with real LLM reasoning about failures.

#### `test_live_transfer_learning`
Live test with real knowledge transfer between tasks.

## Running the Tests

### Unit Tests (Mock Services)
```bash
poetry run pytest tests/test_e2e_continual_learning.py -v
```

### Live Tests (Real Services)
```bash
TEST_LIVE_LEARNING=1 poetry run pytest tests/test_e2e_continual_learning.py::TestE2ELiveLearning -v
```

### Live Test Script
The `scripts/test_e2e_learning_live.ps1` script provides a PowerShell interface for testing against a running daemon:

```powershell
.\scripts\test_e2e_learning_live.ps1 -BaseUrl "http://localhost:8000"
```

This script:
1. Tests learning from failure
2. Tests transfer learning
3. Tests user feedback integration
4. Tests survey answer reuse
5. Tests continual improvement

## Key Features Demonstrated

### 1. LLM-Driven Reasoning
The agent uses the LLM to reason about failures, extract lessons, and generate adapted plans.

### 2. Semantic Knowledge Retrieval
The agent uses embeddings to find similar knowledge across different contexts.

### 3. Adaptive Execution
The agent automatically adapts procedures when they fail, with up to 3 retry attempts.

### 4. User Feedback Integration
The agent learns from explicit user corrections and incorporates them into its knowledge base.

### 5. Transfer Learning
The agent transfers knowledge from similar tasks, reducing the need for repeated learning.

### 6. Survey Answer Reuse
The agent recognizes survey forms and reuses answers for semantically similar questions.

### 7. Continual Improvement
The agent accumulates knowledge over time, improving its performance through multiple learning cycles.

## Architecture

The tests use:
- **MockWebToolsWithLearning**: Simulates web interactions with learning scenarios
- **FakeOpenAIClient**: Provides controlled LLM responses for testing
- **MockMemoryTools**: In-memory knowledge graph for testing
- **LearningEngine**: Centralized learning logic for reasoning and knowledge transfer

## Future Enhancements

Potential additions to the test suite:
- Multi-step task learning
- Complex procedure generalization
- Cross-domain knowledge transfer
- Long-term memory persistence
- Real-world website testing
- Performance benchmarking

