"""
Deterministic Parser: Rule-based classification without LLM.

Ported from deprecated knowshowgo repository.
Use for: offline mode, cost optimization, fast preprocessing.

This module provides lightweight rule-based classification for obvious
intents (task, event, query) without calling the LLM. Use it to:
- Reduce API costs for simple queries
- Enable offline/dev/test modes (no API keys needed)
- Provide predictable unit tests
- Speed up response time for simple requests
"""

import re
from typing import Dict, Optional, Tuple, List

# Keywords that suggest different intent types
EVENT_KEYWORDS = {
    "remind", "reminder", "schedule", "event", "meet", "meeting", 
    "appointment", "call", "calendar", "alarm", "notify", "notification"
}
TASK_KEYWORDS = {
    "todo", "task", "do", "complete", "finish", "fix", "implement", 
    "add", "create", "make", "build", "write", "update", "delete",
    "remove", "install", "setup", "configure"
}
QUERY_KEYWORDS = {
    "what", "when", "where", "who", "how", "why", "show", "list", 
    "find", "search", "get", "tell", "explain", "describe"
}
PROCEDURE_KEYWORDS = {
    "procedure", "workflow", "process", "steps", "run", "execute",
    "perform", "automate", "script"
}


def infer_concept_kind(instruction: str) -> str:
    """
    Classify instruction into concept type without LLM.
    
    Returns: "event", "task", "query", or "procedure"
    
    Examples:
        >>> infer_concept_kind("remind me to call mom at 3pm")
        'event'
        >>> infer_concept_kind("what is my schedule for tomorrow?")
        'query'
        >>> infer_concept_kind("create a new task to fix the bug")
        'task'
    """
    text = instruction.lower().strip()
    
    # Check for query patterns FIRST if instruction starts with question word
    # This ensures "what is my schedule?" is a query, not an event
    first_word = text.split()[0] if text.split() else ""
    question_starters = {"what", "when", "where", "who", "how", "why"}
    if first_word in question_starters:
        return "query"
    
    # Check for other query patterns (show, list, find)
    if any(text.startswith(kw) for kw in ["show", "list", "find", "search", "get"]):
        return "query"
    
    # Check for event-like patterns (time-sensitive)
    if any(keyword in text for keyword in EVENT_KEYWORDS):
        return "event"
    
    # Check for procedure/workflow patterns
    if any(keyword in text for keyword in PROCEDURE_KEYWORDS):
        return "procedure"
    
    # Check for task patterns
    if any(keyword in text for keyword in TASK_KEYWORDS):
        return "task"
    
    # Default to task for imperative sentences
    return "task"


def extract_event_fields(instruction: str) -> Dict[str, str]:
    """
    Extract time and action from event-like instructions.
    
    Returns: {"time": "HH:MM" or "unspecified", "action": "..."}
    
    Examples:
        >>> extract_event_fields("remind me at 3pm to call mom")
        {'time': '15:00', 'action': 'call mom'}
        >>> extract_event_fields("schedule meeting at noon")
        {'time': '12:00', 'action': 'meeting'}
    """
    time_value = "unspecified"
    
    # Try midnight/noon first
    if re.search(r"\bat\s+midnight\b", instruction, re.IGNORECASE):
        time_value = "00:00"
    elif re.search(r"\bat\s+noon\b", instruction, re.IGNORECASE):
        time_value = "12:00"
    else:
        # Try HH:MM pattern with optional am/pm
        match = re.search(
            r"\bat\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?",
            instruction, re.IGNORECASE
        )
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2) or 0)
            ampm = (match.group(3) or "").lower()
            
            if ampm == "pm" and hour < 12:
                hour += 12
            elif ampm == "am" and hour == 12:
                hour = 0
                
            time_value = f"{hour:02d}:{minute:02d}"
    
    # Try relative time patterns
    if time_value == "unspecified":
        # "in X minutes/hours"
        match = re.search(r"\bin\s+(\d+)\s+(minute|hour|min|hr)s?\b", instruction, re.IGNORECASE)
        if match:
            amount = int(match.group(1))
            unit = match.group(2).lower()
            if unit in ("hour", "hr"):
                time_value = f"+{amount}h"
            else:
                time_value = f"+{amount}m"
    
    # Extract action by removing time phrase and common prefixes
    text = re.sub(
        r"(?i)\bat\s+(midnight|noon|\d{1,2}(:\d{2})?\s*(am|pm)?)",
        "", instruction
    )
    text = re.sub(r"(?i)\bin\s+\d+\s+(minute|hour|min|hr)s?\b", "", text)
    text = re.sub(r"(?i)\b(remind me to|remind me|please|can you|could you)\b", "", text)
    text = re.sub(r"(?i)\b(schedule|set|create)\s+(a\s+)?(reminder|event|meeting)\s*(to|for)?\b", "", text)
    action = text.strip(" ,.")
    
    return {
        "time": time_value,
        "action": action or instruction.strip()
    }


def extract_task_fields(instruction: str) -> Dict[str, str]:
    """
    Extract task-related fields from instruction.
    
    Returns: {"title": "...", "priority": "normal|high|low"}
    """
    text = instruction.lower()
    
    # Detect priority
    priority = "normal"
    if any(word in text for word in ["urgent", "asap", "important", "critical", "high priority"]):
        priority = "high"
    elif any(word in text for word in ["low priority", "whenever", "eventually", "someday"]):
        priority = "low"
    
    # Clean up the title
    title = re.sub(r"(?i)\b(please|can you|could you|i need to|i want to)\b", "", instruction)
    title = re.sub(r"(?i)\b(urgent|asap|important|critical|high priority|low priority)\b", "", title)
    title = title.strip(" ,.")
    
    return {
        "title": title or instruction.strip(),
        "priority": priority
    }


def extract_query_fields(instruction: str) -> Dict[str, str]:
    """
    Extract query-related fields from instruction.
    
    Returns: {"query_type": "what|when|where|who|how|list", "subject": "..."}
    """
    text = instruction.lower().strip()
    
    # Detect query type
    query_type = "what"
    for qtype in ["what", "when", "where", "who", "how", "why"]:
        if text.startswith(qtype):
            query_type = qtype
            break
    
    if any(word in text for word in ["list", "show", "find", "search"]):
        query_type = "list"
    
    # Extract subject
    subject = re.sub(r"(?i)^(what|when|where|who|how|why|list|show|find|search)\s*(is|are|do|does|did|was|were|my|the)?\s*", "", instruction)
    subject = subject.strip(" ?.")
    
    return {
        "query_type": query_type,
        "subject": subject or instruction.strip()
    }


def quick_parse(instruction: str) -> Tuple[str, Dict[str, str]]:
    """
    Quick deterministic parsing without LLM.
    
    Returns: (concept_kind, fields_dict)
    
    Example:
        >>> kind, fields = quick_parse("Remind me at 3pm to call mom")
        >>> kind
        'event'
        >>> fields
        {'time': '15:00', 'action': 'call mom'}
    """
    kind = infer_concept_kind(instruction)
    
    if kind == "event":
        fields = extract_event_fields(instruction)
    elif kind == "task":
        fields = extract_task_fields(instruction)
    elif kind == "query":
        fields = extract_query_fields(instruction)
    else:
        fields = {"description": instruction}
    
    return kind, fields


def is_obvious_intent(instruction: str, kind: str) -> bool:
    """
    Check if the classified intent is obviously correct (high confidence).
    
    Use this to decide whether to skip LLM for simple cases.
    
    Args:
        instruction: The user's instruction
        kind: The classified kind from infer_concept_kind()
        
    Returns:
        True if the classification is obviously correct, False if ambiguous
    """
    text = instruction.lower()
    
    if kind == "event":
        # Obvious if it has time indicators AND event keywords
        has_time = bool(re.search(r"\bat\s+\d|in\s+\d+\s+(minute|hour)|midnight|noon", text, re.IGNORECASE))
        has_event_word = any(kw in text for kw in ["remind", "schedule", "meeting", "appointment", "alarm"])
        return has_time and has_event_word
    
    elif kind == "query":
        # Obvious if it starts with a question word
        return text.strip().split()[0] in {"what", "when", "where", "who", "how", "why"}
    
    elif kind == "task":
        # Obvious if it has clear action verbs at the start
        first_words = text.strip().split()[:2]
        action_verbs = {"create", "make", "add", "fix", "update", "delete", "remove", "install", "build"}
        return any(word in action_verbs for word in first_words)
    
    elif kind == "procedure":
        # Obvious if it mentions procedure/workflow explicitly
        return any(kw in text for kw in ["procedure", "workflow", "run the", "execute the"])
    
    return False


def get_confidence_score(instruction: str, kind: str) -> float:
    """
    Get a confidence score for the classification (0.0 to 1.0).
    
    Args:
        instruction: The user's instruction
        kind: The classified kind
        
    Returns:
        Confidence score (higher = more confident)
    """
    text = instruction.lower()
    score = 0.5  # Base score
    
    # Count keyword matches
    keyword_sets = {
        "event": EVENT_KEYWORDS,
        "task": TASK_KEYWORDS,
        "query": QUERY_KEYWORDS,
        "procedure": PROCEDURE_KEYWORDS,
    }
    
    if kind in keyword_sets:
        matches = sum(1 for kw in keyword_sets[kind] if kw in text)
        score += min(0.3, matches * 0.1)  # Up to 0.3 bonus for keyword matches
    
    # Bonus for obvious patterns
    if is_obvious_intent(instruction, kind):
        score += 0.2
    
    return min(1.0, score)
