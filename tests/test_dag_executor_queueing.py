import json

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.dag_executor import DAGExecutor
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockContactsTools,
    MockWebTools,
)
from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.procedure_manager import ProcedureManager


def test_dag_executor_orders_by_dependencies():
    memory = MockMemoryTools()
    prov = Provenance("user", "2026-01-01T00:00:00Z", 1.0, "trace")
    concept = Node(
        kind="Concept",
        labels=["Procedure"],
        props={
            "name": "Queued Login",
            "steps": [
                {"id": "step_1", "tool": "web.get_dom", "params": {"url": "https://example.com"}, "depends_on": []},
                {"id": "step_2", "tool": "form.autofill", "params": {"url": "https://example.com"}, "depends_on": ["step_1"]},
                {"id": "step_3", "tool": "web.click_selector", "params": {"url": "https://example.com", "selector": "#submit"}, "depends_on": ["step_2"]},
            ],
        },
    )
    memory.upsert(concept, prov)

    enqueued = []

    def enqueue_cmd(cmd):
        enqueued.append(cmd.get("tool"))

    executor = DAGExecutor(memory)
    result = executor.execute_dag(concept.uuid, enqueue_fn=enqueue_cmd)

    assert result["status"] == "completed"
    assert result["execution_order"] == ["step_1", "step_2", "step_3"]
    assert enqueued == ["web.get_dom", "form.autofill", "web.click_selector"]


def test_agent_dag_execute_enqueues_queue_items():
    memory = MockMemoryTools()
    proc_manager = ProcedureManager(memory, embed_fn=lambda text: [0.1, 0.2])
    prov = Provenance("user", "2026-01-01T00:00:00Z", 1.0, "trace")
    procedure_json = {
        "name": "Queued Procedure",
        "description": "Queue each step",
        "steps": [
            {"id": "step_1", "tool": "web.get_dom", "params": {"url": "https://example.com"}, "depends_on": []},
            {"id": "step_2", "tool": "form.autofill", "params": {"url": "https://example.com"}, "depends_on": ["step_1"]},
            {"id": "step_3", "tool": "web.click_selector", "params": {"url": "https://example.com", "selector": "#submit"}, "depends_on": ["step_2"]},
        ],
    }
    proc_result = proc_manager.create_from_json(procedure_json, provenance=prov)
    proc_uuid = proc_result["procedure_uuid"]

    plan = {
        "intent": "task",
        "steps": [{"tool": "dag.execute", "params": {"concept_uuid": proc_uuid}}],
    }
    agent = PersonalAssistantAgent(
        memory,
        MockCalendarTools(),
        MockTaskTools(),
        web=MockWebTools(),
        contacts=MockContactsTools(),
        openai_client=FakeOpenAIClient(chat_response=json.dumps(plan), embedding=[0.1, 0.2]),
    )

    res = agent.execute_request("run queued procedure")
    step = res["execution_results"]["steps"][0]
    dag_result = step.get("dag_result", {})
    assert dag_result.get("execution_order") == ["step_1", "step_2", "step_3"]

    items = agent.queue_manager.list_items(
        Provenance("user", "2026-01-01T00:00:00Z", 1.0, "queue-test")
    )
    assert len(items) == 3
    task_nodes = [item.get("task_node") for item in items]
    tools = {node.props.get("tool") for node in task_nodes if node}
    assert tools == {"web.get_dom", "form.autofill", "web.click_selector"}
