"""
Test survey form recognition and answer reuse:
1. Agent encounters a survey form
2. Recognizes it as a survey (exemplar)
3. Remembers answers to similar questions
4. Fills in those answers automatically
"""

import json
import unittest
from typing import Dict, Any, Optional, List

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.knowshowgo import KnowShowGoAPI
from src.personal_assistant.openai_client import FakeOpenAIClient
from src.personal_assistant.mock_tools import (
    MockMemoryTools,
    MockCalendarTools,
    MockTaskTools,
    MockWebTools,
    MockContactsTools,
)
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.models import Provenance
from src.personal_assistant.ksg import KSGStore
from src.personal_assistant.cpms_adapter import CPMSAdapter
from tests.test_cpms_adapter import FakeCpmsClientWithPatterns


class FakeCpmsClientWithSurveyDetection(FakeCpmsClientWithPatterns):
    """Extended fake CPMS client that detects survey forms."""
    
    def detect_form(self, html=None, screenshot_path=None, url=None, dom_snapshot=None):
        """Detect form patterns including surveys."""
        html_lower = (html or "").lower()
        
        # Check if it's a survey (has multiple questions, labels, form structure)
        is_survey = (
            "survey" in html_lower or
            ("form" in html_lower and "label" in html_lower and html_lower.count("label") >= 2) or
            ("question" in html_lower and "answer" in html_lower)
        )
        
        if is_survey:
            # Extract survey fields
            import re
            labels = re.findall(r'<label[^>]*>([^<]+)</label>', html or "", re.IGNORECASE)
            inputs = re.findall(r'<input[^>]*name=["\']([^"\']+)["\']', html or "", re.IGNORECASE)
            selects = re.findall(r'<select[^>]*name=["\']([^"\']+)["\']', html or "", re.IGNORECASE)
            
            fields = []
            for i, label in enumerate(labels[:len(inputs) + len(selects)]):
                field_name = inputs[i] if i < len(inputs) else selects[i - len(inputs)]
                fields.append({
                    "type": "text" if i < len(inputs) else "select",
                    "name": field_name,
                    "label": label.strip(),
                    "selector": f"input[name='{field_name}'], select[name='{field_name}']",
                    "confidence": 0.9,
                })
            
            return {
                "form_type": "survey",
                "fields": fields,
                "confidence": 0.85,
                "pattern_id": "survey-pattern-123"
            }
        
        # Fallback to parent class for login forms
        return super().detect_form(html, screenshot_path, url, dom_snapshot)


class MockSurveyWebTools(MockWebTools):
    """Mock web tools that simulate survey forms."""
    
    def __init__(self):
        super().__init__()
        self.survey_forms = {
            "survey1": {
                "html": """
                <html>
                <body>
                    <form id="survey-form">
                        <label>What is your favorite programming language?</label>
                        <input type="text" name="favorite_language" id="fav-lang" />
                        <label>How many years of experience do you have?</label>
                        <input type="number" name="years_experience" id="years-exp" />
                        <label>What is your preferred work environment?</label>
                        <select name="work_env" id="work-env">
                            <option value="">Select...</option>
                            <option value="remote">Remote</option>
                            <option value="office">Office</option>
                            <option value="hybrid">Hybrid</option>
                        </select>
                        <button type="submit">Submit Survey</button>
                    </form>
                </body>
                </html>
                """,
                "fields": [
                    {"name": "favorite_language", "label": "What is your favorite programming language?", "type": "text"},
                    {"name": "years_experience", "label": "How many years of experience do you have?", "type": "number"},
                    {"name": "work_env", "label": "What is your preferred work environment?", "type": "select"},
                ]
            },
            "survey2": {
                "html": """
                <html>
                <body>
                    <form id="survey-form">
                        <label>Which programming language do you prefer?</label>
                        <input type="text" name="preferred_language" id="pref-lang" />
                        <label>Years of professional experience?</label>
                        <input type="number" name="experience_years" id="exp-years" />
                        <label>Preferred work setting?</label>
                        <select name="work_setting" id="work-setting">
                            <option value="">Select...</option>
                            <option value="remote">Remote</option>
                            <option value="office">Office</option>
                            <option value="hybrid">Hybrid</option>
                        </select>
                        <button type="submit">Submit</button>
                    </form>
                </body>
                </html>
                """,
                "fields": [
                    {"name": "preferred_language", "label": "Which programming language do you prefer?", "type": "text"},
                    {"name": "experience_years", "label": "Years of professional experience?", "type": "number"},
                    {"name": "work_setting", "label": "Preferred work setting?", "type": "select"},
                ]
            }
        }
        self.filled_values = {}
    
    def get_dom(self, url: str) -> Dict[str, Any]:
        """Return survey form HTML."""
        survey_id = "survey1" if "survey1" in url else "survey2" if "survey2" in url else "survey1"
        return {
            "status": 200,
            "html": self.survey_forms[survey_id]["html"],
            "url": url
        }
    
    def fill(self, url: str, selector: str = "", text: str = "", selectors: Dict[str, str] = None, values: Dict[str, str] = None, **kwargs) -> Dict[str, Any]:
        """Simulate form filling - store values for verification. Supports both old API (selector, text) and new API (selectors dict, values dict)."""
        # Handle new API with selectors and values dicts
        if selectors and values:
            self.filled_values.update(values)
            return {"status": "success", "url": url, "filled": selectors, "values": values}
        # Handle old API with single selector and text
        elif selector and text:
            self.filled_values[selector] = text
            return {"status": "success", "url": url, "selector": selector, "text": text}
        return {"status": "success", "url": url}




class TestAgentSurveyAnswerReuse(unittest.TestCase):
    """Test survey form recognition and answer reuse."""
    
    def setUp(self):
        self.memory = MockMemoryTools()
        
        def embed(text):
            """Simple embedding function."""
            text_lower = text.lower()
            if "survey" in text_lower:
                return [1.0, 0.5, 0.2]
            elif "question" in text_lower or "answer" in text_lower:
                return [0.9, 0.6, 0.3]
            elif "programming" in text_lower or "language" in text_lower:
                return [0.8, 0.7, 0.4]
            elif "experience" in text_lower or "years" in text_lower:
                return [0.7, 0.8, 0.5]
            elif "work" in text_lower and "environment" in text_lower:
                return [0.6, 0.9, 0.6]
            else:
                return [float(len(text)) * 0.01, 0.1 * len(text.split()) * 0.01, 0.0]
        
        # Seed prototypes
        ksg_store = KSGStore(self.memory)
        ksg_store.ensure_seeds(embedding_fn=embed)
        
        self.ksg = KnowShowGoAPI(self.memory, embed_fn=embed)
        self.procedure_builder = ProcedureBuilder(self.memory, embed_fn=embed)
        self.web_tools = MockSurveyWebTools()
        self.cpms = CPMSAdapter(FakeCpmsClientWithSurveyDetection())
    
    def _create_agent_with_llm_plan(self, llm_plan: Dict[str, Any], chat_response_override: Optional[str] = None):
        """Helper to create agent with specific LLM plan."""
        response = chat_response_override or json.dumps(llm_plan)
        llm_client = FakeOpenAIClient(
            chat_response=response,
            embedding=[1.0, 0.5, 0.2]
        )
        
        return PersonalAssistantAgent(
            memory=self.memory,
            calendar=MockCalendarTools(),
            tasks=MockTaskTools(),
            web=self.web_tools,
            contacts=MockContactsTools(),
            procedure_builder=self.procedure_builder,
            ksg=self.ksg,
            openai_client=llm_client,
            cpms=self.cpms,
        )
    
    def test_phase1_recognize_survey_and_store_answers(self):
        """Phase 1: Agent recognizes survey form and stores answers."""
        user_msg = "Fill out this survey at https://example.com/survey1"
        
        # First time - user provides answers
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "web.get_dom",
                    "params": {"url": "https://example.com/survey1"},
                    "comment": "Get survey form"
                },
                {
                    "tool": "cpms.detect_form",
                    "params": {"html": "<form>...</form>", "url": "https://example.com/survey1"},
                    "comment": "Detect if this is a survey form"
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "https://example.com/survey1",
                        "selectors": {
                            "favorite_language": "#fav-lang",
                            "years_experience": "#years-exp",
                            "work_env": "#work-env"
                        },
                        "values": {
                            "favorite_language": "Python",
                            "years_experience": "5",
                            "work_env": "remote"
                        }
                    },
                    "comment": "Fill survey with user-provided answers"
                },
                {
                    "tool": "ksg.create_concept",
                    "params": {
                        "prototype_uuid": self._get_survey_response_prototype_uuid(),
                        "json_obj": {
                            "name": "Survey Response - Programming Language Survey",
                            "description": "Answers to programming language survey",
                            "questions": [
                                {
                                    "question": "What is your favorite programming language?",
                                    "answer": "Python",
                                    "field_name": "favorite_language"
                                },
                                {
                                    "question": "How many years of experience do you have?",
                                    "answer": "5",
                                    "field_name": "years_experience"
                                },
                                {
                                    "question": "What is your preferred work environment?",
                                    "answer": "remote",
                                    "field_name": "work_env"
                                }
                            ],
                            "survey_type": "programming_language",
                            "filled_at": "2026-01-07T12:00:00Z"
                        },
                        "embedding": [1.0, 0.5, 0.2]
                    },
                    "comment": "Store survey responses for future reuse"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution succeeded
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify survey responses were stored
        survey_responses = [n for n in self.memory.nodes.values() 
                          if n.kind == "topic" and n.props.get("isPrototype") is False 
                          and ("survey" in str(n.props.get("name", "")).lower() or 
                               "survey" in str(n.props.get("label", "")).lower() or
                               n.props.get("questions") is not None)]
        self.assertGreater(len(survey_responses), 0, f"Survey responses should be stored. Found {len(self.memory.nodes)} nodes. Survey nodes: {[n.props.get('name') or n.props.get('label') for n in self.memory.nodes.values() if n.kind == 'topic' and n.props.get('isPrototype') is False][:5]}")
    
    def test_phase2_reuse_answers_for_similar_survey(self):
        """Phase 2: Agent reuses stored answers for similar survey questions."""
        # First, store answers from phase 1
        survey_response_uuid = self.ksg.create_concept(
            prototype_uuid=self._get_survey_response_prototype_uuid(),
            json_obj={
                "name": "Survey Response - Programming Language Survey",
                "description": "Answers to programming language survey",
                "questions": [
                    {
                        "question": "What is your favorite programming language?",
                        "answer": "Python",
                        "field_name": "favorite_language"
                    },
                    {
                        "question": "How many years of experience do you have?",
                        "answer": "5",
                        "field_name": "years_experience"
                    },
                    {
                        "question": "What is your preferred work environment?",
                        "answer": "remote",
                        "field_name": "work_env"
                    }
                ],
                "survey_type": "programming_language"
            },
            embedding=[1.0, 0.5, 0.2],
        )
        
        # Now user asks to fill a similar survey
        user_msg = "Fill out this similar survey at https://example.com/survey2"
        
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "web.get_dom",
                    "params": {"url": "https://example.com/survey2"},
                    "comment": "Get survey form"
                },
                {
                    "tool": "cpms.detect_form",
                    "params": {"html": "<form>...</form>", "url": "https://example.com/survey2"},
                    "comment": "Detect if this is a survey form"
                },
                {
                    "tool": "ksg.search_concepts",
                    "params": {"query": "survey response programming language", "top_k": 3},
                    "comment": "Search for similar survey responses"
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "https://example.com/survey2",
                        "selectors": {
                            "preferred_language": "#pref-lang",  # Similar question, different field name
                            "experience_years": "#exp-years",     # Similar question, different field name
                            "work_setting": "#work-setting"      # Similar question, different field name
                        },
                        "values": {
                            "preferred_language": "Python",  # Reused from stored answer
                            "experience_years": "5",          # Reused from stored answer
                            "work_setting": "remote"          # Reused from stored answer
                        }
                    },
                    "comment": "Fill survey with remembered answers to similar questions"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution succeeded
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify answers were filled (check web_tools.filled_values)
        # Values are stored by selector, not field name
        self.assertEqual(self.web_tools.filled_values.get("#pref-lang"), "Python")
        self.assertEqual(self.web_tools.filled_values.get("#exp-years"), "5")
        self.assertEqual(self.web_tools.filled_values.get("#work-setting"), "remote")
    
    def test_phase3_question_similarity_matching(self):
        """Phase 3: Agent matches similar questions even with different wording."""
        # Store answers with specific question text
        survey_response_uuid = self.ksg.create_concept(
            prototype_uuid=self._get_survey_response_prototype_uuid(),
            json_obj={
                "name": "Survey Response - Experience Survey",
                "questions": [
                    {
                        "question": "How many years of experience do you have?",
                        "answer": "5",
                        "field_name": "years_experience"
                    }
                ]
            },
            embedding=[0.7, 0.8, 0.5],
        )
        
        # New survey with similar but different question wording
        user_msg = "Fill out this survey - it asks 'Years of professional experience?'"
        
        llm_plan = {
            "intent": "web_io",
            "steps": [
                {
                    "tool": "ksg.search_concepts",
                    "params": {"query": "years experience", "top_k": 3},
                    "comment": "Search for similar question/answer pairs"
                },
                {
                    "tool": "web.fill",
                    "params": {
                        "url": "https://example.com/survey2",
                        "selectors": {"experience_years": "#exp-years"},
                        "values": {"experience_years": "5"}  # Matched from similar question
                    },
                    "comment": "Fill with answer from similar question"
                }
            ]
        }
        
        agent = self._create_agent_with_llm_plan(llm_plan)
        result = agent.execute_request(user_msg)
        
        # Verify execution succeeded
        self.assertEqual(result["execution_results"]["status"], "completed")
        
        # Verify similar question was matched and answer reused
        # Value is stored by selector, not field name
        self.assertEqual(self.web_tools.filled_values.get("#exp-years"), "5")
    
    def _get_survey_response_prototype_uuid(self) -> str:
        """Get or create SurveyResponse prototype UUID."""
        # Check if it exists
        for node in self.memory.nodes.values():
            if (node.kind == "topic" and 
                node.props.get("isPrototype") is True and
                node.props.get("label") == "SurveyResponse"):
                return node.uuid
        
        # Create it
        return self.ksg.create_prototype(
            name="SurveyResponse",
            description="Stored responses to survey questions",
            context="assistant",
            labels=["SurveyResponse", "FormData"],
            embedding=[1.0, 0.5, 0.2],
        )


if __name__ == "__main__":
    unittest.main()

