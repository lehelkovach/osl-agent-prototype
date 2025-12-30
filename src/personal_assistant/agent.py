import json
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from src.personal_assistant.prompts import SYSTEM_PROMPT, DEVELOPER_PROMPT
from src.personal_assistant.tools import MemoryTools, CalendarTools, TaskTools, WebTools
from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.openai_client import OpenAIClient, FakeOpenAIClient
from src.personal_assistant.task_queue import TaskQueueManager
from src.personal_assistant.events import EventBus, NullEventBus

class PersonalAssistantAgent:
    """A personal assistant agent that follows a structured execution loop."""

    def __init__(
        self,
        memory: MemoryTools,
        calendar: CalendarTools,
        tasks: TaskTools,
        web: Optional[WebTools] = None,
        contacts: Optional["ContactsTools"] = None,
        openai_client: Optional[OpenAIClient] = None,
        event_bus: Optional[EventBus] = None,
    ):
        self.memory = memory
        self.calendar = calendar
        self.tasks = tasks
        self.web = web
        self.contacts = contacts
        self.system_prompt = SYSTEM_PROMPT
        self.developer_prompt = DEVELOPER_PROMPT
        self.openai_client: OpenAIClient = openai_client or OpenAIClient()
        self.queue_manager = TaskQueueManager(memory)
        self.event_bus: EventBus = event_bus or NullEventBus()

    def execute_request(self, user_request: str) -> Dict[str, Any]:
        """
        Executes a user request by following the defined workflow.
        """
        provenance = Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id="agent-trace-1",
        )

        # 0. Log user message into history
        self._log_message("user", user_request, provenance)
        self._emit("request_received", {"user_request": user_request, "trace_id": provenance.trace_id})

        # 1. Classify Intent (simple heuristic)
        intent = self._classify_intent(user_request)

        # 2. Retrieve Memory (+ optional embedding) and supporting context
        query_embedding = self._embed_text(user_request)
        memory_results = self.memory.search(
            user_request, top_k=5, query_embedding=query_embedding
        )
        self._emit(
            "rag_query",
            {
                "query": user_request,
                "top_k": 5,
                "has_embedding": query_embedding is not None,
                "results_count": len(memory_results),
                "trace_id": provenance.trace_id,
            },
        )
        tasks_context = self.tasks.list() if self.tasks else []
        calendar_context = (
            self.calendar.list({"start": "1970-01-01", "end": "2100-01-01"})
            if self.calendar
            else []
        )
        contacts_context = self.contacts.list() if self.contacts else []

        # 3. Propose a Plan (LLM)
        plan, raw_llm = self._generate_plan(
            intent,
            user_request,
            memory_results,
            tasks_context,
            calendar_context,
            contacts_context,
        )
        if raw_llm:
            self._log_message("assistant", raw_llm, provenance)
        if plan.get("error") or not plan.get("steps"):
            fallback = self._fallback_plan(intent, user_request)
            if fallback:
                plan = fallback
        self._emit(
            "plan_ready",
            {
                "plan": plan,
                "raw_llm": raw_llm,
                "trace_id": provenance.trace_id,
                "fallback": plan.get("fallback", False),
            },
        )

        # 4. Execute via Tools
        execution_results = self._execute_plan(plan, provenance)
        self._emit(
            "execution_completed",
            {"plan": plan, "results": execution_results, "trace_id": provenance.trace_id},
        )

        # 5. Write Back (already handled per tool)
        return {"plan": plan, "execution_results": execution_results}

    def _classify_intent(self, user_request: str) -> str:
        """Simulates intent classification based on keywords."""
        if "remind me to" in user_request or "add task" in user_request:
            return "task"
        elif "schedule" in user_request or "meeting" in user_request:
            return "schedule"
        elif "remember" in user_request:
            return "remember"
        else:
            return "inform"

    def _generate_plan(
        self,
        intent: str,
        user_request: str,
        memory_results: list,
        tasks_context: list,
        calendar_context: list,
        contacts_context: list,
    ) -> (Dict[str, Any], Optional[str]):
        """Generates a plan by calling the LLM for structured JSON. Returns plan and raw LLM text."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": self.developer_prompt},
            {"role": "user", "content": f"User request: {user_request}"},
            {"role": "user", "content": f"Intent: {intent}"},
            {"role": "user", "content": f"Memory results: {json.dumps(memory_results)}"},
            {"role": "user", "content": f"Tasks context: {json.dumps(tasks_context)}"},
            {
                "role": "user",
                "content": f"Calendar context: {json.dumps(calendar_context)}",
            },
            {
                "role": "user",
                "content": f"Contacts context: {json.dumps(contacts_context)}",
            },
            {
                "role": "user",
                "content": "Return a strict JSON plan object with intent and steps as described. No prose.",
            },
        ]
        try:
            llm_text = self.openai_client.chat(messages, temperature=0.0)
            return json.loads(llm_text), llm_text
        except Exception as e:
            llm_text = locals().get("llm_text", None)
            return {"intent": intent, "steps": [], "error": str(e)}, llm_text

    def _execute_plan(self, plan: Dict[str, Any], provenance: Provenance) -> Dict[str, Any]:
        """Executes each step in the plan by calling the appropriate tool."""
        results = []
        for step in plan.get("steps", []):
            tool_name = step.get("tool")
            params = step.get("params", {})
            if tool_name == "tasks.create":
                res = self.tasks.create(**params)
                if res.get("status") == "success" and "task" in res:
                    task_node = self._task_to_node(res["task"])
                    task_node.llm_embedding = self._embed_text(task_node.props.get("title", ""))
                    self.memory.upsert(task_node, provenance, embedding_request=True)
                    self._emit_memory_upsert(task_node, provenance)
                    queue = self.queue_manager.enqueue(task_node, provenance)
                    self._emit(
                        "queue_updated",
                        {
                            "trace_id": provenance.trace_id,
                            "task_uuid": task_node.uuid,
                            "items": queue.props.get("items", []),
                        },
                    )
                results.append(res)
            elif tool_name == "calendar.create_event":
                res = self.calendar.create_event(**params)
                if res.get("status") == "success" and "event" in res:
                    event_node = Node(
                        kind="Event",
                        labels=[res["event"]["title"]],
                        props=res["event"],
                    )
                    event_node.llm_embedding = self._embed_text(res["event"]["title"])
                    self.memory.upsert(event_node, provenance, embedding_request=True)
                    self._emit_memory_upsert(event_node, provenance)
                    self._emit(
                        "calendar_event_created",
                        {
                            "trace_id": provenance.trace_id,
                            "event": res["event"],
                        },
                    )
                results.append(res)
            elif tool_name == "contacts.create" and self.contacts:
                res = self.contacts.create(**params)
                if res.get("status") == "success" and "contact" in res:
                    contact_node = Node(
                        kind="Person",
                        labels=[res["contact"].get("name", "contact")],
                        props=res["contact"],
                    )
                    contact_node.llm_embedding = self._embed_text(
                        " ".join(
                            [
                                res["contact"].get("name", ""),
                                " ".join(res["contact"].get("emails", [])),
                                " ".join(res["contact"].get("phones", [])),
                            ]
                        )
                    )
                    self.memory.upsert(contact_node, provenance, embedding_request=True)
                    self._emit_memory_upsert(contact_node, provenance)
                results.append(res)
            elif tool_name == "web.get" and self.web:
                res = self.web.get(**params)
                results.append(res)
            elif tool_name == "web.post" and self.web:
                res = self.web.post(**params)
                results.append(res)
            elif tool_name == "web.screenshot" and self.web:
                res = self.web.screenshot(**params)
                results.append(res)
            elif tool_name == "web.get_dom" and self.web:
                res = self.web.get_dom(**params)
                results.append(res)
            elif tool_name == "web.locate_bounding_box" and self.web:
                res = self.web.locate_bounding_box(**params)
                results.append(res)
            elif tool_name == "web.click_selector" and self.web:
                res = self.web.click_selector(**params)
                results.append(res)
            elif tool_name == "web.click_xpath" and self.web:
                res = self.web.click_xpath(**params)
                results.append(res)
            elif tool_name == "web.click_xy" and self.web:
                res = self.web.click_xy(**params)
                results.append(res)
            elif tool_name == "web.fill" and self.web:
                res = self.web.fill(**params)
                results.append(res)
            elif tool_name == "web.wait_for" and self.web:
                res = self.web.wait_for(**params)
                results.append(res)
            elif tool_name == "queue.update":
                queue = self.queue_manager.update_items(params.get("items", []), provenance)
                res = {"status": "success", "queue": queue.props.get("items", [])}
                results.append(res)
                self._emit(
                    "queue_updated",
                    {
                        "trace_id": provenance.trace_id,
                        "items": queue.props.get("items", []),
                    },
                )
            else:
                results.append({"status": "no action taken", "tool": tool_name})
            # Emit tool invocation event with params and result
            self._emit(
                "tool_invoked",
                {
                    "tool": tool_name,
                    "params": params,
                    "result": results[-1] if results else {"status": "no action taken"},
                    "trace_id": provenance.trace_id,
                },
            )
        if not results:
            return {"status": "no action taken"}
        return {"status": "completed", "steps": results}

    def _task_to_node(self, task_data: Dict[str, Any]) -> Node:
        return Node(kind="Task", labels=[task_data.get("title", "task")], props=task_data)

    def _embed_text(self, text: str) -> Optional[List[float]]:
        if not text:
            return None
        try:
            return self.openai_client.embed(text)
        except Exception:
            return None

    def _fallback_plan(self, intent: str, user_request: str) -> Optional[Dict[str, Any]]:
        """
        Provide a basic deterministic plan when LLM planning fails.
        """
        if intent == "task":
            return {
                "intent": intent,
                "fallback": True,
                "steps": [
                    {
                        "tool": "tasks.create",
                        "params": {
                            "title": user_request,
                            "due": None,
                            "priority": 3,
                            "notes": "Created via fallback plan",
                            "links": [],
                        },
                        "comment": "Fallback task creation when LLM plan failed",
                    }
                ],
            }
        return None

    def _log_message(self, role: str, content: str, provenance: Provenance) -> None:
        """Persist conversation messages with embeddings into history."""
        if not content:
            return
        msg_node = Node(
            kind="Message",
            labels=["history", role],
            props={"role": role, "content": content, "ts": provenance.ts},
        )
        msg_node.llm_embedding = self._embed_text(content)
        try:
            self.memory.upsert(msg_node, provenance, embedding_request=True)
        except Exception:
            # Do not fail the agent loop on logging errors
            pass
        self._emit(
            "message_logged",
            {
                "role": role,
                "content": content,
                "ts": provenance.ts,
                "trace_id": provenance.trace_id,
            },
        )

    def _emit(self, event_type: str, payload: Dict[str, Any]) -> None:
        """Emit events safely, supporting sync call sites."""
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.event_bus.emit(event_type, payload))
        except RuntimeError:
            # No running loop
            asyncio.run(self.event_bus.emit(event_type, payload))

    def _emit_memory_upsert(self, item: Node, provenance: Provenance) -> None:
        self._emit(
            "memory_upsert",
            {
                "uuid": item.uuid,
                "kind": item.kind,
                "labels": item.labels,
                "trace_id": provenance.trace_id,
            },
        )
