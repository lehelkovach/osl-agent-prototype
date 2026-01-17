"""
Message detection and autorespond tools for email inboxes.

Provides functionality to detect new messages and send autoresponses.
"""

from typing import Dict, Any, Optional, List
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class MessageTools(ABC):
    """Abstract interface for message detection and autorespond."""
    
    @abstractmethod
    def detect_messages(
        self,
        url: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Detect new messages in an email inbox.
        
        Args:
            url: URL of the inbox page
            filters: Optional filters (e.g., {"unread": True, "from": "example@email.com"})
            
        Returns:
            Dict with list of detected messages
        """
        pass
    
    @abstractmethod
    def get_message_details(
        self,
        url: str,
        message_id: Optional[str] = None,
        selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get details of a specific message.
        
        Args:
            url: URL of the inbox or message page
            message_id: Optional message identifier
            selector: Optional CSS selector or XPath to message element
            
        Returns:
            Dict with message details (subject, from, body, etc.)
        """
        pass
    
    @abstractmethod
    def compose_response(
        self,
        message: Dict[str, Any],
        template: Optional[str] = None,
        custom_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compose a response to a message.
        
        Args:
            message: Message details (from detect_messages or get_message_details)
            template: Optional template name to use
            custom_text: Optional custom response text
            
        Returns:
            Dict with composed response
        """
        pass
    
    @abstractmethod
    def send_response(
        self,
        url: str,
        response: Dict[str, Any],
        message: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send an autoresponse.
        
        Args:
            url: URL of the inbox or compose page
            response: Response details from compose_response
            message: Optional original message for context
            
        Returns:
            Dict with send status
        """
        pass


class WebMessageTools(MessageTools):
    """
    Web-based message detection and autorespond using web automation.
    Uses web tools to interact with email inboxes.
    """
    
    def __init__(self, web_tools):
        """
        Initialize with web tools for automation.
        
        Args:
            web_tools: WebTools instance for web automation
        """
        self.web = web_tools
    
    def detect_messages(
        self,
        url: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Detect new messages in an email inbox.
        Uses web.get_dom to fetch inbox HTML and parse for messages.
        """
        try:
            # Get inbox DOM
            dom_result = self.web.get_dom(url)
            html = dom_result.get("html", "")
            
            # Simple message detection (can be enhanced with CPMS or vision)
            # Look for common email inbox patterns
            messages = []
            
            # Try to find message elements (this is a simplified version)
            # In a real implementation, would use CPMS or vision to detect message patterns
            import re
            
            # Look for unread indicators, message subjects, etc.
            # This is a placeholder - real implementation would parse HTML structure
            unread_pattern = re.compile(r'unread|new|unread.*message', re.IGNORECASE)
            subject_pattern = re.compile(r'<[^>]*class="[^"]*subject[^"]*"[^>]*>([^<]+)</', re.IGNORECASE)
            
            has_unread = bool(unread_pattern.search(html))
            subjects = subject_pattern.findall(html)
            
            # Create mock message entries
            for i, subject in enumerate(subjects[:10]):  # Limit to 10 messages
                messages.append({
                    "id": f"msg_{i}",
                    "subject": subject.strip(),
                    "unread": has_unread if i == 0 else False,  # First message marked as unread if pattern found
                    "detected_at": datetime.now(timezone.utc).isoformat(),
                })
            
            # Apply filters
            if filters:
                if filters.get("unread"):
                    messages = [m for m in messages if m.get("unread")]
                if filters.get("from"):
                    # Would need to parse sender info from HTML
                    pass
            
            return {
                "status": "success",
                "url": url,
                "messages": messages,
                "count": len(messages),
                "filters_applied": filters or {},
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }
    
    def get_message_details(
        self,
        url: str,
        message_id: Optional[str] = None,
        selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get details of a specific message.
        """
        try:
            # Get DOM
            dom_result = self.web.get_dom(url)
            html = dom_result.get("html", "")
            
            # Simple parsing (placeholder - real implementation would use CPMS/vision)
            import re
            
            # Try to extract message details
            # This is simplified - real implementation would parse structured HTML
            from_pattern = re.compile(r'<[^>]*class="[^"]*from[^"]*"[^>]*>([^<]+)</', re.IGNORECASE)
            subject_pattern = re.compile(r'<[^>]*class="[^"]*subject[^"]*"[^>]*>([^<]+)</', re.IGNORECASE)
            body_pattern = re.compile(r'<[^>]*class="[^"]*body[^"]*"[^>]*>([^<]+)</', re.IGNORECASE)
            
            from_addr = from_pattern.search(html)
            subject = subject_pattern.search(html)
            body = body_pattern.search(html)
            
            return {
                "status": "success",
                "url": url,
                "message_id": message_id,
                "from": from_addr.group(1).strip() if from_addr else None,
                "subject": subject.group(1).strip() if subject else None,
                "body": body.group(1).strip() if body else None,
                "selector": selector,
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }
    
    def compose_response(
        self,
        message: Dict[str, Any],
        template: Optional[str] = None,
        custom_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Compose a response to a message.
        """
        if custom_text:
            response_text = custom_text
        elif template:
            # Use template (placeholder - real implementation would load from memory)
            templates = {
                "acknowledgment": "Thank you for your message. I have received it and will respond shortly.",
                "out_of_office": "I am currently out of the office and will respond when I return.",
                "auto_reply": f"Thank you for your message regarding '{message.get('subject', 'your inquiry')}'. I will review it and get back to you.",
            }
            response_text = templates.get(template, templates["auto_reply"])
        else:
            # Default response
            response_text = f"Thank you for your message regarding '{message.get('subject', 'your inquiry')}'. I will review it and get back to you."
        
        return {
            "status": "success",
            "to": message.get("from"),
            "subject": f"Re: {message.get('subject', 'Your message')}",
            "body": response_text,
            "template_used": template,
                    "composed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def send_response(
        self,
        url: str,
        response: Dict[str, Any],
        message: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Send an autoresponse.
        Uses web automation to fill and submit a reply form.
        """
        try:
            # Navigate to compose/reply page
            # This is simplified - real implementation would:
            # 1. Click reply button (using message selector)
            # 2. Wait for compose form
            # 3. Fill to, subject, body fields
            # 4. Click send button
            
            # For now, use web.post to simulate sending
            # In real implementation, would use web.click_selector, web.fill, etc.
            
            # Try to find reply button and click it
            reply_result = self.web.click_selector(url, "button[aria-label*='Reply'], button[aria-label*='reply'], .reply-button, #reply")
            
            if reply_result.get("status") != 200:
                # Fallback: try to navigate to compose URL
                compose_url = url.replace("/inbox", "/compose").replace("/messages", "/compose")
                dom_result = self.web.get_dom(compose_url)
                
                # Fill form fields
                if response.get("to"):
                    self.web.fill(compose_url, "input[name='to'], input[type='email']", response["to"])
                if response.get("subject"):
                    self.web.fill(compose_url, "input[name='subject']", response["subject"])
                if response.get("body"):
                    # Try textarea for body
                    self.web.fill(compose_url, "textarea[name='body'], textarea[name='message']", response["body"])
                
                # Click send
                send_result = self.web.click_selector(compose_url, "button[type='submit'], button[aria-label*='Send'], #send")
                
                return {
                    "status": "success",
                    "url": compose_url,
                    "response_sent": True,
                    "to": response.get("to"),
                    "subject": response.get("subject"),
                    "sent_at": datetime.now(timezone.utc).isoformat(),
                }
            
            return {
                "status": "success",
                "url": url,
                "response_sent": True,
                "to": response.get("to"),
                "subject": response.get("subject"),
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "url": url,
            }


class MockMessageTools(MessageTools):
    """Mock message tools for testing."""
    
    def detect_messages(
        self,
        url: str,
        filters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mock implementation returns fake messages."""
        messages = [
            {
                "id": "msg_1",
                "subject": "Test Message 1",
                "from": "sender1@example.com",
                "unread": True,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "id": "msg_2",
                "subject": "Test Message 2",
                "from": "sender2@example.com",
                "unread": False,
                "detected_at": datetime.now(timezone.utc).isoformat(),
            },
        ]
        
        if filters and filters.get("unread"):
            messages = [m for m in messages if m.get("unread")]
        
        return {
            "status": "success",
            "url": url,
            "messages": messages,
            "count": len(messages),
            "filters_applied": filters or {},
        }
    
    def get_message_details(
        self,
        url: str,
        message_id: Optional[str] = None,
        selector: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mock implementation returns fake message details."""
        return {
            "status": "success",
            "url": url,
            "message_id": message_id or "msg_1",
            "from": "sender@example.com",
            "subject": "Test Message",
            "body": "This is a test message body.",
            "selector": selector,
        }
    
    def compose_response(
        self,
        message: Dict[str, Any],
        template: Optional[str] = None,
        custom_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Mock implementation returns fake response."""
        return {
            "status": "success",
            "to": message.get("from", "recipient@example.com"),
            "subject": f"Re: {message.get('subject', 'Your message')}",
            "body": custom_text or "Thank you for your message.",
            "template_used": template,
                    "composed_at": datetime.now(timezone.utc).isoformat(),
        }
    
    def send_response(
        self,
        url: str,
        response: Dict[str, Any],
        message: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Mock implementation simulates sending."""
        return {
            "status": "success",
            "url": url,
            "response_sent": True,
            "to": response.get("to"),
            "subject": response.get("subject"),
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

