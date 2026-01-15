import json
import asyncio
from typing import Dict, Any, List, Optional
import re
import os
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from src.personal_assistant.prompts import SYSTEM_PROMPT, DEVELOPER_PROMPT
from src.personal_assistant.tools import MemoryTools, CalendarTools, TaskTools, WebTools, ShellTools
from src.personal_assistant.models import Edge, Node, Provenance
from src.personal_assistant.openai_client import OpenAIClient, FakeOpenAIClient
from src.personal_assistant.task_queue import TaskQueueManager
from src.personal_assistant.events import EventBus, NullEventBus
from src.personal_assistant.cpms_adapter import CPMSAdapter
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.dag_executor import DAGExecutor
from src.personal_assistant.form_filler import FormDataRetriever
from src.personal_assistant.form_fingerprint import compute_form_fingerprint
from src.personal_assistant.logging_setup import get_logger
from src.personal_assistant.learning_engine import LearningEngine
from src.personal_assistant.working_memory import WorkingMemoryGraph
from src.personal_assistant.deterministic_parser import (
    infer_concept_kind, quick_parse, is_obvious_intent, get_confidence_score
)

class PersonalAssistantAgent:
    """A personal assistant agent that follows a structured execution loop."""

    def __init__(
        self,
        memory: MemoryTools,
        calendar: CalendarTools,
        tasks: TaskTools,
        web: Optional[WebTools] = None,
        contacts: Optional["ContactsTools"] = None,
        shell: Optional[ShellTools] = None,
        cpms: Optional[CPMSAdapter] = None,
        procedure_builder: Optional[ProcedureBuilder] = None,
        openai_client: Optional[OpenAIClient] = None,
        event_bus: Optional[EventBus] = None,
        use_cpms_for_procs: Optional[bool] = None,
        use_cpms_for_forms: Optional[bool] = None,
        ksg: Optional[KnowShowGoAPI] = None,
        vision: Optional[Any] = None,
        messages: Optional[Any] = None,
    ):
        self.memory = memory
        self.calendar = calendar
        self.tasks = tasks
        self.web = web
        self.contacts = contacts
        self.shell = shell
        self.cpms = cpms
        self.procedure_builder = procedure_builder
        self.vision = vision
        self.messages = messages
        self.system_prompt = SYSTEM_PROMPT
        self.developer_prompt = DEVELOPER_PROMPT
        # Support both old OpenAIClient and new LLMClient interface
        from src.personal_assistant.llm_client import LLMClient
        if openai_client is None:
            from src.personal_assistant.openai_client import OpenAIClient
            self.openai_client = OpenAIClient()
        else:
            self.openai_client = openai_client
        self.ksg = ksg or KnowShowGoAPI(memory, embed_fn=self._embed_text)
        self.queue_manager = TaskQueueManager(memory, embed_fn=self._embed_text, ksg=self.ksg)
        self.event_bus: EventBus = event_bus or NullEventBus()
        self._last_procedure_matches: Optional[List[Dict[str, Any]]] = None
        self.form_retriever = FormDataRetriever(memory, embed_fn=self._embed_text)
        self.dag_executor = DAGExecutor(memory, queue_manager=self.queue_manager)
        self.log = get_logger("agent")
        # Enhanced learning engine for continual improvement
        from src.personal_assistant.learning_engine import LearningEngine
        self.learning_engine = LearningEngine(
            memory=memory,
            ksg=self.ksg,
            llm_client=self.openai_client,
            embed_fn=self._embed_text,
        )
        # Flag to route procedure ops through CPMS if present
        if use_cpms_for_procs is None:
            self.use_cpms_for_procs = os.getenv("USE_CPMS_FOR_PROCS") == "1"
        else:
            self.use_cpms_for_procs = use_cpms_for_procs

        # Flag to store CPMS-detected form patterns into KnowShowGo
        if use_cpms_for_forms is None:
            self.use_cpms_for_forms = os.getenv("USE_CPMS_FOR_FORMS") == "1"
        else:
            self.use_cpms_for_forms = use_cpms_for_forms
        # Flag to enable ask-user fallback on empty plans (default off to preserve legacy flows)
        self.ask_user_enabled = os.getenv("ASK_USER_FALLBACK") == "1"
        
        # Working memory for session-scoped activation (Hebbian reinforcement)
        reinforce_delta = float(os.getenv("WORKING_MEMORY_REINFORCE_DELTA", "1.0"))
        max_weight = float(os.getenv("WORKING_MEMORY_MAX_WEIGHT", "100.0"))
        self.working_memory = WorkingMemoryGraph(
            reinforce_delta=reinforce_delta,
            max_weight=max_weight
        )
        
        # Flag to use deterministic parser for obvious intents (skip LLM)
        self.skip_llm_for_obvious = os.getenv("SKIP_LLM_FOR_OBVIOUS_INTENTS") == "1"

    def execute_request(self, user_request: str) -> Dict[str, Any]:
        """
        Executes a user request by following the defined workflow.
        """
        trace_id = f"agent-{uuid4()}"
        provenance = Provenance(
            source="user",
            ts=datetime.now(timezone.utc).isoformat(),
            confidence=1.0,
            trace_id=trace_id,
        )

        # 0. Log user message into history
        self._log_message("user", user_request, provenance)
        self._emit("request_received", {"user_request": user_request, "trace_id": provenance.trace_id})

        # 1. Classify Intent (simple heuristic)
        intent = self._classify_intent(user_request)
        self.log.info("execute_request", intent=intent, user_request=user_request, trace_id=provenance.trace_id)

        # 2. Retrieve Memory (+ optional embedding) and supporting context
        query_embedding = self._embed_text(user_request)
        top_k = 50 if intent == "inform" else 5
        memory_results = self.memory.search(
            user_request, top_k=top_k, query_embedding=query_embedding
        )
        
        # Apply working memory activation boost to results
        memory_results = self._boost_by_activation(memory_results, query_uuid=provenance.trace_id)
        
        self.log.info(
            "memory_retrieved",
            results=len(memory_results),
            top_k=top_k,
            has_embedding=query_embedding is not None,
            trace_id=provenance.trace_id,
        )
        # Procedure reuse (embedding-aware)
        # #region agent log
        import json
        import time
        try:
            with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({"location": "agent.py:106", "message": "searching for procedures", "data": {"query": user_request[:100], "has_procedure_builder": self.procedure_builder is not None}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "procedure-recall", "hypothesisId": "D"}) + "\n")
        except Exception:
            pass
        # #endregion
        if self.procedure_builder:
            proc_matches = self.procedure_builder.search_procedures(user_request, top_k=3)
            # #region agent log
            try:
                with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"location": "agent.py:109", "message": "procedure search results", "data": {"matches_count": len(proc_matches), "match_titles": [m.get("title", "unknown")[:50] for m in proc_matches[:3]]}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "procedure-recall", "hypothesisId": "D"}) + "\n")
            except Exception:
                pass
            # #endregion
            self._last_procedure_matches = proc_matches
            memory_results.extend(proc_matches)
            self._emit(
                "procedure_recall",
                {
                    "query": user_request,
                    "matches": proc_matches,
                    "trace_id": provenance.trace_id,
                },
            )
        else:
            proc_matches = []

        # Concept search in KnowShowGo (embedding-based)
        concept_matches = []
        if self.ksg:
            try:
                concept_matches = self.ksg.search_concepts(
                    user_request, top_k=3, query_embedding=query_embedding
                )
                if concept_matches:
                    memory_results.extend(concept_matches)
                    self._emit(
                        "concept_recall",
                        {
                            "query": user_request,
                            "matches": concept_matches,
                            "trace_id": provenance.trace_id,
                        },
                    )
            except Exception as exc:
                self.log.warning(
                    "concept_search_error",
                    error=str(exc),
                    trace_id=provenance.trace_id,
                )
        self._emit(
            "rag_query",
            {
                "query": user_request,
                "top_k": 5,
                "has_embedding": query_embedding is not None,
                "results_count": len(memory_results),
                "trace_id": provenance.trace_id,
                "ts": provenance.ts,
            },
        )
        tasks_context = self.tasks.list() if self.tasks else []
        calendar_context = (
            self.calendar.list({"start": "1970-01-01", "end": "2100-01-01"})
            if self.calendar
            else []
        )
        contacts_context = self.contacts.list() if self.contacts else []

        # Direct note recall for concept-named queries
        if intent == "inform" and "note" in user_request.lower():
            target_name = None
            for token in user_request.replace("?", " ").split():
                if token.lower().startswith("concept-"):
                    target_name = token
                    break
            if target_name:
                try:
                    all_hits = self.memory.search("", top_k=500, filters=None, query_embedding=None)
                except Exception:
                    all_hits = []
                for item in all_hits:
                    props = item.get("props", {}) if isinstance(item, dict) else {}
                    if props.get("name") == target_name and isinstance(props.get("note"), str):
                        note_val = props["note"]
                        plan = {
                            "intent": "inform",
                            "fallback": True,
                            "raw_llm": note_val,
                            "steps": [],
                            "trace_id": provenance.trace_id,
                        }
                        self._log_message("assistant", note_val, provenance)
                        self._emit(
                            "plan_ready",
                            {
                                "plan": plan,
                                "raw_llm": note_val,
                                "trace_id": provenance.trace_id,
                                "fallback": True,
                            },
                        )
                        execution_results = {"status": "no action taken", "trace_id": provenance.trace_id}
                        self._emit(
                            "execution_completed",
                            {"plan": plan, "results": execution_results, "trace_id": provenance.trace_id},
                        )
                        return {"plan": plan, "execution_results": execution_results}

        # Quick memory answer path for simple inform queries (e.g., "what is my name?")
        recall_keywords = ("recall", "steps", "procedure", "workflow", "run", "execute")
        recall_like = any(k in user_request.lower() for k in recall_keywords)
        note_like = any(k in user_request.lower() for k in ("note", "concept", "about"))
        skip_memory_answer = recall_like and bool(proc_matches) and not note_like
        mem_answer = None if skip_memory_answer else self._answer_from_memory(intent, memory_results, user_request)
        if mem_answer:
            plan = {
                "intent": "inform",
                "fallback": True,
                "raw_llm": mem_answer,
                "steps": [],
                "trace_id": provenance.trace_id,
            }
            self._log_message("assistant", mem_answer, provenance)
            self._emit(
                "plan_ready",
                {
                    "plan": plan,
                    "raw_llm": mem_answer,
                    "trace_id": provenance.trace_id,
                    "fallback": True,
                },
            )
            execution_results = {"status": "no action taken", "trace_id": provenance.trace_id}
            self._emit(
                "execution_completed",
                {"plan": plan, "results": execution_results, "trace_id": provenance.trace_id},
            )
            return {"plan": plan, "execution_results": execution_results}

        # 3. Propose a Plan (LLM)
        try:
            plan, raw_llm = self._generate_plan(
                intent,
                user_request,
                memory_results,
                tasks_context,
                calendar_context,
                contacts_context,
                proc_matches,
            )
        except Exception as exc:
            self.log.error(
                "llm_plan_error",
                module="agent",
                function="execute_request",
                intent=intent,
                error=str(exc),
                trace_id=provenance.trace_id,
            )
            plan = self._reuse_or_fallback(intent, user_request, proc_matches, trace_id=provenance.trace_id)
            raw_llm = None
        if raw_llm:
            self._log_message("assistant", raw_llm, provenance)
        if plan.get("error") or not plan.get("steps"):
            plan = self._reuse_or_fallback(intent, user_request, proc_matches, trace_id=provenance.trace_id)
        if plan.get("fallback") or plan.get("reuse"):
            plan.setdefault("raw_llm", "Hello! I'm ready to help.")

        # Confidence/uncertainty handling: if we have no actionable steps after fallback/reuse
        # and the intent is not a direct "remember"/"task"/"schedule", ask the user for guidance.
        if (not plan.get("steps")) and intent not in ("remember", "task", "schedule"):
            base_msg = plan.get("raw_llm")
            clarification = (
                f"{base_msg} I need your instructions. Please describe the steps or procedure so I can save it and queue it."
                if base_msg
                else "Hello! I'm ready to help. I need your instructions. Please describe the steps or procedure so I can save it and queue it."
            )
            plan["fallback"] = True
            plan["raw_llm"] = clarification
            plan.setdefault("intent", intent)
            plan.setdefault("trace_id", provenance.trace_id)
            self._emit(
                "plan_ready",
                {
                    "plan": plan,
                    "raw_llm": clarification,
                    "trace_id": provenance.trace_id,
                    "fallback": True,
                },
            )
            execution_results = {"status": "ask_user", "trace_id": provenance.trace_id}
            self._emit(
                "execution_completed",
                {"plan": plan, "results": execution_results, "trace_id": provenance.trace_id},
            )
            plan["trace_id"] = provenance.trace_id
            execution_results["trace_id"] = provenance.trace_id
            return {"plan": plan, "execution_results": execution_results}

        self._emit(
            "plan_ready",
            {
                "plan": plan,
                "raw_llm": raw_llm,
                "trace_id": provenance.trace_id,
                "fallback": plan.get("fallback", False),
            },
        )
        self.log.debug(
            "plan_ready",
            module="agent",
            function="execute_request",
            intent=intent,
            fallback=plan.get("fallback", False),
            reuse=plan.get("reuse", False),
            trace_id=provenance.trace_id,
        )

        # 4. Execute via Tools with retry logic (1-3 attempts)
        execution_results = self._execute_plan(plan, provenance)
        max_adaptation_attempts = int(os.getenv("MAX_ADAPTATION_ATTEMPTS", "3"))
        adaptation_attempt = 0
        
        while execution_results.get("status") == "error" and adaptation_attempt < max_adaptation_attempts:
            adaptation_attempt += 1
            # #region agent log
            try:
                with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"location": "agent.py:335", "message": "execution failed, attempting adaptation", "data": {"attempt": adaptation_attempt, "max_attempts": max_adaptation_attempts, "error": str(execution_results.get("error", ""))[:200], "trace_id": provenance.trace_id}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "procedure-adapt", "hypothesisId": "F"}) + "\n")
            except Exception:
                pass
            # #endregion
            
            # Adaptation attempt: ask LLM to adjust based on the error context.
            err = execution_results.get("error", "")
            errors = execution_results.get("errors", [])
            error_text = err or (errors[0] if errors else "Execution failed")
            
            adapt_request = (
                f"{user_request}\n"
                f"Previous plan failed (attempt {adaptation_attempt}/{max_adaptation_attempts}) with error: {error_text}. "
                f"Adjust selectors/URLs/values and try again. If you're unsure, ask the user for guidance."
            )
            
            plan, raw_llm = self._generate_plan(
                intent,
                adapt_request,
                memory_results,
                tasks_context,
                calendar_context,
                contacts_context,
                proc_matches,
            )
            plan["adapted"] = True
            plan["adaptation_attempt"] = adaptation_attempt
            plan["raw_llm"] = raw_llm or plan.get("raw_llm")
            
            # #region agent log
            try:
                with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"location": "agent.py:360", "message": "adapted plan generated", "data": {"attempt": adaptation_attempt, "steps_count": len(plan.get("steps", [])), "has_procedure_create": any(s.get("tool") == "procedure.create" for s in plan.get("steps", []))}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "procedure-adapt", "hypothesisId": "F"}) + "\n")
            except Exception:
                pass
            # #endregion
            
            self._emit(
                "plan_ready",
                {
                    "plan": plan,
                    "raw_llm": plan.get("raw_llm"),
                    "trace_id": provenance.trace_id,
                    "fallback": plan.get("fallback", False),
                    "adaptation_attempt": adaptation_attempt,
                },
            )
            
            execution_results = self._execute_plan(plan, provenance)
            
            # If adaptation succeeded, break out of retry loop
            if execution_results.get("status") == "completed":
                self.log.info(
                    "adaptation_succeeded",
                    attempt=adaptation_attempt,
                    trace_id=provenance.trace_id,
                )
                break
        
        # If execution still failed after all retries, ask the user for guidance.
        if execution_results.get("status") == "error" and intent not in ("remember", "task", "schedule"):
            clarification = (
                f"I hit an error while executing the plan: {execution_results.get('error', '')}. "
                "Please provide the correct steps or selectors so I can try again."
            )
            plan["fallback"] = True
            plan["raw_llm"] = clarification
            plan.setdefault("intent", intent)
            plan.setdefault("trace_id", provenance.trace_id)
            execution_results = {"status": "ask_user", "trace_id": provenance.trace_id}
            # Emit input_needed event
            self._emit("input_needed", {
                "message": "Execution error. Need guidance to proceed.",
                "play_chime": True,
                "trace_id": provenance.trace_id
            })

        # If the plan carries a low confidence score, ask the user for approval before executing.
        try:
            confidence = float(plan.get("confidence"))
        except Exception:
            confidence = None
        if confidence is not None and confidence < float(os.getenv("PLAN_MIN_CONFIDENCE", 0.9)):
            summary = plan.get("raw_llm") or "I can attempt this, but confidence is low. Approve or provide corrections?"
            plan["fallback"] = True
            plan["raw_llm"] = summary + " (Awaiting your approval.)"
            plan.setdefault("intent", intent)
            plan.setdefault("trace_id", provenance.trace_id)
            execution_results = {"status": "ask_user", "trace_id": provenance.trace_id}
            # Emit input_needed event
            self._emit("input_needed", {
                "message": "Low confidence plan. Need approval to proceed.",
                "play_chime": True,
                "trace_id": provenance.trace_id
            })

        # Persist selector improvements back to stored procedures when reuse + fallbacks succeed.
        proc_uuid = plan.get("procedure_uuid")
        if proc_uuid and execution_results.get("status") == "completed":
            try:
                self._update_procedure_selectors(proc_uuid, execution_results)
            except Exception:
                pass

        # Persist executed plan as a Procedure with basic success/failure stats
        try:
            self._persist_procedure_run(user_request, plan, execution_results, provenance)
        except Exception:
            # Persistence should not break the main loop
            pass
        
        # Enhanced learning: Learn from success or failure
        if execution_results.get("status") == "completed":
            # Extract lessons from successful execution
            try:
                knowledge_uuid = self.learning_engine.learn_from_success(
                    user_request=user_request,
                    plan=plan,
                    execution_results=execution_results,
                    provenance=provenance,
                )
                if knowledge_uuid:
                    self.log.info(
                        "learned_from_success",
                        knowledge_uuid=knowledge_uuid,
                        trace_id=provenance.trace_id,
                    )
            except Exception as exc:
                self.log.warning(
                    "learning_from_success_failed",
                    error=str(exc),
                    trace_id=provenance.trace_id,
                )
            
            # Auto-generalize: If execution succeeded and multiple similar concepts were found,
            # automatically merge them into a generalized pattern
            if self.ksg:
                try:
                    self._auto_generalize_if_applicable(
                        concept_matches=concept_matches,
                        execution_results=execution_results,
                        provenance=provenance
                    )
                except Exception as exc:
                    self.log.warning(
                        "auto_generalize_error",
                        error=str(exc),
                        trace_id=provenance.trace_id,
                    )
        elif execution_results.get("status") == "error":
            # Store failure analysis for future reference (non-blocking)
            try:
                failure_analysis = self.learning_engine.analyze_failure(
                    user_request=user_request,
                    plan=plan,
                    execution_results=execution_results,
                    similar_cases=None,
                )
                if failure_analysis.get("status") == "success":
                    self.log.info(
                        "analyzed_failure",
                        trace_id=provenance.trace_id,
                        root_cause=failure_analysis.get("analysis", {}).get("root_cause", "")[:100],
                    )
            except Exception:
                pass  # Non-blocking
        
        self._emit(
            "execution_completed",
            {"plan": plan, "results": execution_results, "trace_id": provenance.trace_id},
        )
        self.log.debug(
            "execution_completed",
            module="agent",
            function="execute_request",
            status=execution_results.get("status"),
            trace_id=provenance.trace_id,
        )

        # 5. Write Back (already handled per tool)
        # Attach trace_id for downstream consumers
        plan["trace_id"] = provenance.trace_id
        if isinstance(execution_results, dict):
            execution_results.setdefault("trace_id", provenance.trace_id)
        return {"plan": plan, "execution_results": execution_results}

    def _classify_intent(self, user_request: str) -> str:
        """Simulates intent classification based on keywords."""
        text = user_request.lower()
        has_url = "http://" in text or "https://" in text or any(tld in text for tld in (".com", ".net", ".org", ".io", ".ai"))
        if (
            "remind me to" in text
            or "add task" in text
            or "create a task" in text
            or "task" in text
            or "todo" in text
            or "to-do" in text
        ):
            return "task"
        elif "schedule" in text or "meeting" in text:
            return "schedule"
        elif "remember" in text:
            return "remember"
        elif any(
            k in text
            for k in [
                "login",
                "log in",
                "log into",
                "sign in",
                "sign into",
                "procedure",
                "workflow",
                "automation",
                "web",
                "recall",
                "steps",
                "execute",
                "run",
                "screenshot",
                "capture",
            ]
        ):
            return "web_io"
        elif has_url:
            return "web_io"
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
        procedure_matches: list,
    ) -> (Dict[str, Any], Optional[str]):
        """Generates a plan by calling the LLM for structured JSON. Returns plan and raw LLM text."""
        def _prune(obj):
            if isinstance(obj, dict):
                pruned = {}
                for k, v in obj.items():
                    if k in ("llm_embedding", "embedding", "vector"):
                        continue
                    pruned[k] = _prune(v)
                return pruned
            if isinstance(obj, list):
                return [_prune(x) for x in obj[:5]]
            if hasattr(obj, "__dict__"):
                return _prune(obj.__dict__)
            return obj

        def _norm(obj):
            return _prune(obj)

        mem_payload = _norm(memory_results[:5])
        proc_payload = _norm(procedure_matches[:5])
        tasks_payload = _norm(tasks_context[:5])
        calendar_payload = _norm(calendar_context[:5])
        contacts_payload = _norm(contacts_context[:5])
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "system", "content": self.developer_prompt},
            {"role": "user", "content": f"User request: {user_request}"},
            {"role": "user", "content": f"Intent: {intent}"},
            {"role": "user", "content": f"Memory results: {json.dumps(mem_payload)}"},
            {"role": "user", "content": f"Procedure matches: {json.dumps(proc_payload)}"},
            {"role": "user", "content": f"Tasks context: {json.dumps(tasks_payload)}"},
            {
                "role": "user",
                "content": f"Calendar context: {json.dumps(calendar_payload)}",
            },
            {
                "role": "user",
                "content": f"Contacts context: {json.dumps(contacts_payload)}",
            },
            {
                "role": "user",
                "content": "Return a strict JSON plan object with intent and steps as described. No prose.",
            },
        ]
        try:
            llm_text = self.openai_client.chat(
                messages, temperature=0.0, response_format={"type": "json_object"}
            )
            plan_obj = self._parse_plan(llm_text, intent)
            plan_obj["raw_llm"] = llm_text
            self.log.debug(
                "llm_plan_success",
                module="agent",
                function="_generate_plan",
                intent=intent,
                raw_llm=llm_text,
            )
            return plan_obj, llm_text
        except Exception as e:
            # Emit LLM error to event bus
            self._emit(
                "llm_error",
                {
                    "error": str(e),
                    "raw_llm": locals().get("llm_text"),
                    "trace_id": None,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
            llm_text = locals().get("llm_text", None)
            self.log.error(
                "llm_plan_error",
                module="agent",
                function="_generate_plan",
                intent=intent,
                error=str(e),
                raw_llm=llm_text,
            )
            return {"intent": intent, "steps": [], "error": str(e)}, llm_text

    def _parse_plan(self, llm_text: str, intent: str) -> Dict[str, Any]:
        """
        Parse LLM output using the commandtype/metadata contract.
        Accepts:
          - {"commandtype":"procedure","metadata":{"steps":[...]}}
          - legacy {"intent":..., "steps":[...]}
        """
        try:
            obj = json.loads(llm_text)
        except Exception as exc:
            raise RuntimeError(f"Failed to parse plan JSON: {exc}")
        # Legacy path
        if "steps" in obj and "intent" in obj:
            obj.setdefault("intent", intent)
            return obj
        # New commandtype path
        if obj.get("commandtype") == "procedure":
            steps = obj.get("metadata", {}).get("steps", [])
            converted_steps = []
            for step in steps:
                if not isinstance(step, dict):
                    continue
                tool = step.get("commandtype")
                params = step.get("metadata", {}) or {}
                comment = step.get("comment", "")
                if tool:
                    converted_steps.append({"tool": tool, "params": params, "comment": comment})
            return {"intent": intent, "steps": converted_steps}
        raise RuntimeError("Unrecognized plan shape")

    def _execute_plan(self, plan: Dict[str, Any], provenance: Provenance) -> Dict[str, Any]:
        """Executes each step in the plan by calling the appropriate tool.
        Any tool error is surfaced so the planner can adapt."""
        results = []
        for step in plan.get("steps", []):
            tool_name = step.get("tool")
            params = dict(step.get("params") or {})
            ts = datetime.now(timezone.utc).isoformat()
            self.log.debug(
                "tool_start",
                module="agent",
                function="_execute_plan",
                tool=tool_name,
                params=params,
                trace_id=provenance.trace_id,
                ts=ts,
            )
            self._emit(
                "tool_start",
                {
                    "tool": tool_name,
                    "params": params,
                    "trace_id": provenance.trace_id,
                    "ts": ts,
                },
            )
            try:
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
                                "items": self.queue_manager.list_items(provenance),
                            },
                        )
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
                elif tool_name == "web.get" and self.web:
                    res = self.web.get(**params)
                elif tool_name == "web.post" and self.web:
                    res = self.web.post(**params)
                elif tool_name == "web.screenshot" and self.web:
                    res = self.web.screenshot(**params)
                elif tool_name == "web.get_dom" and self.web:
                    res = self.web.get_dom(**params)
                elif tool_name == "web.locate_bounding_box" and self.web:
                    res = self.web.locate_bounding_box(**params)
                    self._record_form_element(params, provenance, action="locate_bounding_box")
                elif tool_name == "web.click_selector" and self.web:
                    res = self.web.click_selector(**params)
                    self._record_form_element(params, provenance, action="click_selector")
                elif tool_name == "web.click_xpath" and self.web:
                    res = self.web.click_xpath(**params)
                    self._record_form_element(params, provenance, action="click_xpath")
                elif tool_name == "web.click_xy" and self.web:
                    res = self.web.click_xy(**params)
                elif tool_name == "web.fill" and self.web:
                    if "selectors" in params:
                        selectors = params.pop("selectors", {}) or {}
                        values = params.pop("values", params.get("data") or params.get("fields") or {})
                        url = params.get("url")
                        multi_res = []

                        def _fallback_selectors(field_name: str) -> List[str]:
                            if field_name.lower() in ("username", "email", "user"):
                                return [
                                    "input[type='email']",
                                    "input[type='text']",
                                    "#email",
                                    "#username",
                                    "input[name='email']",
                                    "input[name='username']",
                                ]
                            if field_name.lower() in ("password", "pass", "pwd"):
                                return ["input[type='password']", "#password", "input[name='password']"]
                            if field_name.lower() in ("card", "cardnumber", "cc", "cc_number", "creditcard"):
                                return [
                                    "input[autocomplete='cc-number']",
                                    "input[name*='card']",
                                    "#card",
                                    "input[type='tel']",
                                ]
                            if field_name.lower() in ("expiry", "exp", "expdate", "expiration"):
                                return [
                                    "input[autocomplete='cc-exp']",
                                    "input[name*='exp']",
                                    "#expiry",
                                ]
                            if field_name.lower() in ("cvc", "cvv", "securitycode", "code"):
                                return [
                                    "input[autocomplete='cc-csc']",
                                    "input[name*='cvc']",
                                    "input[name*='cvv']",
                                    "#cvc",
                                ]
                            return []

                        for field, sel in selectors.items():
                            val = ""
                            if isinstance(values, dict):
                                val = values.get(field, params.get("text") or "")
                            try:
                                single = self.web.fill(url=url, selector=sel, text=val)
                            except Exception as exc:
                                attempted = [sel]
                                single = {"status": "error", "error": str(exc), "selector": sel}
                                for fallback_sel in _fallback_selectors(field):
                                    if fallback_sel in attempted:
                                        continue
                                    try:
                                        single = self.web.fill(url=url, selector=fallback_sel, text=val)
                                        single["fallback_selector"] = fallback_sel
                                        break
                                    except Exception:
                                        attempted.append(fallback_sel)
                                single.setdefault("attempted_selectors", attempted)
                            single["field"] = field
                            multi_res.append(single)
                        res = {"status": "success", "fills": multi_res}
                    else:
                        res = self.web.fill(**params)
                    self._record_form_element(params, provenance, action="fill")
                elif tool_name == "web.wait_for" and self.web:
                    res = self.web.wait_for(**params)
                elif tool_name == "shell.run" and self.shell:
                    res = self.shell.run(**params)
                elif tool_name == "queue.enqueue":
                    delay_seconds = params.get("delay_seconds")
                    not_before = params.get("not_before")
                    if delay_seconds and not not_before:
                        try:
                            nb_dt = datetime.now(timezone.utc) + timedelta(seconds=float(delay_seconds))
                            not_before = nb_dt.isoformat()
                        except Exception:
                            not_before = None
                    title = params.get("title") or params.get("name") or "Task"
                    enqueue_res = self.queue_manager.enqueue_payload(
                        provenance=provenance,
                        title=title,
                        kind=params.get("kind", "Task"),
                        labels=params.get("labels"),
                        priority=params.get("priority"),
                        due=params.get("due"),
                        status=params.get("status", "pending"),
                        not_before=not_before,
                        props=params.get("props"),
                        create_edge=True,
                    )
                    res = {"status": "success", "queue": enqueue_res.props.get("items", [])}
                    self._emit(
                        "queue_updated",
                        {
                            "trace_id": provenance.trace_id,
                            "items": self.queue_manager.list_items(provenance),
                        },
                    )
                elif tool_name == "queue.update":
                    queue = self.queue_manager.update_items(params.get("items", []), provenance)
                    res = {"status": "success", "queue": self.queue_manager.list_items(provenance)}
                    self._emit(
                        "queue_updated",
                        {
                            "trace_id": provenance.trace_id,
                            "items": self.queue_manager.list_items(provenance),
                        },
                    )
                elif tool_name == "memory.remember":
                    res = self._remember_fact(params, provenance)
                elif tool_name == "cpms.create_procedure":
                    if not self.cpms:
                        res = {"status": "error", "error": "CPMS adapter not configured"}
                    else:
                        res = {"status": "success", "procedure": self.cpms.create_procedure(**params)}
                elif tool_name == "cpms.list_procedures":
                    if not self.cpms:
                        res = {"status": "error", "error": "CPMS adapter not configured"}
                    else:
                        res = {"status": "success", "procedures": self.cpms.list_procedures()}
                elif tool_name == "cpms.get_procedure":
                    if not self.cpms:
                        res = {"status": "error", "error": "CPMS adapter not configured"}
                    else:
                        res = {"status": "success", "procedure": self.cpms.get_procedure(**params)}
                elif tool_name == "cpms.create_task":
                    if not self.cpms:
                        res = {"status": "error", "error": "CPMS adapter not configured"}
                    else:
                        res = {"status": "success", "task": self.cpms.create_task(**params)}
                elif tool_name == "cpms.list_tasks":
                    if not self.cpms:
                        res = {"status": "error", "error": "CPMS adapter not configured"}
                    else:
                        res = {"status": "success", "tasks": self.cpms.list_tasks(**params)}
                elif tool_name == "procedure.create":
                    # #region agent log
                    try:
                        with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                            f.write(json.dumps({"location": "agent.py:827", "message": "procedure.create called", "data": {"title": params.get("title") or params.get("name", "unknown")[:50], "steps_count": len(params.get("steps", [])), "use_cpms": self.use_cpms_for_procs}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "procedure-create", "hypothesisId": "E"}) + "\n")
                    except Exception:
                        pass
                    # #endregion
                    if self.use_cpms_for_procs and self.cpms:
                        res = {"status": "success", "procedure": self.cpms.create_procedure(**params)}
                    elif self.procedure_builder:
                        norm_params = params.copy()
                        # Normalize to ProcedureBuilder signature (title instead of name)
                        if "name" in norm_params and "title" not in norm_params:
                            norm_params["title"] = norm_params.pop("name")
                        if "steps" in norm_params:
                            norm_steps = []
                            for idx, st in enumerate(norm_params.get("steps") or []):
                                norm_steps.append(
                                    {
                                        "title": st.get("title") or st.get("tool") or f"step-{idx}",
                                        "tool": st.get("tool"),
                                        "payload": {"tool": st.get("tool"), "params": st.get("params", {})},
                                        "order": st.get("order", idx),
                                    }
                                )
                            norm_params["steps"] = norm_steps
                        # #region agent log
                        try:
                            with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                                f.write(json.dumps({"location": "agent.py:848", "message": "creating procedure via ProcedureBuilder", "data": {"title": norm_params.get("title", "unknown")[:50]}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "procedure-create", "hypothesisId": "E"}) + "\n")
                        except Exception:
                            pass
                        # #endregion
                        procedure_result = self.procedure_builder.create_procedure(**norm_params)
                        # #region agent log
                        try:
                            with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                                f.write(json.dumps({"location": "agent.py:850", "message": "procedure created successfully", "data": {"procedure_uuid": procedure_result.get("procedure_uuid"), "steps_count": len(procedure_result.get("step_uuids", []))}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "procedure-create", "hypothesisId": "E"}) + "\n")
                        except Exception:
                            pass
                        # #endregion
                        res = {
                            "status": "success",
                            "procedure": procedure_result,
                        }
                    else:
                        res = {"status": "error", "error": "ProcedureBuilder not configured"}
                elif tool_name == "procedure.search":
                    if self.use_cpms_for_procs and self.cpms:
                        try:
                            procs = self.cpms.list_procedures()
                        except Exception as exc:
                            res = {"status": "error", "error": str(exc)}
                        else:
                            res = {"status": "success", "procedures": procs}
                    elif self.procedure_builder:
                        res = {
                            "status": "success",
                            "procedures": self.procedure_builder.search_procedures(**params),
                        }
                    else:
                        res = {"status": "error", "error": "ProcedureBuilder not configured"}
                elif tool_name == "ksg.create_prototype":
                    try:
                        proto_uuid = self.ksg.create_prototype(**params)
                        res = {"status": "success", "prototype_uuid": proto_uuid}
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "ksg.create_concept":
                    try:
                        concept_params = params.copy()
                        if not concept_params.get("prototype_uuid"):
                            # best-effort: use first prototype in memory
                            for node in self.memory.nodes.values():
                                if getattr(node, "kind", None) == "Prototype":
                                    concept_params["prototype_uuid"] = node.uuid
                                    break
                        concept_uuid = self.ksg.create_concept(**concept_params)
                        res = {"status": "success", "concept_uuid": concept_uuid}
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "ksg.create_concept_recursive":
                    try:
                        concept_params = params.copy()
                        if not concept_params.get("prototype_uuid"):
                            # best-effort: use first prototype in memory
                            for node in self.memory.nodes.values():
                                if getattr(node, "kind", None) == "Prototype":
                                    concept_params["prototype_uuid"] = node.uuid
                                    break
                        concept_uuid = self.ksg.create_concept_recursive(**concept_params)
                        res = {"status": "success", "concept_uuid": concept_uuid}
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "ksg.search_concepts":
                    try:
                        results = self.ksg.search_concepts(**params)
                        res = {"status": "success", "concepts": results}
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "ksg.store_cpms_pattern":
                    try:
                        pattern_uuid = self.ksg.store_cpms_pattern(**params)
                        res = {"status": "success", "pattern_uuid": pattern_uuid}
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "cpms.detect_form":
                    if not self.cpms:
                        res = {"status": "error", "error": "CPMS adapter not configured"}
                    else:
                        try:
                            # Extract HTML and screenshot from params
                            html = params.get("html") or params.get("dom") or ""
                            screenshot_path = params.get("screenshot_path") or params.get("screenshot")
                            url = params.get("url")
                            dom_snapshot = params.get("dom_snapshot")
                            concept_uuid = params.get("concept_uuid")
                            pattern_name = params.get("pattern_name")
                            form_type_hint = params.get("form_type")
                            reuse_min_score = float(params.get("reuse_min_score") or os.getenv("KSG_PATTERN_REUSE_MIN_SCORE", "2.0"))
                            
                            # Reuse-first: if we already have a stored CPMS pattern that matches this
                            # page strongly, return it immediately and avoid a CPMS call.
                            did_reuse = False
                            if self.use_cpms_for_forms and self.ksg and url and html:
                                try:
                                    best = self.ksg.find_best_cpms_pattern(
                                        url=url,
                                        html=html,
                                        form_type=form_type_hint,
                                        top_k=1,
                                    )
                                    if best and best[0].get("score", 0.0) >= reuse_min_score:
                                        concept = best[0].get("concept") or {}
                                        pdata = best[0].get("pattern_data") or {}
                                        res = {
                                            "status": "success",
                                            "pattern": pdata,
                                            "pattern_uuid": concept.get("uuid"),
                                            "reused": True,
                                            "reuse_score": best[0].get("score"),
                                        }
                                        # If a concept_uuid was provided, ensure it is linked (best-effort).
                                        if concept_uuid and concept.get("uuid"):
                                            try:
                                                self.ksg.add_association(
                                                    from_concept_uuid=concept_uuid,
                                                    to_concept_uuid=concept["uuid"],
                                                    relation_type="has_pattern",
                                                    strength=1.0,
                                                    props={"pattern_name": concept.get("props", {}).get("name") if isinstance(concept.get("props"), dict) else None},
                                                )
                                            except Exception:
                                                pass
                                        did_reuse = True
                                except Exception:
                                    # Ignore reuse errors; fall back to CPMS.
                                    pass

                            if not did_reuse:
                                pattern_data = self.cpms.detect_form_pattern(
                                    html=html,
                                    screenshot_path=screenshot_path,
                                    url=url,
                                    dom_snapshot=dom_snapshot
                                )
                                res = {"status": "success", "pattern": pattern_data}

                            # Optional: store pattern into KnowShowGo for future reuse (only when we detected anew).
                            if not did_reuse and self.use_cpms_for_forms and self.ksg and pattern_data:
                                try:
                                    # Attach deterministic fingerprint for later matching.
                                    if isinstance(pattern_data, dict) and url and html and "fingerprint" not in pattern_data:
                                        pattern_data["fingerprint"] = compute_form_fingerprint(url=url, html=html).to_dict()
                                    form_type = pattern_data.get("form_type") if isinstance(pattern_data, dict) else None
                                    safe_name = pattern_name or f"{url or 'unknown'}:{form_type or 'unknown'}"
                                    emb = self._embed_text(safe_name) or [0.0, 0.0]
                                    pattern_uuid = self.ksg.store_cpms_pattern(
                                        pattern_name=safe_name,
                                        pattern_data=pattern_data if isinstance(pattern_data, dict) else {"pattern": pattern_data},
                                        embedding=emb,
                                        concept_uuid=concept_uuid,
                                    )
                                    res["pattern_uuid"] = pattern_uuid
                                except Exception:
                                    # Don't fail tool execution if storage fails.
                                    pass
                        except Exception as exc:
                            res = {"status": "error", "error": str(exc)}
                elif tool_name == "vision.parse_screenshot" and self.vision:
                    try:
                        screenshot_path = params.get("screenshot_path") or params.get("screenshot")
                        query = params.get("query") or params.get("element")
                        url = params.get("url")
                        res = self.vision.parse_screenshot(screenshot_path, query, url)
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "message.detect_messages" and self.messages:
                    try:
                        url = params.get("url")
                        filters = params.get("filters")
                        res = self.messages.detect_messages(url, filters)
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "message.get_details" and self.messages:
                    try:
                        url = params.get("url")
                        message_id = params.get("message_id")
                        selector = params.get("selector")
                        res = self.messages.get_message_details(url, message_id, selector)
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "message.compose_response" and self.messages:
                    try:
                        message = params.get("message")
                        template = params.get("template")
                        custom_text = params.get("custom_text")
                        res = self.messages.compose_response(message, template, custom_text)
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "message.send_response" and self.messages:
                    try:
                        url = params.get("url")
                        response = params.get("response")
                        message = params.get("message")
                        res = self.messages.send_response(url, response, message)
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "dag.execute":
                    try:
                        concept_uuid = params.get("concept_uuid")
                        if not concept_uuid:
                            res = {"status": "error", "error": "concept_uuid required"}
                        else:
                            def enqueue_cmd(cmd: Dict[str, Any]):
                                # Enqueue tool command to priority queue
                                if self.queue_manager:
                                    # Create a Node for the queue item
                                    from src.personal_assistant.models import Node
                                    task_node = Node(
                                        kind="Task",
                                        labels=["dag_command"],
                                        props={
                                            "title": cmd.get("tool", "dag_command"),
                                            "priority": params.get("priority", 5),
                                            **cmd
                                        }
                                    )
                                    self.queue_manager.enqueue(task_node, provenance)
                            result = self.dag_executor.execute_dag(concept_uuid, context=params.get("context"), enqueue_fn=enqueue_cmd)
                            res = {"status": "success", "dag_result": result}
                            
                            # Check if execution failed and trigger adaptation
                            if result.get("status") == "error" or result.get("errors"):
                                # Store user_request in plan for adaptation context
                                if not hasattr(plan, 'get'):
                                    plan = {"user_request": None}
                                self._adapt_procedure_on_failure(concept_uuid, result, provenance, user_request=plan.get("user_request"))
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                        # Trigger adaptation on exception
                        concept_uuid = params.get("concept_uuid")
                        if concept_uuid:
                            self._adapt_procedure_on_failure(concept_uuid, {"status": "error", "error": str(exc)}, provenance, user_request=plan.get("user_request"))
                elif tool_name == "vault.query_credentials":
                    try:
                        # Query vault for credentials associated with a concept or URL
                        query = params.get("query") or params.get("url") or ""
                        concept_uuid = params.get("concept_uuid")
                        results = self.memory.search(
                            query, top_k=5, filters={"kind": "Credential"}, query_embedding=self._embed_text(query) if query else None
                        )
                        # Also check for Identity/PaymentMethod if needed
                        if params.get("include_identity"):
                            identity_results = self.memory.search(
                                query, top_k=3, filters={"kind": "Identity"}, query_embedding=self._embed_text(query) if query else None
                            )
                            results.extend(identity_results)
                        res = {"status": "success", "credentials": results}
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "ksg.generalize_concepts":
                    try:
                        parent_uuid = self.ksg.generalize_concepts(**params)
                        res = {"status": "success", "generalized_concept_uuid": parent_uuid}
                    except Exception as exc:
                        res = {"status": "error", "error": str(exc)}
                elif tool_name == "form.autofill":
                    res = self._autofill_form(params)
                elif tool_name == "billing.submit_and_verify":
                    res = self._billing_submit_and_verify(params, provenance)
                elif tool_name == "billing.prompt_for_data":
                    res = self._billing_prompt_for_data(params)
                else:
                    res = {"status": "no action taken", "tool": tool_name}
            except Exception as exc:
                return {
                    "status": "error",
                    "error": str(exc),
                    "tool": tool_name,
                    "params": params,
                    "trace_id": provenance.trace_id,
                }
            results.append(res)
            # Safely log result (avoid circular references)
            try:
                safe_result = json.loads(json.dumps(res, default=str))
            except (TypeError, ValueError):
                safe_result = {"status": res.get("status") if isinstance(res, dict) else "unknown"}
            self.log.debug(
                "tool_result",
                module="agent",
                function="_execute_plan",
                tool=tool_name,
                params=params,
                result=safe_result,
                trace_id=provenance.trace_id,
                ts=datetime.now(timezone.utc).isoformat(),
            )
            # Emit tool invocation event with params and result
            self._emit(
                "tool_invoked",
                {
                    "tool": tool_name,
                    "params": params,
                    "result": res,
                    "trace_id": provenance.trace_id,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
        if not results:
            return {"status": "no action taken"}
        return {"status": "completed", "steps": results}

    def _task_to_node(self, task_data: Dict[str, Any]) -> Node:
        return Node(kind="Task", labels=[task_data.get("title", "task")], props=task_data)

    def _remember_fact(self, params: Dict[str, Any], provenance: Provenance) -> Dict[str, Any]:
        """
        Store a fact/claim as a concept node with an embedding, suitable for later RAG.
        params: {"text": str, "kind": optional str, "labels": optional list[str], "props": optional dict}
        """
        text = params.get("text") or params.get("content") or ""
        if not text:
            return {"status": "error", "error": "text required"}
        kind = params.get("kind", "Concept")
        labels = params.get("labels", ["fact"])
        extra_props = params.get("props", {})

        created = []
        # Always create the primary node according to requested kind/labels/props
        node = Node(
            kind=kind,
            labels=labels,
            props={"content": text, **extra_props},
        )
        node.llm_embedding = self._embed_text(node.props.get("name") or text)
        self.memory.upsert(node, provenance, embedding_request=True)
        self._emit_memory_upsert(node, provenance)
        # Additionally, if a name is present in the text, create supplemental Person/Name nodes
        person_name = self._extract_person_name(text)
        if person_name:
            name_node = Node(
                kind="Name",
                labels=["tag", "name"],
                props={"value": person_name},
            )
            name_node.llm_embedding = self._embed_text(person_name)
            try:
                self.memory.upsert(name_node, provenance, embedding_request=True)
                self._emit_memory_upsert(name_node, provenance)
                created.append(name_node.uuid)
            except Exception:
                pass
            person_node = Node(
                kind="Person",
                labels=["fact", "person"],
                props={"name": person_name, "source_text": text},
            )
            person_node.llm_embedding = self._embed_text(person_name)
            try:
                self.memory.upsert(person_node, provenance, embedding_request=True)
                self._emit_memory_upsert(person_node, provenance)
                created.append(person_node.uuid)
            except Exception:
                pass
        return {"status": "success", "uuid": node.uuid, "kind": node.kind, "extra": created}

    def _autofill_form(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Autofill a form using stored FormData/Identity/Credential/PaymentMethod concepts.
        params:
          - url: str
          - selectors: optional {field: selector} (direct fill)
          - required_fields: optional [field]
          - query: optional str (memory query)
          - form_type: optional str (login/billing/etc.)
          - reuse_min_score: optional float (for pattern reuse)
        """
        if not self.web:
            return {"status": "error", "error": "WebTools not configured"}
        url = params.get("url") or ""
        if not url:
            return {"status": "error", "error": "url required"}

        # If selectors were explicitly provided, keep the legacy behavior:
        # fill exactly those selectors using values from memory.
        selectors = params.get("selectors") or {}
        if selectors:
            required_fields = params.get("required_fields") or list(selectors.keys())
            query = params.get("query", "form data")
            fill_map = self.form_retriever.build_autofill(required_fields=required_fields, query=query)
            filled = []
            for field, selector in selectors.items():
                val = fill_map.get(field)
                if val is None:
                    continue
                res = self.web.fill(url=url, selector=selector, text=str(val))
                filled.append({"field": field, "value": val, "selector": selector, "result": res})
            return {"status": "success", "filled": filled}

        # Otherwise, derive selectors from stored patterns (reuse-first) or CPMS detection.
        dom = self.web.get_dom(url)
        html = dom.get("html") or dom.get("body") or ""
        screenshot_path = dom.get("screenshot_path")

        form_type = params.get("form_type")
        reuse_min_score = float(params.get("reuse_min_score") or os.getenv("KSG_PATTERN_REUSE_MIN_SCORE", "2.0"))

        reused = False
        pattern_uuid = None
        pattern_data: Optional[Dict[str, Any]] = None

        # Reuse-first: consult KSG before calling CPMS.
        if self.use_cpms_for_forms and self.ksg and html:
            try:
                best = self.ksg.find_best_cpms_pattern(url=url, html=html, form_type=form_type, top_k=1)
                if best and best[0].get("score", 0.0) >= reuse_min_score:
                    concept = best[0].get("concept") or {}
                    pdata = best[0].get("pattern_data") or {}
                    if isinstance(pdata, dict):
                        pattern_data = pdata
                        pattern_uuid = concept.get("uuid")
                        reused = True
            except Exception:
                pass

        if not pattern_data:
            if not self.cpms:
                return {"status": "error", "error": "No stored pattern match and CPMS adapter not configured"}
            pattern_data = self.cpms.detect_form_pattern(html=html, screenshot_path=screenshot_path, url=url, dom_snapshot=None)
            reused = False

            # Store exemplar for future reuse.
            if self.use_cpms_for_forms and self.ksg and isinstance(pattern_data, dict):
                try:
                    if "fingerprint" not in pattern_data and html:
                        pattern_data["fingerprint"] = compute_form_fingerprint(url=url, html=html).to_dict()
                    safe_name = params.get("pattern_name") or f"{url}:{pattern_data.get('form_type', form_type or 'unknown')}"
                    emb = self._embed_text(safe_name) or [0.0, 0.0]
                    pattern_uuid = self.ksg.store_cpms_pattern(
                        pattern_name=safe_name,
                        pattern_data=pattern_data,
                        embedding=emb,
                        concept_uuid=params.get("concept_uuid"),
                    )
                except Exception:
                    pass

        # Build selector map from the pattern.
        selector_map: Dict[str, str] = {}
        fields = pattern_data.get("fields") if isinstance(pattern_data, dict) else None
        if isinstance(fields, list):
            for f in fields:
                if not isinstance(f, dict):
                    continue
                ftype = (f.get("type") or "unknown").strip()
                if ftype in ("submit", "button", "unknown"):
                    continue
                sel = f.get("selector") or ""
                if sel:
                    selector_map[ftype] = sel

        required_fields = params.get("required_fields") or list(selector_map.keys())
        query = params.get("query", "form data")

        # Gather values from memory with minimal synonym support.
        synonym_keys = {
            "email": ["email", "username"],
            "username": ["username", "email"],
            "password": ["password"],
        }

        nodes = self.form_retriever.fetch_latest(query=query, top_k=20)
        values_by_key: Dict[str, Any] = {}
        for node in nodes:
            props = node.get("props", {}) if isinstance(node, dict) else {}
            if not isinstance(props, dict):
                continue
            for k, v in props.items():
                if v is not None and k not in values_by_key:
                    values_by_key[k] = v

        filled: List[Dict[str, Any]] = []
        missing: List[str] = []
        for field in required_fields:
            selector = selector_map.get(field) or selectors.get(field)
            if not selector:
                missing.append(field)
                continue
            candidates = synonym_keys.get(field, [field])
            val = None
            for k in candidates:
                if k in values_by_key:
                    val = values_by_key[k]
                    break
            if val is None:
                missing.append(field)
                continue
            res = self.web.fill(url=url, selector=selector, text=str(val))
            filled.append({"field": field, "value": val, "selector": selector, "result": res})

        return {
            "status": "success",
            "filled": filled,
            "missing_fields": sorted(set(missing)),
            "pattern_uuid": pattern_uuid,
            "reused": reused,
        }

    def _billing_submit_and_verify(self, params: Dict[str, Any], provenance: Provenance) -> Dict[str, Any]:
        """
        Submit a billing form and verify the payment result.
        
        params:
          - url: str - The checkout page URL
          - submit_selector: str - CSS selector for submit button (optional, auto-detect)
          - wait_ms: int - Time to wait after clicking (default 2000)
          
        Returns:
            - status: "success" | "failed" | "ask_user"
            - payment_status: "success" | "failed" | "unknown"
            - message: Description of the result
            - prompt: If failed, prompt for new billing data
        """
        if not self.web:
            return {"status": "error", "error": "WebTools not configured"}
        
        url = params.get("url")
        if not url:
            return {"status": "error", "error": "url required"}
        
        submit_selector = params.get("submit_selector")
        wait_ms = params.get("wait_ms", 2000)
        
        # If no submit selector provided, try common patterns
        if not submit_selector:
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                '#submit-btn',
                '.submit-button',
                'button:contains("Pay")',
                'button:contains("Submit")',
                'button:contains("Complete")',
            ]
            for sel in submit_selectors:
                try:
                    # Try to click the selector
                    click_result = self.web.click_selector(url=url, selector=sel)
                    if click_result.get("status") == "success" or click_result.get("clicked"):
                        submit_selector = sel
                        break
                except Exception:
                    continue
        else:
            # Click the provided selector
            self.web.click_selector(url=url, selector=submit_selector)
        
        # Wait for the page to process
        import time
        time.sleep(wait_ms / 1000.0)
        
        # Get the updated page content
        dom_result = self.web.get_dom(url)
        page_text = dom_result.get("text", "") or dom_result.get("body", "")
        page_html = dom_result.get("html", "")
        
        # Detect payment result
        payment_result = self.form_retriever.detect_payment_result(
            page_text=page_text,
            page_html=page_html
        )
        
        result = {
            "status": "success",
            "payment_status": payment_result["status"],
            "message": payment_result["message"],
            "confidence": payment_result["confidence"],
        }
        
        # If payment failed, add prompt for user
        if payment_result["status"] == "failed":
            result["status"] = "ask_user"
            result["prompt"] = self.form_retriever.build_payment_prompt(
                failure_reason=payment_result["reason"]
            )
            result["failure_reason"] = payment_result["reason"]
            
            # Log the failed attempt
            self.log.info(
                "billing_payment_failed",
                url=url,
                reason=payment_result["reason"],
                trace_id=provenance.trace_id,
            )
        elif payment_result["status"] == "success":
            self.log.info(
                "billing_payment_success",
                url=url,
                trace_id=provenance.trace_id,
            )
        
        # Take a screenshot of the result
        try:
            screenshot = self.web.screenshot(url=url)
            result["screenshot"] = screenshot.get("path") or screenshot.get("screenshot_path")
        except Exception:
            pass
        
        return result
    
    def _billing_prompt_for_data(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a prompt asking the user for billing/payment information.
        
        params:
          - failure_reason: str - Why the previous attempt failed (optional)
          - missing_fields: list - Fields that need to be provided (optional)
          
        Returns:
            - status: "ask_user"
            - prompt: The prompt text to show the user
        """
        failure_reason = params.get("failure_reason")
        missing_fields = params.get("missing_fields", [])
        
        if failure_reason:
            prompt = self.form_retriever.build_payment_prompt(failure_reason=failure_reason)
        elif missing_fields:
            prompt = f"Please provide the following billing information:\n"
            for field in missing_fields:
                prompt += f"- {field.replace('_', ' ').title()}: \n"
        else:
            prompt = self.form_retriever.build_payment_prompt()
        
        return {
            "status": "ask_user",
            "prompt": prompt,
            "required_fields": missing_fields or [
                "card_number", "expiry", "cvv", "card_name",
                "billing_address", "city", "state", "zip", "country"
            ]
        }

    def _record_form_element(self, params: Dict[str, Any], provenance: Provenance, action: str) -> None:
        """
        Persist a lightweight FormElement concept for later exemplar reuse.
        """
        try:
            url = params.get("url") or params.get("page") or ""
            selector = params.get("selector") or params.get("xpath") or params.get("query") or ""
            if not url and not selector:
                return
            element = Node(
                kind="FormElement",
                labels=["form", "exemplar"],
                props={
                    "url": url,
                    "selector": selector,
                    "action": action,
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            )
            try:
                element.llm_embedding = self._embed_text(f"{selector} {url} {action}")
            except Exception:
                element.llm_embedding = None
            self.memory.upsert(element, provenance, embedding_request=True)
            self._emit_memory_upsert(element, provenance)
        except Exception:
            # Do not break the agent loop on exemplar logging
            return

    def _embed_text(self, text: str) -> Optional[List[float]]:
        if not text:
            return None
        try:
            return self.openai_client.embed(text)
        except Exception:
            return None

    # -------------------------------------------------------------------------
    # Working Memory Integration (Salvage Step D)
    # -------------------------------------------------------------------------
    
    def _boost_by_activation(self, results: List[Dict[str, Any]], query_uuid: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Boost search results by working memory activation.
        
        Adds an '_activation_boost' field to each result and optionally
        adjusts the score. Results are re-sorted by combined score.
        
        Args:
            results: List of search results (dicts with 'uuid' and optionally 'score')
            query_uuid: Optional query context UUID for linking
            
        Returns:
            Results with activation boost applied and re-sorted
        """
        if not results:
            return results
        
        activation_weight = 0.1  # Tunable: how much activation affects ranking
        
        for result in results:
            uuid = result.get("uuid")
            boost = 0.0
            if uuid:
                boost = self.working_memory.get_activation_boost(uuid, default=0.0)
            result["_activation_boost"] = boost
            # Combine with existing score if present
            if "score" in result:
                result["_boosted_score"] = result["score"] + (boost * activation_weight)
            else:
                result["_boosted_score"] = boost * activation_weight
        
        # Re-sort by boosted score (higher first)
        return sorted(results, key=lambda r: r.get("_boosted_score", 0), reverse=True)
    
    def _reinforce_selection(self, query_uuid: str, selected_uuid: str, seed_weight: float = 1.0) -> None:
        """
        Reinforce working memory when a concept/procedure is selected.
        
        Creates or strengthens the link between query context and selected item.
        Implements Hebbian learning: "neurons that fire together wire together".
        
        Args:
            query_uuid: The query/context UUID
            selected_uuid: The selected concept/procedure UUID
            seed_weight: Initial weight for new links (default 1.0)
        """
        self.working_memory.link(query_uuid, selected_uuid, seed_weight=seed_weight)
        self.log.debug(
            "working_memory_reinforced",
            query_uuid=query_uuid,
            selected_uuid=selected_uuid,
            new_weight=self.working_memory.get_weight(query_uuid, selected_uuid)
        )
    
    def _classify_intent_with_fallback(self, user_request: str) -> str:
        """
        Classify intent using deterministic parser first, then LLM for ambiguous cases.
        
        When SKIP_LLM_FOR_OBVIOUS_INTENTS=1, uses rule-based classification for
        obvious intents (events with time, questions, clear action verbs) to
        reduce API costs and improve response time.
        
        Args:
            user_request: The user's request text
            
        Returns:
            Intent string: "task", "event", "query", "procedure", or "inform"
        """
        # Try deterministic classification first
        kind = infer_concept_kind(user_request)
        
        # Check if it's obvious enough to skip LLM
        if self.skip_llm_for_obvious and is_obvious_intent(user_request, kind):
            confidence = get_confidence_score(user_request, kind)
            self.log.debug(
                "deterministic_intent_classification",
                kind=kind,
                confidence=confidence,
                skipped_llm=True
            )
            return kind
        
        # Fall back to LLM for complex/ambiguous cases
        return self._classify_intent(user_request)
    
    def _get_activated_concepts(self, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Get top activated concepts from working memory for context.
        
        Useful for providing recent context to the LLM planner.
        
        Args:
            top_k: Number of top activated concepts to return
            
        Returns:
            List of (uuid, activation) tuples for most activated concepts
        """
        return self.working_memory.get_top_activated(top_k=top_k)

    def _load_procedure_steps(self, proc: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Hydrate stored procedure steps from memory (ProcedureBuilder format).
        """
        proc_uuid = proc.get("uuid") or proc.get("_key")
        if not proc_uuid:
            return []
        try:
            all_steps = self.memory.search("", top_k=500, filters={"kind": "Step"}, query_embedding=None)
        except Exception:
            return []
        steps_with_order = []
        for st in all_steps:
            props = st.get("props", {}) if isinstance(st, dict) else {}
            if props.get("procedure_uuid") != proc_uuid:
                continue
            payload = props.get("payload") or {}
            tool = props.get("tool") or payload.get("tool") or props.get("title")
            params = {}
            if isinstance(payload, dict):
                params = payload.get("params") or {}
                # If params are absent but payload has fields (e.g., url), treat payload as params
                if not params:
                    params = {k: v for k, v in payload.items() if k not in ("tool", "params")}
            steps_with_order.append(
                (
                    props.get("order", 0),
                    {
                        "tool": tool,
                        "params": params or {},
                        "comment": f"Reused step {props.get('title') or tool}",
                    },
                )
            )
        # Sort by order if present
        steps_with_order.sort(key=lambda t: t[0])
        return [s for _, s in steps_with_order]

    def _update_procedure_selectors(self, proc_uuid: str, execution_results: Dict[str, Any]) -> None:
        """
        If a reused procedure succeeded using fallback selectors, persist those selectors back into the stored Step.
        """
        if not self.procedure_builder:
            return
        # Gather fallback selector updates from execution_results
        selector_updates: Dict[str, str] = {}
        for step_res in execution_results.get("steps", []):
            fills = step_res.get("fills") or []
            for fill in fills:
                if fill.get("fallback_selector") and fill.get("field"):
                    selector_updates[fill["field"]] = fill["fallback_selector"]
        if not selector_updates:
            return
        try:
            steps = self.memory.search("", top_k=500, filters={"kind": "Step"}, query_embedding=None)
        except Exception:
            return
        for st in steps:
            props = st.get("props", {}) if isinstance(st, dict) else {}
            if props.get("procedure_uuid") != proc_uuid:
                continue
            if props.get("tool") not in ("web.fill",):
                continue
            payload = props.get("payload") or {}
            params = payload.get("params") or {}
            selectors = params.get("selectors") or {}
            updated = False
            for field, new_sel in selector_updates.items():
                if field in selectors and selectors[field] != new_sel:
                    selectors[field] = new_sel
                    updated = True
            if updated:
                params["selectors"] = selectors
                payload["params"] = params
                props["payload"] = payload
                st["props"] = props
                try:
                    self.memory.upsert(
                        st,
                        Provenance(
                            source="user",
                            ts=datetime.now(timezone.utc).isoformat(),
                            confidence=1.0,
                            trace_id="proc-update",
                        ),
                        embedding_request=False,
                    )
                except Exception:
                    continue

    def _guard_allows(self, guard: Optional[Dict[str, Any]], last_result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Evaluate a simple guard dict:
          - {"type":"equals", "path":"status", "value":"success"}
          - {"type":"not_equals", "path":"status", "value":"error"}
          - {"type":"exists", "path":"params.selector"}
        """
        if not guard:
            return True
        gtype = guard.get("type")
        path = guard.get("path")
        target = guard.get("value")
        if not path or not gtype:
            return True
        def _get(d, path_str):
            cur = d or {}
            for part in path_str.split("."):
                if isinstance(cur, dict):
                    cur = cur.get(part)
                else:
                    return None
            return cur
        val = _get(last_result or {}, path)
        if gtype == "equals":
            return val == target
        if gtype == "not_equals":
            return val != target
        if gtype == "exists":
            return val is not None
        return True
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
        if intent == "remember":
            return {
                "intent": intent,
                "fallback": True,
                "raw_llm": "Got it, I'll remember that.",
                "steps": [
                    {
                        "tool": "memory.remember",
                        "params": {"text": user_request, "kind": "Concept", "props": {"note": user_request}},
                        "comment": "Fallback remember to store the fact.",
                    }
                ],
            }
        if intent == "task":
            return {
                "intent": intent,
                "fallback": True,
                "raw_llm": "Task noted. Adding to your queue.",
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
        if intent == "web_io":
            url = self._extract_url(user_request) or "about:blank"
            return {
                "intent": intent,
                "fallback": True,
                "raw_llm": "Inspecting the page and capturing a screenshot.",
                "steps": [
                    {"tool": "web.get_dom", "params": {"url": url}, "comment": "Fetch DOM for inspection"},
                    {"tool": "web.screenshot", "params": {"url": url}, "comment": "Capture page snapshot"},
                ],
            }
        if intent == "inform":
            return {
                "intent": intent,
                "fallback": True,
                "raw_llm": "Hello! I'm ready to help.",
                "steps": [],
            }
        return None

    def _auto_generalize_if_applicable(
        self,
        concept_matches: List[Dict[str, Any]],
        execution_results: Dict[str, Any],
        provenance: Provenance,
    ) -> None:
        """
        Auto-generalize via vector embeddings: If execution succeeded and 2+ similar concepts
        were found (matched via vector embedding similarity), automatically merge them into a
        generalized pattern.
        
        This implements automatic learning: when multiple similar procedures work,
        the agent learns a general pattern by:
        1. Averaging their vector embeddings dimension-wise to create a centroid embedding
        2. Creating a generalized concept with the averaged embedding
        3. Linking exemplars to the generalized pattern
        
        Only concepts with vector embeddings are used (those matched via embedding similarity).
        """
        # Only generalize if execution succeeded
        if execution_results.get("status") != "completed":
            return
        
        # Need at least 2 similar concepts to generalize
        if not concept_matches or len(concept_matches) < 2:
            return
        
        # Filter to concepts that have vector embeddings and are procedures/patterns
        # Only generalize concepts that were matched via embedding similarity (fuzzy matching)
        procedure_concepts = []
        for match in concept_matches:
            # Extract embedding (vector embedding for similarity matching)
            embedding = match.get("llm_embedding") if isinstance(match, dict) else getattr(match, "llm_embedding", None)
            if not embedding:
                continue  # Skip concepts without vector embeddings
            
            # Check if it's a procedure concept (has steps or is a procedure)
            props = match.get("props", {}) if isinstance(match, dict) else getattr(match, "props", {})
            if "steps" in props or props.get("name", "").lower().startswith(("login", "procedure", "task")):
                procedure_concepts.append(match)
        
        # Need at least 2 procedure concepts with vector embeddings
        if len(procedure_concepts) < 2:
            return
        
        # Extract concept UUIDs and vector embeddings
        # Only use concepts that have embeddings (matched via vector similarity)
        concept_uuids = []
        embeddings = []  # Vector embeddings list
        concept_names = []
        
        for concept in procedure_concepts[:3]:  # Limit to top 3 for generalization
            uuid_val = concept.get("uuid") if isinstance(concept, dict) else getattr(concept, "uuid", None)
            if not uuid_val:
                continue
            
            # Extract vector embedding (required for generalization)
            embedding = concept.get("llm_embedding") if isinstance(concept, dict) else getattr(concept, "llm_embedding", None)
            if not embedding or not isinstance(embedding, list):
                continue  # Must have vector embedding
            
            name = concept.get("props", {}).get("name") if isinstance(concept, dict) else getattr(concept, "props", {}).get("name", "")
            
            concept_uuids.append(uuid_val)
            embeddings.append(embedding)  # Store vector embedding
            concept_names.append(name)
        
        # Need at least 2 concepts with valid vector embeddings
        if len(concept_uuids) < 2 or len(embeddings) < 2:
            return
        
        # Average vector embeddings for generalized pattern
        # Vector embeddings are averaged dimension-wise to create a centroid embedding
        # This represents the "average" semantic meaning of the exemplars in embedding space
        def average_vector_embeddings(emb_list):
            """
            Average vector embeddings dimension-wise to create centroid.
            Returns a centroid embedding that represents the average semantic meaning
            in the embedding vector space.
            """
            if not emb_list:
                return None
            if len(emb_list) == 1:
                return emb_list[0]
            
            # Validate all embeddings have same dimensionality
            dim = len(emb_list[0])
            for emb in emb_list[1:]:
                if len(emb) != dim:
                    self.log.warning(
                        "embedding_dimension_mismatch",
                        expected_dim=dim,
                        actual_dim=len(emb),
                        trace_id=provenance.trace_id,
                    )
                    return emb_list[0]  # Return first if mismatch
            
            # Average each dimension: centroid of vector embeddings in embedding space
            # This creates a new embedding vector that is the average of the input vectors
            averaged = [sum(emb[i] for emb in emb_list) / len(emb_list) for i in range(dim)]
            return averaged
        
        # Create generalized embedding by averaging vector embeddings
        generalized_embedding = average_vector_embeddings(embeddings)
        if not generalized_embedding:
            self.log.warning(
                "generalization_no_embedding",
                trace_id=provenance.trace_id,
            )
            return
        
        # Extract common steps (simplified: use steps from first concept as template)
        # In a more sophisticated implementation, would compare and extract truly common steps
        first_concept = procedure_concepts[0]
        first_props = first_concept.get("props", {}) if isinstance(first_concept, dict) else getattr(first_concept, "props", {})
        common_steps = first_props.get("steps", [])
        
        # Create generalized name
        generalized_name = f"General {concept_names[0].split()[0] if concept_names else 'Procedure'}"
        if len(concept_names) > 1:
            # Try to find common prefix/pattern
            words = [name.split() for name in concept_names if name]
            if words:
                common_prefix = words[0][0] if words[0] else "General"
                generalized_name = f"General {common_prefix} Procedure"
        
        # Find Procedure prototype
        proto_uuid = None
        proto_results = self.memory.search("Procedure", top_k=1, filters={"kind": "Prototype"})
        if proto_results:
            proto_uuid = proto_results[0].get("uuid") if isinstance(proto_results[0], dict) else getattr(proto_results[0], "uuid", None)
        
        # Create generalized pattern using averaged vector embeddings
        try:
            generalized_uuid = self.ksg.generalize_concepts(
                exemplar_uuids=concept_uuids,
                generalized_name=generalized_name,
                generalized_description=f"Generalized pattern learned from {len(concept_uuids)} exemplars via vector embedding similarity",
                generalized_embedding=generalized_embedding,  # Averaged vector embedding
                prototype_uuid=proto_uuid,
                provenance=provenance,
            )
            
            self.log.info(
                "auto_generalized",
                module="agent",
                function="_auto_generalize_if_applicable",
                exemplar_count=len(concept_uuids),
                generalized_uuid=generalized_uuid,
                embedding_dim=len(generalized_embedding),
                trace_id=provenance.trace_id,
            )
            
            self._emit(
                "concept_generalized",
                {
                    "exemplar_uuids": concept_uuids,
                    "generalized_uuid": generalized_uuid,
                    "generalized_name": generalized_name,
                    "trace_id": provenance.trace_id,
                },
            )
        except Exception as exc:
            self.log.warning(
                "generalize_failed",
                error=str(exc),
                trace_id=provenance.trace_id,
            )

    def _adapt_procedure_on_failure(
        self,
        concept_uuid: str,
        execution_result: Dict[str, Any],
        provenance: Provenance,
        user_request: Optional[str] = None,
    ) -> None:
        """
        Adapt a procedure when execution fails.
        
        When a DAG execution fails, this method:
        1. Loads the original procedure concept
        2. Uses LLM to adapt it based on the error and user request
        3. Stores the adapted version
        4. Links it to the original (via previous_version_uuid)
        
        This implements automatic adaptation: when a procedure doesn't work,
        the agent learns by creating an adapted version.
        """
        try:
            # Load the original concept
            original_concept = self.memory.nodes.get(concept_uuid)
            if not original_concept:
                self.log.warning(
                    "adaptation_original_not_found",
                    concept_uuid=concept_uuid,
                    trace_id=provenance.trace_id,
                )
                return
            
            # Extract error information
            error_msg = execution_result.get("error", "")
            errors = execution_result.get("errors", [])
            error_text = error_msg or (errors[0] if errors else "Execution failed")
            
            # Get original procedure data
            original_props = original_concept.props
            original_steps = original_props.get("steps", [])
            original_name = original_props.get("name", "Procedure")
            original_desc = original_props.get("description", "")
            
            # Use LLM to adapt the procedure
            # For now, create a simple adapted version with error context
            # In a full implementation, would use LLM to intelligently adapt
            adapted_name = f"{original_name} (Adapted)"
            adapted_desc = f"Adapted version of {original_name}. Error: {error_text[:100]}"
            
            # Create adapted steps (simplified: same steps for now, but in real implementation
            # would use LLM to update URLs/selectors based on error and user_request)
            adapted_steps = original_steps.copy()
            
            # If user_request provides context (e.g., different URL), update steps
            if user_request:
                # Simple heuristic: if user_request mentions a URL, update first web.get step
                url_match = re.search(r'https?://[^\s]+', user_request)
                if url_match:
                    new_url = url_match.group(0)
                    for step in adapted_steps:
                        if step.get("tool") == "web.get" and "url" in step.get("params", {}):
                            step["params"]["url"] = new_url
                            break
            
            # Get prototype UUID
            proc_proto_uuid = None
            for node in self.memory.nodes.values():
                if node.kind == "Prototype" and node.props.get("name") == "Procedure":
                    proc_proto_uuid = node.uuid
                    break
            
            if not proc_proto_uuid:
                self.log.warning(
                    "adaptation_no_prototype",
                    trace_id=provenance.trace_id,
                )
                return
            
            # Create adapted concept
            adapted_json = {
                "name": adapted_name,
                "description": adapted_desc,
                "steps": adapted_steps,
                "original_uuid": concept_uuid,
                "adaptation_reason": error_text[:200],
            }
            
            # Generate embedding for adapted concept
            adapted_embedding = self._embed_text(f"{adapted_name} {adapted_desc} {user_request or ''}")
            
            # Store adapted version
            adapted_uuid = self.ksg.create_concept(
                prototype_uuid=proc_proto_uuid,
                json_obj=adapted_json,
                embedding=adapted_embedding,
                previous_version_uuid=concept_uuid,  # Link to original
            )
            
            # Create association edge from original to adapted
            self.ksg.add_association(
                from_uuid=concept_uuid,
                to_uuid=adapted_uuid,
                association_type="adapted_from",
                strength=0.8,
            )
            
            self.log.info(
                "adaptation_completed",
                original_uuid=concept_uuid,
                adapted_uuid=adapted_uuid,
                error=error_text[:100],
                trace_id=provenance.trace_id,
            )
        except Exception as exc:
            self.log.warning(
                "adaptation_failed",
                concept_uuid=concept_uuid,
                error=str(exc),
                trace_id=provenance.trace_id,
            )

    def _extract_url(self, text: str) -> Optional[str]:
        """Best-effort URL/domain extractor for web fallback."""
        # Simple domain/URL finder
        m = re.search(r"(https?://[\\w\\.-]+|[\\w\\.-]+\\.(com|net|org|io|ai))", text, re.IGNORECASE)
        if not m:
            return None
        url = m.group(1)
        if not url.startswith("http"):
            url = f"https://{url}"
        return url

    def _reuse_or_fallback(self, intent: str, user_request: str, proc_matches: list, trace_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Prefer reuse of a retrieved procedure if available; else fallback.
        """
        if proc_matches:
            proc = proc_matches[0]
            proc_uuid = proc.get("uuid")
            
            # Reinforce working memory when we select a procedure for reuse
            if proc_uuid and trace_id:
                self._reinforce_selection(trace_id, proc_uuid, seed_weight=2.0)
            
            steps = self._load_procedure_steps(proc)
            if steps:
                if len(steps) <= 1:
                    return {
                        "intent": intent,
                        "steps": [
                            {
                                "tool": "procedure.search",
                                "params": {"query": user_request, "top_k": 3},
                                "comment": f"Reuse procedure match {proc.get('props', {}).get('title', '')}",
                            }
                        ],
                        "reuse": True,
                        "procedure_uuid": proc.get("uuid"),
                        "raw_llm": f"Reusing stored procedure {proc.get('props', {}).get('title', '')}".strip(),
                    }
                return {
                    "intent": intent,
                    "steps": steps,
                    "reuse": True,
                    "procedure_uuid": proc.get("uuid"),
                    "raw_llm": f"Reusing stored procedure {proc.get('props', {}).get('title', '')}".strip(),
                }
            # Fallback to search if we cannot hydrate steps
            return {
                "intent": intent,
                "steps": [
                    {
                        "tool": "procedure.search",
                        "params": {"query": user_request, "top_k": 3},
                        "comment": f"Reuse procedure match {proc.get('props', {}).get('title', '')}",
                    }
                ],
                "reuse": True,
            }
        fallback = self._fallback_plan(intent, user_request)
        return fallback or {"intent": intent, "steps": [], "fallback": True}

    def _persist_procedure_run(
        self,
        user_request: str,
        plan: Dict[str, Any],
        execution_results: Dict[str, Any],
        provenance: Provenance,
    ) -> None:
        """
        Store an executed plan as a Procedure with simple success/failure stats.
        """
        if not self.procedure_builder:
            return
        # Avoid duplicating when plan explicitly created a procedure
        if any(step.get("tool") == "procedure.create" for step in plan.get("steps", [])):
            return
        # Try to find an existing procedure by embedding/text match
        existing_proc = self._find_existing_procedure(user_request)
        proc_uuid = existing_proc.get("uuid") if existing_proc else None
        steps = []
        for idx, step in enumerate(plan.get("steps", [])):
            title = step.get("tool") or f"step-{idx}"
            steps.append(
                {
                    "title": title,
                    "tool": step.get("tool"),
                    "payload": {"tool": step.get("tool"), "params": step.get("params", {})},
                    "order": idx,
                }
            )
        if not steps:
            return
        success = execution_results.get("status") == "completed"
        run_node = Node(
            kind="ProcedureRun",
            labels=["procedure_run"],
            props={
                "goal": user_request,
                "status": execution_results.get("status"),
                "success": success,
                "trace_id": provenance.trace_id,
                "ts": provenance.ts,
            },
        )
        run_node.llm_embedding = self._embed_text(user_request)
        self.memory.upsert(run_node, provenance, embedding_request=True)
        self._emit_memory_upsert(run_node, provenance)

        if not proc_uuid:
            extra_props = {
                "tested": True,
                "success_count": 1 if success else 0,
                "failure_count": 0 if success else 1,
                "last_status": execution_results.get("status"),
                "last_trace_id": provenance.trace_id,
                "goal": user_request,
            }
            created = self.procedure_builder.create_procedure(
                title=user_request[:120],
                description=user_request,
                steps=steps,
                dependencies=[],
                guards=None,
                provenance=provenance,
                extra_props=extra_props,
            )
            proc_uuid = created.get("procedure_uuid")
        else:
            # Update success/failure counters on existing procedure
            try:
                proc_node = self.memory.nodes.get(proc_uuid)
                if proc_node:
                    sc = int(proc_node.props.get("success_count", 0))
                    fc = int(proc_node.props.get("failure_count", 0))
                    if success:
                        sc += 1
                    else:
                        fc += 1
                    proc_node.props.update(
                        {
                            "tested": True,
                            "success_count": sc,
                            "failure_count": fc,
                            "last_status": execution_results.get("status"),
                            "last_trace_id": provenance.trace_id,
                            "goal": user_request,
                        }
                    )
                    self.memory.upsert(proc_node, provenance, embedding_request=False)
            except Exception:
                pass
        if proc_uuid:
            # Link run to procedure
            try:
                self.memory.upsert(
                    Edge(
                        from_node=run_node.uuid,
                        to_node=proc_uuid,
                        rel="run_of",
                        props={"success": success, "ts": provenance.ts},
                    ),
                    provenance,
                    embedding_request=False,
                )
            except Exception:
                pass

    def _find_existing_procedure(self, goal: str) -> Optional[Dict[str, Any]]:
        if not self.procedure_builder:
            return None
        try:
            matches = self.procedure_builder.search_procedures(goal, top_k=1)
        except Exception:
            return None
        return matches[0] if matches else None

    def _log_message(self, role: str, content: str, provenance: Provenance) -> None:
        """Persist conversation messages with embeddings into history."""
        # #region agent log
        import json
        import time
        try:
            with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({"location": "agent.py:1794", "message": "_log_message entry", "data": {"role": role, "content_len": len(content) if content else 0, "trace_id": provenance.trace_id}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "chat-history", "hypothesisId": "C"}) + "\n")
        except Exception:
            pass
        # #endregion
        if not content:
            return
        msg_node = Node(
            kind="Message",
            labels=["history", role],
            props={"role": role, "content": content, "ts": provenance.ts},
        )
        # #region agent log
        try:
            with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({"location": "agent.py:1801", "message": "generating embedding for message", "data": {"node_uuid": msg_node.uuid, "kind": msg_node.kind, "labels": msg_node.labels}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "chat-history", "hypothesisId": "C"}) + "\n")
        except Exception:
            pass
        # #endregion
        msg_node.llm_embedding = self._embed_text(content)
        # #region agent log
        try:
            with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                f.write(json.dumps({"location": "agent.py:1804", "message": "embedding generated, upserting to memory", "data": {"embedding_len": len(msg_node.llm_embedding) if msg_node.llm_embedding else 0}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "chat-history", "hypothesisId": "C"}) + "\n")
        except Exception:
            pass
        # #endregion
        try:
            self.memory.upsert(msg_node, provenance, embedding_request=True)
            # #region agent log
            try:
                with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"location": "agent.py:1807", "message": "message upserted to memory successfully", "data": {"node_uuid": msg_node.uuid, "memory_backend": type(self.memory).__name__}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "chat-history", "hypothesisId": "C"}) + "\n")
            except Exception:
                pass
            # #endregion
            self._emit(
                "message_logged",
                {"role": role, "content": content, "trace_id": provenance.trace_id, "ts": provenance.ts},
            )
        except Exception as e:
            # #region agent log
            try:
                with open(r"c:\Users\lehel\OneDrive\development\source\osl-agent-prototype\.cursor\debug.log", "a", encoding="utf-8") as f:
                    f.write(json.dumps({"location": "agent.py:1814", "message": "message upsert failed", "data": {"error": str(e)[:200]}, "timestamp": int(time.time() * 1000), "sessionId": "debug-session", "runId": "chat-history", "hypothesisId": "C"}) + "\n")
            except Exception:
                pass
            # #endregion
            # Do not fail the agent loop on logging errors
            pass

    def _answer_from_memory(
        self, intent: str, memory_results: List[Dict[str, Any]], user_request: Optional[str] = None
    ) -> Optional[str]:
        """Simple recall: if intent is inform and we have memory hits, surface the top match."""
        if intent != "inform" or not memory_results:
            return None
        lower_q = user_request.lower() if user_request else ""
        bias_procedure = any(
            kw in lower_q for kw in ("procedure", "steps", "workflow", "execute", "run", "recall", "credential", "login")
        )
        ask_for_name = any(
            kw in lower_q for kw in ("name", "who am", "what is my name", "my name")
        ) or (
            not user_request
            and any(
                (item.get("kind") if isinstance(item, dict) else getattr(item, "kind", None))
                in ("Person", "Name")
                for item in memory_results
            )
        )
        # If the query asks for a note or concept, surface note/description first
        bias_note = any(kw in lower_q for kw in ("note", "concept", "about"))
        prefer_fact = bias_note or "credential" in lower_q or "password" in lower_q or "login" in lower_q
        if bias_note:
            target_name = None
            if user_request:
                for token in user_request.replace("?", " ").split():
                    if token.lower().startswith("concept-"):
                        target_name = token
                        break
            for item in memory_results:
                props = item.get("props", {}) if isinstance(item, dict) else {}
                if target_name and props.get("name") == target_name and isinstance(props.get("note"), str):
                    return props["note"]
                for key in ("note", "description", "content"):
                    val = props.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            # Fallback: query concepts directly
            try:
                concept_hits = self.memory.search("", top_k=100, filters={"kind": "Concept"}, query_embedding=None)
            except Exception:
                concept_hits = []
            for item in concept_hits:
                props = item.get("props", {}) if isinstance(item, dict) else {}
                if target_name and props.get("name") == target_name and isinstance(props.get("note"), str):
                    return props["note"]
                for key in ("note", "description", "content"):
                    val = props.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
            # Last resort: scan all nodes for a note/description/content
            try:
                all_hits = self.memory.search("", top_k=500, filters=None, query_embedding=None)
            except Exception:
                all_hits = []
            for item in all_hits:
                props = item.get("props", {}) if isinstance(item, dict) else {}
                if target_name and props.get("name") == target_name and isinstance(props.get("note"), str):
                    return props["note"]
                for key in ("note", "description", "content"):
                    val = props.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        if bias_procedure:
            for item in memory_results:
                props = item.get("props", {}) if isinstance(item, dict) else {}
                kind = item.get("kind") if isinstance(item, dict) else getattr(item, "kind", None)
                if kind == "Procedure":
                    title = props.get("title") or props.get("name")
                    desc = props.get("description")
                    if title and desc:
                        return f"Procedure '{title}': {desc}"
                    if title:
                        return f"Procedure '{title}' recalled."
            for item in memory_results:
                props = item.get("props", {}) if isinstance(item, dict) else {}
                labels = item.get("labels", []) if isinstance(item, dict) else getattr(item, "labels", [])
                kind = item.get("kind") if isinstance(item, dict) else getattr(item, "kind", None)
                if kind == "Message" or "history" in labels:
                    continue
                for key in ("note", "description", "content"):
                    if isinstance(props.get(key), str) and props.get(key).strip():
                        return props.get(key).strip()
        if prefer_fact:
            for item in memory_results:
                props = item.get("props", {}) if isinstance(item, dict) else {}
                labels = item.get("labels", []) if isinstance(item, dict) else getattr(item, "labels", [])
                kind = item.get("kind") if isinstance(item, dict) else getattr(item, "kind", None)
                if kind == "Message" or "history" in labels:
                    continue
                for key in ("note", "description", "content"):
                    val = props.get(key)
                    if isinstance(val, str) and val.strip():
                        return val.strip()
        # Name recall only when user asks for it
        if ask_for_name:
            for item in memory_results:
                props = item.get("props", {}) if isinstance(item, dict) else {}
                if isinstance(props.get("name"), str) and props["name"].strip():
                    clean = props["name"].strip()
                    return f"Your name is {clean}."
                if isinstance(props.get("value"), str) and props["value"].strip():
                    clean = props["value"].strip()
                    return f"Your name is {clean}."
                for key in ("note", "description", "content", "title"):
                    val = props.get(key)
                    if isinstance(val, str):
                        extracted = self._extract_person_name(val)
                        if extracted:
                            return f"Your name is {extracted}."
            for kind in ("Person", "Name", "Concept"):
                try:
                    hits = self.memory.search("", top_k=50, filters={"kind": kind}, query_embedding=None)
                except Exception:
                    hits = []
                for item in hits:
                    props = item.get("props", {}) if isinstance(item, dict) else {}
                    if isinstance(props.get("name"), str) and props["name"].strip():
                        clean = props["name"].strip()
                        return f"Your name is {clean}."
                    if isinstance(props.get("value"), str) and props["value"].strip():
                        clean = props["value"].strip()
                        return f"Your name is {clean}."
                    for key in ("note", "description", "content", "title"):
                        val = props.get(key)
                        if isinstance(val, str):
                            extracted = self._extract_person_name(val)
                            if extracted:
                                return f"Your name is {extracted}."

        scored: List[tuple[int, str]] = []
        for item in memory_results:
            props = item.get("props", {}) if isinstance(item, dict) else {}
            labels = item.get("labels", []) if isinstance(item, dict) else []
            kind = item.get("kind") if isinstance(item, dict) else None
            text = None
            answer_text = None
            for key in ("content", "note", "title"):
                val = props.get(key)
                if isinstance(val, str) and val.strip():
                    text = val.strip()
                    break
            if not text:
                continue
            score = 0
            if kind == "Person":
                score += 4
            if kind == "Name":
                score += 3
            if kind == "Concept":
                score += 1
            if labels and "fact" in labels:
                score += 2
            lower = text.lower()
            if "name" in lower:
                score += 2
            if "my name is" in lower or "i am" in lower:
                score += 2
            if "remember" in lower:
                score += 1
            if score > 0:
                scored.append((score, answer_text or text))
        if not scored:
            return None
        scored.sort(key=lambda t: t[0], reverse=True)
        return scored[0][1]

    def _extract_person_name(self, text: str) -> Optional[str]:
        """Heuristic extraction of a person's name from a sentence."""
        patterns = [
            r"\bmy name is\s+([A-Za-z][A-Za-z\s'.-]{0,60})",
            r"\bmy name's\s+([A-Za-z][A-Za-z\s'.-]{0,60})",
            r"\bi am\s+([A-Za-z][A-Za-z\s'.-]{0,60})",
            r"\bi'm\s+([A-Za-z][A-Za-z\s'.-]{0,60})",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                name = m.group(1).strip()
                name = re.sub(r"[.,;:!?]+$", "", name).strip()
                if name:
                    return name
        return None
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
