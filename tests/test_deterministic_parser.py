"""Tests for DeterministicParser - rule-based classification without LLM."""
import pytest
from src.personal_assistant.deterministic_parser import (
    infer_concept_kind,
    extract_event_fields,
    extract_task_fields,
    extract_query_fields,
    quick_parse,
    is_obvious_intent,
    get_confidence_score,
)


class TestInferConceptKind:
    """Tests for infer_concept_kind function."""
    
    def test_event_with_remind(self):
        assert infer_concept_kind("remind me to call mom") == "event"
    
    def test_event_with_schedule(self):
        assert infer_concept_kind("schedule a meeting for tomorrow") == "event"
    
    def test_event_with_appointment(self):
        assert infer_concept_kind("set an appointment with the doctor") == "event"
    
    def test_task_with_create(self):
        assert infer_concept_kind("create a new file") == "task"
    
    def test_task_with_fix(self):
        assert infer_concept_kind("fix the bug in the login page") == "task"
    
    def test_task_with_implement(self):
        assert infer_concept_kind("implement the new feature") == "task"
    
    def test_query_with_what(self):
        assert infer_concept_kind("what is my schedule?") == "query"
    
    def test_query_with_show(self):
        assert infer_concept_kind("show me my tasks") == "query"
    
    def test_query_with_list(self):
        assert infer_concept_kind("list all contacts") == "query"
    
    def test_procedure_with_workflow(self):
        assert infer_concept_kind("run the login workflow") == "procedure"
    
    def test_procedure_with_execute(self):
        assert infer_concept_kind("execute the deployment procedure") == "procedure"
    
    def test_default_to_task(self):
        assert infer_concept_kind("something random") == "task"


class TestExtractEventFields:
    """Tests for extract_event_fields function."""
    
    def test_time_at_3pm(self):
        result = extract_event_fields("remind me at 3pm to call mom")
        assert result["time"] == "15:00"
        assert "call mom" in result["action"]
    
    def test_time_at_noon(self):
        result = extract_event_fields("schedule lunch at noon")
        assert result["time"] == "12:00"
    
    def test_time_at_midnight(self):
        result = extract_event_fields("alarm at midnight")
        assert result["time"] == "00:00"
    
    def test_time_with_minutes(self):
        result = extract_event_fields("meeting at 2:30pm")
        assert result["time"] == "14:30"
    
    def test_time_24_hour(self):
        result = extract_event_fields("call at 14:00")
        assert result["time"] == "14:00"
    
    def test_time_am(self):
        result = extract_event_fields("wake up at 7am")
        assert result["time"] == "07:00"
    
    def test_time_12am(self):
        result = extract_event_fields("event at 12am")
        assert result["time"] == "00:00"
    
    def test_relative_time_minutes(self):
        result = extract_event_fields("remind me in 30 minutes")
        assert result["time"] == "+30m"
    
    def test_relative_time_hours(self):
        result = extract_event_fields("call back in 2 hours")
        assert result["time"] == "+2h"
    
    def test_no_time_specified(self):
        result = extract_event_fields("remind me to buy milk")
        assert result["time"] == "unspecified"
        assert "buy milk" in result["action"]
    
    def test_action_extraction(self):
        result = extract_event_fields("remind me to call the doctor at 3pm")
        assert "call the doctor" in result["action"]


class TestExtractTaskFields:
    """Tests for extract_task_fields function."""
    
    def test_normal_priority(self):
        result = extract_task_fields("create a new document")
        assert result["priority"] == "normal"
    
    def test_high_priority_urgent(self):
        result = extract_task_fields("urgent: fix the server crash")
        assert result["priority"] == "high"
    
    def test_high_priority_asap(self):
        result = extract_task_fields("deploy the fix asap")
        assert result["priority"] == "high"
    
    def test_low_priority(self):
        result = extract_task_fields("low priority: update documentation")
        assert result["priority"] == "low"
    
    def test_title_extraction(self):
        result = extract_task_fields("please create a new user account")
        assert "create" in result["title"].lower()
        assert "user account" in result["title"].lower()


class TestExtractQueryFields:
    """Tests for extract_query_fields function."""
    
    def test_what_query(self):
        result = extract_query_fields("what is my schedule?")
        assert result["query_type"] == "what"
        assert "schedule" in result["subject"]
    
    def test_when_query(self):
        result = extract_query_fields("when is the meeting?")
        assert result["query_type"] == "when"
        assert "meeting" in result["subject"]
    
    def test_who_query(self):
        result = extract_query_fields("who is John Smith?")
        assert result["query_type"] == "who"
        assert "john smith" in result["subject"].lower()
    
    def test_list_query(self):
        result = extract_query_fields("list all my tasks")
        assert result["query_type"] == "list"
    
    def test_show_query(self):
        result = extract_query_fields("show me the contacts")
        assert result["query_type"] == "list"


class TestQuickParse:
    """Tests for quick_parse function."""
    
    def test_event_parsing(self):
        kind, fields = quick_parse("remind me at 3pm to call mom")
        assert kind == "event"
        assert fields["time"] == "15:00"
        assert "call mom" in fields["action"]
    
    def test_task_parsing(self):
        kind, fields = quick_parse("create a new document")
        assert kind == "task"
        assert "title" in fields
    
    def test_query_parsing(self):
        kind, fields = quick_parse("what is my schedule?")
        assert kind == "query"
        assert fields["query_type"] == "what"
    
    def test_procedure_parsing(self):
        kind, fields = quick_parse("run the deployment procedure")
        assert kind == "procedure"
        assert "description" in fields


class TestIsObviousIntent:
    """Tests for is_obvious_intent function."""
    
    def test_obvious_event(self):
        assert is_obvious_intent("remind me at 3pm to call", "event") is True
    
    def test_not_obvious_event(self):
        # No time indicator
        assert is_obvious_intent("remind me about something", "event") is False
    
    def test_obvious_query(self):
        assert is_obvious_intent("what is the weather?", "query") is True
    
    def test_obvious_task(self):
        assert is_obvious_intent("create a new file", "task") is True
    
    def test_obvious_procedure(self):
        assert is_obvious_intent("run the login procedure", "procedure") is True


class TestGetConfidenceScore:
    """Tests for get_confidence_score function."""
    
    def test_high_confidence_event(self):
        score = get_confidence_score("remind me at 3pm to call mom", "event")
        assert score >= 0.7
    
    def test_high_confidence_query(self):
        score = get_confidence_score("what is my schedule?", "query")
        assert score >= 0.7
    
    def test_moderate_confidence(self):
        score = get_confidence_score("something vague", "task")
        assert 0.4 <= score <= 0.7
    
    def test_score_in_range(self):
        score = get_confidence_score("anything", "task")
        assert 0.0 <= score <= 1.0
