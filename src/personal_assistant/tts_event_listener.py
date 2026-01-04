"""
Event listener that integrates TTS with the agent's event bus.

Listens for agent events and announces them via TTS:
- tool_start: Announce step start
- tool_complete: Announce step completion
- execution_completed: Announce overall completion
- input_needed: Announce when input is required
"""

import logging
from typing import Dict, Any, Optional
from src.personal_assistant.tts_helper import get_tts, announce_step, announce_completion, announce_input_needed
from src.personal_assistant.events import Event, EventBus, Listener

logger = logging.getLogger(__name__)


class TTSEventListener:
    """Event listener that converts agent events to TTS announcements."""
    
    def __init__(self, tts=None):
        """
        Initialize TTS event listener.
        
        Args:
            tts: TTSHelper instance (if None, uses global instance)
        """
        self.tts = tts or get_tts()
        self.announce_tool_starts = True
        self.announce_tool_completions = True
        self.announce_execution_completion = True
        self.announce_errors = True
    
    async def on_tool_start(self, event: Event):
        """Handle tool_start events."""
        if not self.announce_tool_starts:
            return
        
        payload = event.payload
        tool = payload.get("tool", "unknown")
        params = payload.get("params", {})
        
        # Create concise description
        description = self._describe_tool_action(tool, params)
        self.tts.announce_step(f"Starting {description}", tool_name=tool)
    
    async def on_tool_complete(self, event: Event):
        """Handle tool_complete events."""
        if not self.announce_tool_completions:
            return
        
        payload = event.payload
        tool = payload.get("tool", "unknown")
        status = payload.get("status", "unknown")
        result = payload.get("result", {})
        
        if status == "success":
            description = self._describe_tool_result(tool, result)
            self.tts.announce_step(f"Completed {description}", tool_name=tool)
        elif status == "error":
            error_msg = result.get("error", "error occurred")
            self.tts.speak(f"{tool} failed: {error_msg}", summarize=True)
    
    async def on_tool_invoked(self, event: Event):
        """Handle tool_invoked events (emitted after tool execution)."""
        if not self.announce_tool_completions:
            return
        
        payload = event.payload
        tool = payload.get("tool", "unknown")
        result = payload.get("result", {})
        status = result.get("status", "unknown")
        
        if status == "success":
            description = self._describe_tool_result(tool, result)
            self.tts.announce_step(f"Completed {description}", tool_name=tool)
        elif status == "error":
            error_msg = result.get("error", "error occurred")
            self.tts.speak(f"{tool} failed: {error_msg}", summarize=True)
    
    async def on_execution_completed(self, event: Event):
        """Handle execution_completed events."""
        if not self.announce_execution_completion:
            return
        
        payload = event.payload
        plan = payload.get("plan", {})
        results = payload.get("results", {})
        status = results.get("status", "unknown")
        
        # Generate brief summary for TTS
        summary = self._generate_execution_summary(plan, results, status)
        # Use spd-say for completion announcements
        self.tts.speak(summary, summarize=False, priority=True, prefer_spd_say=True)
    
    def _generate_execution_summary(self, plan: Dict[str, Any], results: Dict[str, Any], status: str) -> str:
        """Generate a brief summary of execution for TTS."""
        intent = plan.get("intent", "task")
        steps = plan.get("steps", [])
        step_count = len(steps)
        
        if status == "completed" or status == "success":
            # Count successful steps
            completed_steps = results.get("steps", [])
            success_count = sum(1 for s in completed_steps if s.get("status") in ("success", "completed"))
            
            if step_count == 0:
                return "Request completed successfully"
            elif step_count == 1:
                # Single step - describe it
                step = steps[0] if steps else {}
                tool = step.get("tool", "action")
                description = self._describe_tool_action(tool, step.get("params", {}))
                return f"Completed {description}"
            else:
                # Multiple steps
                return f"Completed {success_count} of {step_count} steps successfully"
        elif status == "error":
            error = results.get("error", "execution error")
            # Keep error message brief
            if len(error) > 50:
                error = error[:47] + "..."
            return f"Execution failed: {error}"
        elif status == "ask_user":
            return "Waiting for your input"
        else:
            return f"Execution {status}"
    
    async def on_input_needed(self, event: Event):
        """Handle input_needed events."""
        payload = event.payload
        message = payload.get("message", "Input needed")
        play_chime = payload.get("play_chime", True)
        
        self.tts.announce_input_needed(message, play_chime=play_chime)
    
    async def on_plan_ready(self, event: Event):
        """Handle plan_ready events (announce plan summary)."""
        payload = event.payload
        plan = payload.get("plan", {})
        steps = plan.get("steps", [])
        
        if steps:
            step_count = len(steps)
            self.tts.speak(f"Plan ready with {step_count} steps", summarize=False, priority=True)
    
    def _describe_tool_action(self, tool: str, params: Dict[str, Any]) -> str:
        """Create a concise description of tool action."""
        if tool == "tasks.create":
            title = params.get("title", "task")
            return f"creating task: {title}"
        elif tool == "calendar.create_event":
            title = params.get("title", "event")
            return f"creating event: {title}"
        elif tool == "web.get":
            url = params.get("url", "webpage")
            return f"fetching {url}"
        elif tool == "web.click_selector":
            selector = params.get("selector", "element")
            return f"clicking {selector}"
        elif tool == "memory.search":
            query = params.get("query_text", "memory")
            return f"searching {query}"
        elif tool == "memory.upsert":
            return "saving to memory"
        elif tool == "shell.run":
            command = params.get("command", "command")
            # Truncate long commands
            if len(command) > 30:
                command = command[:27] + "..."
            return f"running {command}"
        else:
            # Generic description
            return tool.replace(".", " ").replace("_", " ")
    
    def _describe_tool_result(self, tool: str, result: Dict[str, Any]) -> str:
        """Create a concise description of tool result."""
        if tool == "tasks.create" and "task" in result:
            title = result["task"].get("title", "task")
            return f"task: {title}"
        elif tool == "calendar.create_event" and "event" in result:
            title = result["event"].get("title", "event")
            return f"event: {title}"
        elif tool == "web.get" and "response" in result:
            return "webpage fetched"
        elif tool == "memory.search" and "results" in result:
            count = len(result.get("results", []))
            return f"found {count} results"
        elif tool == "shell.run" and "output" in result:
            return "command executed"
        else:
            return "completed"


def register_tts_listeners(event_bus: EventBus, tts_listener: Optional[TTSEventListener] = None):
    """
    Register TTS event listeners with the event bus.
    
    Args:
        event_bus: EventBus instance
        tts_listener: TTSEventListener instance (if None, creates new)
    """
    if tts_listener is None:
        tts_listener = TTSEventListener()
    
    # Register listeners for various events
    event_bus.on("tool_start", tts_listener.on_tool_start)
    event_bus.on("tool_complete", tts_listener.on_tool_complete)
    event_bus.on("tool_invoked", tts_listener.on_tool_invoked)  # Also handle tool_invoked
    event_bus.on("execution_completed", tts_listener.on_execution_completed)
    event_bus.on("input_needed", tts_listener.on_input_needed)
    event_bus.on("plan_ready", tts_listener.on_plan_ready)
    
    logger.info("TTS event listeners registered")

