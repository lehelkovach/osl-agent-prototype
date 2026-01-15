"""Tests for survey form filling with answer reuse."""
import unittest
from datetime import datetime, timezone

from src.personal_assistant.form_filler import FormDataRetriever
from src.personal_assistant.mock_tools import MockMemoryTools
from src.personal_assistant.models import Node, Provenance


class TestSurveyResponseStorage(unittest.TestCase):
    """Test storing survey responses for reuse."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
    
    def test_store_survey_response(self):
        """Store a completed survey response."""
        qa = [
            {"field_name": "full_name", "question": "Full Name", "answer": "John Doe"},
            {"field_name": "email", "question": "Email", "answer": "john@example.com"},
            {"field_name": "company", "question": "Company", "answer": "Acme Inc"},
        ]
        
        uuid = self.retriever.store_survey_response(
            form_url="https://example.com/survey",
            questions_and_answers=qa,
            form_title="Customer Feedback"
        )
        
        self.assertIsNotNone(uuid)
        stored = self.memory.nodes.get(uuid)
        self.assertEqual(stored.kind, "SurveyResponse")
        self.assertEqual(stored.props.get("full_name"), "John Doe")
        self.assertEqual(stored.props.get("email"), "john@example.com")
    
    def test_store_survey_extracts_domain(self):
        """Survey response should have domain in labels."""
        qa = [{"field_name": "name", "answer": "Test"}]
        
        uuid = self.retriever.store_survey_response(
            form_url="https://surveys.example.com/form",
            questions_and_answers=qa
        )
        
        stored = self.memory.nodes.get(uuid)
        self.assertIn("surveys.example.com", stored.labels)


class TestFieldNormalization(unittest.TestCase):
    """Test field name normalization for matching."""
    
    def setUp(self):
        self.retriever = FormDataRetriever(MockMemoryTools())
    
    def test_normalize_email_variants(self):
        """Different email field names should normalize to 'email'."""
        self.assertEqual(self.retriever.normalize_field_name("email"), "email")
        self.assertEqual(self.retriever.normalize_field_name("email_address"), "email")
        self.assertEqual(self.retriever.normalize_field_name("e_mail"), "email")
    
    def test_normalize_name_variants(self):
        """Different name field names should normalize to 'name'."""
        self.assertEqual(self.retriever.normalize_field_name("name"), "name")
        self.assertEqual(self.retriever.normalize_field_name("full_name"), "name")
        self.assertEqual(self.retriever.normalize_field_name("fullname"), "name")
    
    def test_normalize_company_variants(self):
        """Different company field names should normalize."""
        self.assertEqual(self.retriever.normalize_field_name("company"), "company")
        self.assertEqual(self.retriever.normalize_field_name("organization"), "company")
    
    def test_unknown_field_stays_lowercase(self):
        """Unknown fields should just be lowercased."""
        self.assertEqual(self.retriever.normalize_field_name("Custom_Field"), "custom_field")


class TestSurveyAutofill(unittest.TestCase):
    """Test building autofill data from stored surveys."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
        
        # Store a survey response
        prov = Provenance("test", datetime.now(timezone.utc).isoformat(), 1.0, "test")
        survey = Node(
            kind="SurveyResponse",
            labels=["SurveyResponse"],
            props={
                "full_name": "Jane Smith",
                "email": "jane@company.com",
                "phone": "555-1234",
                "company": "Tech Corp",
                "job_title": "Engineer",
            }
        )
        self.memory.upsert(survey, prov)
    
    def test_autofill_exact_match(self):
        """Fields with exact name match should be filled."""
        form_fields = [
            {"field_name": "full_name", "required": True},
            {"field_name": "email", "required": True},
        ]
        
        result = self.retriever.build_survey_autofill(form_fields)
        
        self.assertEqual(result["autofill"].get("full_name"), "Jane Smith")
        self.assertEqual(result["autofill"].get("email"), "jane@company.com")
    
    def test_autofill_normalized_match(self):
        """Fields with different names but same meaning should match."""
        form_fields = [
            {"field_name": "name", "required": True},  # Should match "full_name"
            {"field_name": "email_address", "required": True},  # Should match "email"
            {"field_name": "organization", "required": True},  # Should match "company"
        ]
        
        result = self.retriever.build_survey_autofill(form_fields)
        
        self.assertEqual(result["autofill"].get("name"), "Jane Smith")
        self.assertEqual(result["autofill"].get("email_address"), "jane@company.com")
        self.assertEqual(result["autofill"].get("organization"), "Tech Corp")
    
    def test_missing_fields_detected(self):
        """Required fields without data should be in missing list."""
        form_fields = [
            {"field_name": "full_name", "required": True},
            {"field_name": "budget", "required": True},  # Not in stored data
            {"field_name": "timeline", "required": True},  # Not in stored data
        ]
        
        result = self.retriever.build_survey_autofill(form_fields)
        
        self.assertIn("budget", result["missing"])
        self.assertIn("timeline", result["missing"])
        self.assertNotIn("full_name", result["missing"])
    
    def test_confidence_calculation(self):
        """Confidence should reflect fill ratio."""
        form_fields = [
            {"field_name": "full_name", "required": True},
            {"field_name": "email", "required": True},
            {"field_name": "unknown_field", "required": True},
            {"field_name": "another_unknown", "required": True},
        ]
        
        result = self.retriever.build_survey_autofill(form_fields)
        
        # 2 out of 4 fields filled = 0.5 confidence
        self.assertEqual(result["filled_fields"], 2)
        self.assertEqual(result["total_fields"], 4)
        self.assertAlmostEqual(result["confidence"], 0.5)


class TestSurveyPromptGeneration(unittest.TestCase):
    """Test prompt generation for missing survey fields."""
    
    def setUp(self):
        self.retriever = FormDataRetriever(MockMemoryTools())
    
    def test_prompt_lists_missing_fields(self):
        """Prompt should list all missing fields."""
        missing = ["budget", "timeline", "team_size"]
        prompt = self.retriever.build_survey_prompt(missing)
        
        self.assertIn("Budget", prompt)
        self.assertIn("Timeline", prompt)
        self.assertIn("Team Size", prompt)
    
    def test_prompt_uses_custom_labels(self):
        """Prompt should use custom labels when provided."""
        missing = ["budget"]
        labels = {"budget": "Annual Software Budget (USD)"}
        prompt = self.retriever.build_survey_prompt(missing, labels)
        
        self.assertIn("Annual Software Budget (USD)", prompt)


class TestMissingSurveyFields(unittest.TestCase):
    """Test detection of missing survey fields."""
    
    def setUp(self):
        self.retriever = FormDataRetriever(MockMemoryTools())
    
    def test_all_fields_present(self):
        """No missing fields when all required are available."""
        required = ["name", "email"]
        available = {"name": "John", "email": "john@test.com"}
        
        missing = self.retriever.get_missing_survey_fields(required, available)
        
        self.assertEqual(missing, [])
    
    def test_some_fields_missing(self):
        """Return list of missing required fields."""
        required = ["name", "email", "phone", "company"]
        available = {"name": "John", "email": "john@test.com"}
        
        missing = self.retriever.get_missing_survey_fields(required, available)
        
        self.assertEqual(set(missing), {"phone", "company"})
    
    def test_none_values_count_as_missing(self):
        """Fields with None values are considered missing."""
        required = ["name", "email"]
        available = {"name": "John", "email": None}
        
        missing = self.retriever.get_missing_survey_fields(required, available)
        
        self.assertEqual(missing, ["email"])


class TestSurveyAnswerMatching(unittest.TestCase):
    """Test matching survey questions to stored answers."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        self.retriever = FormDataRetriever(self.memory)
        
        # Store a survey response with questions
        prov = Provenance("test", datetime.now(timezone.utc).isoformat(), 1.0, "test")
        survey = Node(
            kind="SurveyResponse",
            labels=["SurveyResponse"],
            props={
                "questions": [
                    {"question": "What is your name?", "answer": "Alice"},
                    {"question": "Years of experience", "answer": "5"},
                    {"question": "Preferred programming language", "answer": "Python"},
                ]
            }
        )
        self.memory.upsert(survey, prov)
    
    def test_match_similar_questions(self):
        """Similar questions should match stored answers."""
        questions = [
            {"question": "Your name?", "field_name": "name"},
            {"question": "Years of work experience", "field_name": "experience"},
        ]
        
        matches = self.retriever.match_survey_answers(questions)
        
        self.assertEqual(matches.get("name"), "Alice")
        self.assertEqual(matches.get("experience"), "5")
    
    def test_empty_questions_returns_empty(self):
        """Empty question list should return empty matches."""
        questions = []
        
        matches = self.retriever.match_survey_answers(questions)
        
        self.assertEqual(matches, {})


if __name__ == "__main__":
    unittest.main()
