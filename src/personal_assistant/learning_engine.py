"""
Enhanced learning engine for continual improvement through:
- LLM reasoning about failures and successes
- Transfer learning from similar cases
- Knowledge accumulation and pattern recognition
- Learning from user feedback and corrections
"""

from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timezone
import json

from src.personal_assistant.models import Node, Provenance
from src.personal_assistant.tools import MemoryTools
from src.personal_assistant.knowshowgo import KnowShowGoAPI


class LearningEngine:
    """
    Enhanced learning engine that uses LLM reasoning to:
    1. Analyze failures and extract lessons
    2. Transfer knowledge from similar successful cases
    3. Build up patterns and strategies
    4. Learn from user feedback
    """
    
    def __init__(
        self,
        memory: MemoryTools,
        ksg: KnowShowGoAPI,
        llm_client: Any,  # OpenAIClient or LLMClient
        embed_fn: Callable[[str], List[float]],
    ):
        self.memory = memory
        self.ksg = ksg
        self.llm_client = llm_client
        self.embed_fn = embed_fn
    
    def analyze_failure(
        self,
        user_request: str,
        plan: Dict[str, Any],
        execution_results: Dict[str, Any],
        similar_cases: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Use LLM to reason about why something failed and how to fix it.
        Returns analysis with lessons learned and suggested fixes.
        """
        error = execution_results.get("error", "")
        errors = execution_results.get("errors", [])
        error_text = error or (errors[0] if errors else "Execution failed")
        
        # Build context from similar cases
        similar_context = ""
        if similar_cases:
            similar_context = "\n\nSimilar successful cases:\n"
            for i, case in enumerate(similar_cases[:3], 1):
                case_desc = case.get("description") or case.get("name", "")
                similar_context += f"{i}. {case_desc}\n"
        
        analysis_prompt = f"""Analyze why this execution failed and how to fix it.

User Request: {user_request}

Plan Steps:
{json.dumps(plan.get("steps", []), indent=2)}

Error: {error_text}
{similar_context}

Provide analysis in JSON format:
{{
  "root_cause": "Brief explanation of why it failed",
  "lessons_learned": ["lesson1", "lesson2", ...],
  "suggested_fixes": [
    {{
      "step_index": 0,
      "fix": "What to change",
      "reason": "Why this fix should work"
    }}
  ],
  "transferable_knowledge": "What patterns/strategies can be learned from this",
  "confidence": 0.0-1.0
}}"""
        
        try:
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You are a learning system that analyzes failures and extracts lessons. Return only valid JSON."},
                    {"role": "user", "content": analysis_prompt}
                ],
                response_format={"type": "json_object"} if hasattr(self.llm_client, "chat") else None,
            )
            
            if isinstance(response, str):
                analysis = json.loads(response)
            else:
                analysis = response if isinstance(response, dict) else {}
            
            return {
                "status": "success",
                "analysis": analysis,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "fallback_analysis": {
                    "root_cause": error_text[:200],
                    "lessons_learned": ["Check selectors and URLs"],
                    "suggested_fixes": [{"step_index": 0, "fix": "Verify selectors match DOM", "reason": "Common failure point"}],
                }
            }
    
    def extract_transferable_knowledge(
        self,
        successful_cases: List[Dict[str, Any]],
        current_case: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Use LLM to extract transferable knowledge from similar successful cases.
        Identifies patterns, strategies, and reusable approaches.
        """
        if not successful_cases:
            return {"status": "no_cases", "knowledge": {}}
        
        cases_summary = ""
        for i, case in enumerate(successful_cases[:5], 1):
            case_name = case.get("name") or case.get("label", "")
            case_desc = case.get("description") or case.get("summary", "")
            case_steps = case.get("props", {}).get("steps", [])
            cases_summary += f"\nCase {i}: {case_name}\nDescription: {case_desc}\nSteps: {len(case_steps)} steps\n"
        
        current_desc = current_case.get("description") or current_case.get("name", "")
        
        extraction_prompt = f"""Extract transferable knowledge from these successful cases that can help with the current task.

Successful Cases:
{cases_summary}

Current Task: {current_desc}

Provide analysis in JSON format:
{{
  "common_patterns": ["pattern1", "pattern2", ...],
  "reusable_strategies": ["strategy1", "strategy2", ...],
  "key_insights": ["insight1", "insight2", ...],
  "applicable_approaches": [
    {{
      "approach": "Description of approach",
      "when_to_use": "When this approach works",
      "confidence": 0.0-1.0
    }}
  ],
  "generalized_steps": ["step1", "step2", ...]
}}"""
        
        try:
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You extract transferable knowledge and patterns from successful cases. Return only valid JSON."},
                    {"role": "user", "content": extraction_prompt}
                ],
                response_format={"type": "json_object"} if hasattr(self.llm_client, "chat") else None,
            )
            
            if isinstance(response, str):
                knowledge = json.loads(response)
            else:
                knowledge = response if isinstance(response, dict) else {}
            
            return {
                "status": "success",
                "knowledge": knowledge,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "knowledge": {
                    "common_patterns": ["Follow similar structure to successful cases"],
                    "reusable_strategies": ["Adapt selectors and URLs"],
                }
            }
    
    def learn_from_success(
        self,
        user_request: str,
        plan: Dict[str, Any],
        execution_results: Dict[str, Any],
        provenance: Provenance,
    ) -> Optional[str]:
        """
        Extract and store lessons learned from successful execution.
        Returns UUID of stored knowledge node.
        """
        # Extract what worked
        successful_steps = []
        for step_result in execution_results.get("steps", []):
            if step_result.get("status") == "success":
                successful_steps.append(step_result)
        
        if not successful_steps:
            return None
        
        # Use LLM to extract lessons
        success_prompt = f"""Extract lessons learned from this successful execution.

User Request: {user_request}

Successful Steps:
{json.dumps(successful_steps, indent=2)}

Provide analysis in JSON format:
{{
  "what_worked": ["thing1", "thing2", ...],
  "key_success_factors": ["factor1", "factor2", ...],
  "reusable_patterns": ["pattern1", "pattern2", ...],
  "best_practices": ["practice1", "practice2", ...]
}}"""
        
        try:
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You extract lessons and patterns from successful executions. Return only valid JSON."},
                    {"role": "user", "content": success_prompt}
                ],
                response_format={"type": "json_object"} if hasattr(self.llm_client, "chat") else None,
            )
            
            if isinstance(response, str):
                lessons = json.loads(response)
            else:
                lessons = response if isinstance(response, dict) else {}
            
            # Store as knowledge node
            knowledge_node = Node(
                kind="topic",
                labels=["Knowledge", "Lesson", "Success"],
                props={
                    "label": f"Lessons from: {user_request[:50]}",
                    "summary": "Lessons learned from successful execution",
                    "isPrototype": False,
                    "what_worked": lessons.get("what_worked", []),
                    "key_success_factors": lessons.get("key_success_factors", []),
                    "reusable_patterns": lessons.get("reusable_patterns", []),
                    "best_practices": lessons.get("best_practices", []),
                    "user_request": user_request,
                    "learned_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            
            knowledge_node.llm_embedding = self.embed_fn(user_request)
            self.memory.upsert(knowledge_node, provenance, embedding_request=True)
            
            return knowledge_node.uuid
        except Exception as e:
            return None
    
    def learn_from_user_feedback(
        self,
        user_feedback: str,
        original_request: str,
        plan: Dict[str, Any],
        execution_results: Dict[str, Any],
        provenance: Provenance,
    ) -> Optional[str]:
        """
        Learn from user corrections and feedback.
        Stores corrections as knowledge for future reference.
        """
        feedback_prompt = f"""Extract learning from user feedback/correction.

Original Request: {original_request}

Plan That Was Executed:
{json.dumps(plan.get("steps", []), indent=2)}

Execution Results:
{json.dumps(execution_results, indent=2)}

User Feedback/Correction: {user_feedback}

Provide analysis in JSON format:
{{
  "what_was_wrong": ["issue1", "issue2", ...],
  "correct_approach": "What should have been done",
  "lessons": ["lesson1", "lesson2", ...],
  "future_guidance": "How to handle similar cases in future"
}}"""
        
        try:
            response = self.llm_client.chat(
                messages=[
                    {"role": "system", "content": "You extract learning from user feedback and corrections. Return only valid JSON."},
                    {"role": "user", "content": feedback_prompt}
                ],
                response_format={"type": "json_object"} if hasattr(self.llm_client, "chat") else None,
            )
            
            if isinstance(response, str):
                learning = json.loads(response)
            else:
                learning = response if isinstance(response, dict) else {}
            
            # Store as correction/knowledge node
            correction_node = Node(
                kind="topic",
                labels=["Knowledge", "Correction", "UserFeedback"],
                props={
                    "label": f"Correction: {original_request[:50]}",
                    "summary": "Learning from user feedback",
                    "isPrototype": False,
                    "what_was_wrong": learning.get("what_was_wrong", []),
                    "correct_approach": learning.get("correct_approach", ""),
                    "lessons": learning.get("lessons", []),
                    "future_guidance": learning.get("future_guidance", ""),
                    "user_feedback": user_feedback,
                    "original_request": original_request,
                    "learned_at": datetime.now(timezone.utc).isoformat(),
                },
            )
            
            correction_node.llm_embedding = self.embed_fn(f"{original_request} {user_feedback}")
            self.memory.upsert(correction_node, provenance, embedding_request=True)
            
            return correction_node.uuid
        except Exception as e:
            return None
    
    def find_similar_knowledge(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Find similar knowledge/lessons from past experiences.
        """
        query_embedding = self.embed_fn(query)
        results = self.memory.search(
            query,
            top_k=top_k,
            query_embedding=query_embedding,
            filters={"kind": "topic"},
        )
        
        # Filter for knowledge/lesson nodes
        knowledge_results = []
        for r in results:
            labels = r.get("labels", []) if isinstance(r, dict) else getattr(r, "labels", [])
            if any(label in ["Knowledge", "Lesson", "Success", "Correction", "UserFeedback"] for label in labels):
                knowledge_results.append(r)
        
        return knowledge_results

