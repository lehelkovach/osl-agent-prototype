"""
Thin adapter around `cpms-client` so the agent can create/list procedures/tasks in CPMS.

The adapter is dependency-injected to avoid hard failures when `cpms-client` is absent.
Use CPMSAdapter.from_env() if you want to build a real client from environment variables.
"""
from typing import Any, Dict, List, Optional
import os
import base64
from datetime import datetime, timezone


class CPMSNotInstalled(RuntimeError):
    pass


class CPMSAdapter:
    def __init__(self, client: Any):
        """
        client is expected to expose:
          - create_procedure(name: str, description: str, steps: list[dict]) -> dict
          - list_procedures() -> list[dict]
          - get_procedure(procedure_id: str) -> dict
          - create_task(procedure_id: str, title: str, payload: dict) -> dict (optional)
          - list_tasks(procedure_id: Optional[str]) -> list[dict] (optional)
        """
        self.client = client

    @classmethod
    def from_env(cls):
        """
        Instantiate using cpms-client if installed. Expects:
        - CPMS_BASE_URL
        - CPMS_TOKEN (or CPMS_API_KEY)
        """
        try:
            from cpms_client import Client  # type: ignore
        except Exception as exc:  # pragma: no cover - exercised only when dependency missing
            raise CPMSNotInstalled("cpms-client is not installed; pip install cpms-client") from exc
        base_url = os.getenv("CPMS_BASE_URL", "http://localhost:3000")
        token = os.getenv("CPMS_TOKEN") or os.getenv("CPMS_API_KEY")
        client = Client(base_url=base_url, token=token)  # type: ignore[arg-type]
        return cls(client)

    def create_procedure(self, name: str, description: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        return self.client.create_procedure(name=name, description=description, steps=steps)

    def list_procedures(self) -> List[Dict[str, Any]]:
        return self.client.list_procedures()

    def get_procedure(self, procedure_id: str) -> Dict[str, Any]:
        return self.client.get_procedure(procedure_id)

    def create_task(self, procedure_id: str, title: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not hasattr(self.client, "create_task"):
            raise NotImplementedError("Underlying CPMS client does not support create_task")
        return self.client.create_task(procedure_id=procedure_id, title=title, payload=payload)

    def list_tasks(self, procedure_id: Optional[str] = None) -> List[Dict[str, Any]]:
        if not hasattr(self.client, "list_tasks"):
            raise NotImplementedError("Underlying CPMS client does not support list_tasks")
        if procedure_id:
            return self.client.list_tasks(procedure_id=procedure_id)
        return self.client.list_tasks()

    def detect_form_pattern(
        self, 
        html: str, 
        screenshot_path: Optional[str] = None,
        url: Optional[str] = None,
        dom_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect form patterns in HTML using CPMS.
        Returns pattern data including detected fields (email, password, submit button, etc.).
        
        Args:
            html: HTML content of the page
            screenshot_path: Optional path to screenshot image file
            url: Optional URL of the page (for metadata)
            dom_snapshot: Optional Playwright/Selenium DOM snapshot
            
        Returns:
            Dict with form_type, fields (list of field dicts), confidence, and optional pattern_id
        """
        # Try CPMS API first if available
        if hasattr(self.client, "detect_form"):
            try:
                # Use high-level detect_form endpoint (preferred)
                result = self.client.detect_form(
                    html=html,
                    screenshot_path=screenshot_path,
                    url=url,
                    dom_snapshot=dom_snapshot
                )
                if result:
                    # Response should already be in expected format
                    return self._normalize_pattern_response(result)
            except Exception as e:
                # Log error but fall back to simple detection
                import logging
                logging.warning(f"CPMS detect_form API call failed, using fallback: {e}")
        elif hasattr(self.client, "match_pattern"):
            try:
                # Fallback to lower-level match_pattern if detect_form not available
                observation = self._build_observation(html, screenshot_path, url, dom_snapshot)
                result = self.client.match_pattern(
                    html=html, 
                    screenshot_path=screenshot_path,
                    observation=observation
                )
                if result:
                    return self._normalize_pattern_response(result)
            except Exception as e:
                import logging
                logging.warning(f"CPMS match_pattern API call failed, using fallback: {e}")
        
        # Fallback: simple pattern detection
        return self._simple_form_detection(html)
    
    def _build_observation(
        self,
        html: str,
        screenshot_path: Optional[str] = None,
        url: Optional[str] = None,
        dom_snapshot: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Build CPMS observation format from HTML, screenshot, and optional metadata.
        
        Returns observation dict in format expected by CPMS API.
        """
        observation = {
            "html": html,
            "metadata": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        }
        
        if url:
            observation["metadata"]["url"] = url
        
        # Add screenshot if provided
        if screenshot_path:
            try:
                # Try to read and encode screenshot
                with open(screenshot_path, "rb") as f:
                    screenshot_data = f.read()
                    # Encode as base64 for API transmission
                    observation["screenshot"] = base64.b64encode(screenshot_data).decode("utf-8")
                    observation["screenshot_format"] = "base64"
            except Exception:
                # If file read fails, just pass the path
                observation["screenshot_path"] = screenshot_path
        
        # Add DOM snapshot if provided
        if dom_snapshot:
            observation["dom_snapshot"] = dom_snapshot
        
        return observation
    
    def _normalize_pattern_response(self, cpms_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize CPMS API response to expected format.
        
        Expected format:
        {
            "form_type": "login",
            "fields": [
                {
                    "type": "email",
                    "selector": "input[type='email']",
                    "xpath": "...",
                    "confidence": 0.95,
                    "signals": {...}
                },
                ...
            ],
            "confidence": 0.92,
            "pattern_id": "uuid" (optional)
        }
        """
        # If response is already in expected format, return as-is
        if "fields" in cpms_response and "form_type" in cpms_response:
            return cpms_response
        
        # Otherwise, try to normalize from various CPMS response formats
        normalized = {
            "form_type": cpms_response.get("form_type", "unknown"),
            "fields": [],
            "confidence": cpms_response.get("confidence", 0.5),
        }
        
        # Extract fields from various possible response structures
        if "fields" in cpms_response:
            fields = cpms_response["fields"]
        elif "detected_fields" in cpms_response:
            fields = cpms_response["detected_fields"]
        elif "elements" in cpms_response:
            fields = cpms_response["elements"]
        else:
            fields = []
        
        # Normalize each field
        for field in fields:
            if isinstance(field, dict):
                normalized_field = {
                    "type": field.get("type") or field.get("field_type") or "unknown",
                    "selector": field.get("selector") or field.get("css_selector") or "",
                    "confidence": field.get("confidence", 0.5),
                }
                
                # Add optional fields
                if "xpath" in field:
                    normalized_field["xpath"] = field["xpath"]
                if "signals" in field:
                    normalized_field["signals"] = field["signals"]
                elif "attributes" in field:
                    normalized_field["signals"] = {"attributes": field["attributes"]}
                
                normalized["fields"].append(normalized_field)
        
        # Add pattern ID if present
        if "pattern_id" in cpms_response:
            normalized["pattern_id"] = cpms_response["pattern_id"]
        elif "matched_pattern" in cpms_response:
            normalized["pattern_id"] = cpms_response.get("matched_pattern", {}).get("id")
        
        return normalized

    def _simple_form_detection(self, html: str) -> Dict[str, Any]:
        """
        Simple form pattern detection as fallback.
        Detects email input, password input, and submit button patterns.
        """
        import re

        pattern_data = {
            "fields": [],
            "form_type": "unknown",
            "confidence": 0.5,
        }

        # Detect email input
        email_patterns = [
            r'<input[^>]*type=["\']email["\'][^>]*>',
            r'<input[^>]*type=["\']text["\'][^>]*(?:name|id)=["\'](?:email|username|user)["\'][^>]*>',
            r'<input[^>]*(?:name|id)=["\'](?:email|username|user)["\'][^>]*>',
        ]
        for pattern in email_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                pattern_data["fields"].append({
                    "type": "email",
                    "selector": "input[type='email'], input[name*='email'], input[name*='username']",
                    "confidence": 0.8,
                })
                break

        # Detect password input
        password_patterns = [
            r'<input[^>]*type=["\']password["\'][^>]*>',
        ]
        for pattern in password_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                pattern_data["fields"].append({
                    "type": "password",
                    "selector": "input[type='password']",
                    "confidence": 0.9,
                })
                break

        # Detect submit button
        submit_patterns = [
            r'<button[^>]*type=["\']submit["\'][^>]*>',
            r'<input[^>]*type=["\']submit["\'][^>]*>',
        ]
        for pattern in submit_patterns:
            if re.search(pattern, html, re.IGNORECASE):
                pattern_data["fields"].append({
                    "type": "submit",
                    "selector": "button[type='submit'], input[type='submit']",
                    "confidence": 0.9,
                })
                break

        # Determine form type
        if len([f for f in pattern_data["fields"] if f["type"] in ("email", "password")]) >= 2:
            pattern_data["form_type"] = "login"
            pattern_data["confidence"] = 0.8

        return pattern_data
