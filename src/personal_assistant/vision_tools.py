"""
Vision-based element detection using GPT-4 Vision, Claude Vision, or Gemini Vision.

Provides screenshot parsing and element location via vision models.
"""

import os
import base64
from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod

from src.personal_assistant.llm_client import LLMClient, OpenAIClient, ClaudeClient, GeminiClient, create_llm_client


class VisionTools(ABC):
    """Abstract interface for vision-based element detection."""
    
    @abstractmethod
    def parse_screenshot(
        self,
        screenshot_path: str,
        query: str,
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parse a screenshot using vision model to locate elements.
        
        Args:
            screenshot_path: Path to screenshot image file
            query: Description of element to find (e.g., "login button", "email input field")
            url: Optional URL for context
            
        Returns:
            Dict with bounding boxes, element descriptions, and confidence scores
        """
        pass
    
    @abstractmethod
    def locate_elements(
        self,
        screenshot_path: str,
        element_types: List[str],
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Locate multiple element types in a screenshot.
        
        Args:
            screenshot_path: Path to screenshot image file
            element_types: List of element types to find (e.g., ["input", "button", "link"])
            url: Optional URL for context
            
        Returns:
            Dict with detected elements grouped by type
        """
        pass


class VisionLLMTools(VisionTools):
    """
    Vision-based element detection using LLM vision capabilities.
    Supports OpenAI GPT-4 Vision, Claude Vision, and Gemini Vision.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize vision tools with an LLM client.
        
        Args:
            llm_client: LLM client instance. If None, creates from env vars.
        """
        if llm_client is None:
            self.llm_client = create_llm_client()
        else:
            self.llm_client = llm_client
        
        # Check if client supports vision
        self.supports_vision = self._check_vision_support()
    
    def _check_vision_support(self) -> bool:
        """Check if the LLM client supports vision capabilities."""
        # OpenAI GPT-4 Vision models
        if isinstance(self.llm_client, OpenAIClient):
            vision_models = ["gpt-4o", "gpt-4-turbo", "gpt-4-vision-preview"]
            return any(vm in self.llm_client.chat_model.lower() for vm in vision_models)
        
        # Claude Vision models (Claude 3+ supports vision)
        if isinstance(self.llm_client, ClaudeClient):
            return True  # Claude 3+ models support vision
        
        # Gemini Vision models
        if isinstance(self.llm_client, GeminiClient):
            return True  # Gemini models support vision
        
        return False
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image file to base64."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    
    def _parse_screenshot_openai(self, screenshot_path: str, query: str, url: Optional[str] = None) -> Dict[str, Any]:
        """Parse screenshot using OpenAI GPT-4 Vision."""
        if not isinstance(self.llm_client, OpenAIClient):
            raise ValueError("OpenAI client required for OpenAI vision")
        
        base64_image = self._encode_image(screenshot_path)
        
        prompt = f"""Analyze this screenshot and locate the element described: "{query}"

If the element is found, return a JSON object with:
- "found": true
- "bbox": {{"x": number, "y": number, "width": number, "height": number}}
- "description": "brief description of the element"
- "confidence": number between 0 and 1
- "selector_hint": "suggested CSS selector or XPath if visible"

If not found, return:
- "found": false
- "reason": "why it wasn't found"

URL context: {url or "unknown"}
Return only valid JSON, no markdown."""
        
        try:
            from openai import OpenAI
            client = self.llm_client.client
            
            response = client.chat.completions.create(
                model=self.llm_client.chat_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{base64_image}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=500,
                temperature=0.0,
            )
            
            result_text = response.choices[0].message.content
            # Try to parse JSON from response
            import json
            try:
                # Extract JSON if wrapped in markdown
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()
                
                result = json.loads(result_text)
                return {
                    "status": "success",
                    "found": result.get("found", False),
                    "bbox": result.get("bbox"),
                    "description": result.get("description"),
                    "confidence": result.get("confidence", 0.0),
                    "selector_hint": result.get("selector_hint"),
                    "reason": result.get("reason"),
                    "url": url,
                }
            except json.JSONDecodeError:
                # Fallback: return raw response
                return {
                    "status": "success",
                    "found": False,
                    "raw_response": result_text,
                    "url": url,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }
    
    def _parse_screenshot_claude(self, screenshot_path: str, query: str, url: Optional[str] = None) -> Dict[str, Any]:
        """Parse screenshot using Claude Vision."""
        if not isinstance(self.llm_client, ClaudeClient):
            raise ValueError("Claude client required for Claude vision")
        
        base64_image = self._encode_image(screenshot_path)
        
        prompt = f"""Analyze this screenshot and locate the element described: "{query}"

If the element is found, return a JSON object with:
- "found": true
- "bbox": {{"x": number, "y": number, "width": number, "height": number}}
- "description": "brief description of the element"
- "confidence": number between 0 and 1
- "selector_hint": "suggested CSS selector or XPath if visible"

If not found, return:
- "found": false
- "reason": "why it wasn't found"

URL context: {url or "unknown"}
Return only valid JSON, no markdown."""
        
        try:
            from anthropic import Anthropic
            client = self.llm_client.client
            
            response = client.messages.create(
                model=self.llm_client.chat_model,
                max_tokens=500,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": base64_image,
                                }
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
            )
            
            result_text = response.content[0].text
            # Try to parse JSON from response
            import json
            try:
                # Extract JSON if wrapped in markdown
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()
                
                result = json.loads(result_text)
                return {
                    "status": "success",
                    "found": result.get("found", False),
                    "bbox": result.get("bbox"),
                    "description": result.get("description"),
                    "confidence": result.get("confidence", 0.0),
                    "selector_hint": result.get("selector_hint"),
                    "reason": result.get("reason"),
                    "url": url,
                }
            except json.JSONDecodeError:
                # Fallback: return raw response
                return {
                    "status": "success",
                    "found": False,
                    "raw_response": result_text,
                    "url": url,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }
    
    def _parse_screenshot_gemini(self, screenshot_path: str, query: str, url: Optional[str] = None) -> Dict[str, Any]:
        """Parse screenshot using Gemini Vision."""
        if not isinstance(self.llm_client, GeminiClient):
            raise ValueError("Gemini client required for Gemini vision")
        
        prompt = f"""Analyze this screenshot and locate the element described: "{query}"

If the element is found, return a JSON object with:
- "found": true
- "bbox": {{"x": number, "y": number, "width": number, "height": number}}
- "description": "brief description of the element"
- "confidence": number between 0 and 1
- "selector_hint": "suggested CSS selector or XPath if visible"

If not found, return:
- "found": false
- "reason": "why it wasn't found"

URL context: {url or "unknown"}
Return only valid JSON, no markdown."""
        
        try:
            import google.generativeai as genai
            from PIL import Image
            
            model = self.llm_client.genai.GenerativeModel(self.llm_client.chat_model)
            
            # Load image
            image = Image.open(screenshot_path)
            
            response = model.generate_content(
                [prompt, image],
                generation_config={"temperature": 0.0, "max_output_tokens": 500}
            )
            
            result_text = response.text
            # Try to parse JSON from response
            import json
            try:
                # Extract JSON if wrapped in markdown
                if "```json" in result_text:
                    result_text = result_text.split("```json")[1].split("```")[0].strip()
                elif "```" in result_text:
                    result_text = result_text.split("```")[1].split("```")[0].strip()
                
                result = json.loads(result_text)
                return {
                    "status": "success",
                    "found": result.get("found", False),
                    "bbox": result.get("bbox"),
                    "description": result.get("description"),
                    "confidence": result.get("confidence", 0.0),
                    "selector_hint": result.get("selector_hint"),
                    "reason": result.get("reason"),
                    "url": url,
                }
            except json.JSONDecodeError:
                # Fallback: return raw response
                return {
                    "status": "success",
                    "found": False,
                    "raw_response": result_text,
                    "url": url,
                }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }
    
    def parse_screenshot(
        self,
        screenshot_path: str,
        query: str,
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Parse a screenshot using vision model to locate elements.
        
        Args:
            screenshot_path: Path to screenshot image file
            query: Description of element to find (e.g., "login button", "email input field")
            url: Optional URL for context
            
        Returns:
            Dict with bounding boxes, element descriptions, and confidence scores
        """
        if not self.supports_vision:
            return {
                "status": "error",
                "error": f"Vision not supported for {type(self.llm_client).__name__} with model {getattr(self.llm_client, 'chat_model', 'unknown')}",
            }
        
        if not os.path.exists(screenshot_path):
            return {
                "status": "error",
                "error": f"Screenshot file not found: {screenshot_path}",
            }
        
        # Route to appropriate vision implementation
        if isinstance(self.llm_client, OpenAIClient):
            return self._parse_screenshot_openai(screenshot_path, query, url)
        elif isinstance(self.llm_client, ClaudeClient):
            return self._parse_screenshot_claude(screenshot_path, query, url)
        elif isinstance(self.llm_client, GeminiClient):
            return self._parse_screenshot_gemini(screenshot_path, query, url)
        else:
            return {
                "status": "error",
                "error": f"Vision not implemented for {type(self.llm_client).__name__}",
            }
    
    def locate_elements(
        self,
        screenshot_path: str,
        element_types: List[str],
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Locate multiple element types in a screenshot.
        
        Args:
            screenshot_path: Path to screenshot image file
            element_types: List of element types to find (e.g., ["input", "button", "link"])
            url: Optional URL for context
            
        Returns:
            Dict with detected elements grouped by type
        """
        if not self.supports_vision:
            return {
                "status": "error",
                "error": f"Vision not supported for {type(self.llm_client).__name__}",
            }
        
        if not os.path.exists(screenshot_path):
            return {
                "status": "error",
                "error": f"Screenshot file not found: {screenshot_path}",
            }
        
        query = f"Locate all {', '.join(element_types)} elements in this screenshot. Return a JSON array with one object per element containing: type, bbox (x, y, width, height), description, and confidence."
        
        # Use parse_screenshot with a combined query
        result = self.parse_screenshot(screenshot_path, query, url)
        
        if result.get("status") == "success" and result.get("found"):
            # Try to parse elements from response
            import json
            try:
                if "raw_response" in result:
                    elements = json.loads(result["raw_response"])
                else:
                    # Group by type if possible
                    elements = [result]
                
                return {
                    "status": "success",
                    "elements": elements,
                    "url": url,
                }
            except Exception:
                return result
        else:
            return result


class MockVisionTools(VisionTools):
    """Mock vision tools for testing."""
    
    def parse_screenshot(
        self,
        screenshot_path: str,
        query: str,
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mock implementation returns a fake bounding box."""
        return {
            "status": "success",
            "found": True,
            "bbox": {"x": 100, "y": 200, "width": 150, "height": 40},
            "description": f"Mock element matching '{query}'",
            "confidence": 0.85,
            "selector_hint": "button#submit",
            "url": url,
        }
    
    def locate_elements(
        self,
        screenshot_path: str,
        element_types: List[str],
        url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mock implementation returns fake elements."""
        elements = []
        for i, elem_type in enumerate(element_types):
            elements.append({
                "type": elem_type,
                "bbox": {"x": 100 + i * 50, "y": 200 + i * 50, "width": 150, "height": 40},
                "description": f"Mock {elem_type} element",
                "confidence": 0.85,
            })
        return {
            "status": "success",
            "elements": elements,
            "url": url,
        }

