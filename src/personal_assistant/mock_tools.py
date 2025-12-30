from typing import List, Dict, Any, Union, Optional
import math
import base64
from src.personal_assistant.models import Node, Edge, Provenance
from src.personal_assistant.tools import MemoryTools, CalendarTools, TaskTools, WebTools, ContactsTools

class MockMemoryTools(MemoryTools):
    """A mock implementation of MemoryTools that stores data in-memory."""
    def __init__(self):
        self.nodes: Dict[str, Node] = {}
        self.edges: Dict[str, Edge] = {}

    def search(
        self,
        query_text: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Simulates searching memory with optional embedding-based scoring."""
        print(f"Searching memory for '{query_text}' with top_k={top_k} and filters={filters}")
        candidates = list(self.nodes.values())

        def cosine(a: List[float], b: List[float]) -> float:
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = math.sqrt(sum(x * x for x in a))
            norm_b = math.sqrt(sum(x * x for x in b))
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot / (norm_a * norm_b)

        if query_embedding:
            candidates.sort(
                key=lambda n: cosine(query_embedding, n.llm_embedding or []),
                reverse=True,
            )

        results = []
        for node in candidates[:top_k]:
            results.append(node.__dict__)
        return results

    def upsert(self, item: Union[Node, Edge], provenance: Provenance, embedding_request: Optional[bool] = False) -> Dict[str, Any]:
        """Simulates upserting an item. Adds it to the in-memory store."""
        if isinstance(item, Node):
            self.nodes[item.uuid] = item
            print(f"Upserted Node: {item.uuid}")
        elif isinstance(item, Edge):
            self.edges[item.uuid] = item
            print(f"Upserted Edge: {item.uuid}")
        
        return {"status": "success", "uuid": item.uuid}

class MockCalendarTools(CalendarTools):
    """A mock implementation of CalendarTools that stores data in-memory."""
    def __init__(self):
        self.events: List[Dict[str, Any]] = []

    def list(self, date_range: Dict[str, str]) -> List[Dict[str, Any]]:
        """Simulates listing calendar events."""
        print(f"Listing calendar events for range: {date_range}")
        return self.events

    def create_event(self, title: str, start: str, end: str, attendees: List[str], location: str, notes: str) -> Dict[str, Any]:
        """Simulates creating a calendar event."""
        event = {
            "title": title, "start": start, "end": end, 
            "attendees": attendees, "location": location, "notes": notes
        }
        self.events.append(event)
        print(f"Created event: {title}")
        return {"status": "success", "event": event}

class MockTaskTools(TaskTools):
    """A mock implementation of TaskTools that stores data in-memory."""
    def __init__(self):
        self.tasks: List[Dict[str, Any]] = []

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Simulates listing tasks."""
        print(f"Listing tasks with filters: {filters}")
        return self.tasks

    def create(self, title: str, due: Optional[str], priority: int, notes: str, links: List[str]) -> Dict[str, Any]:
        """Simulates creating a task."""
        task = {
            "title": title, "due": due, "priority": priority, 
            "notes": notes, "links": links, "status": "pending"
        }
        self.tasks.append(task)
        print(f"Created task: {title}")
        return {"status": "success", "task": task}

class MockContactsTools(ContactsTools):
    """A mock implementation of ContactsTools that stores contacts in-memory."""
    def __init__(self):
        self.contacts: List[Dict[str, Any]] = []

    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        print(f"Listing contacts with filters: {filters}")
        if not filters:
            return self.contacts
        results = []
        for c in self.contacts:
            match = True
            for k, v in filters.items():
                if c.get(k) != v:
                    match = False
                    break
            if match:
                results.append(c)
        return results

    def create(self, name: str, emails: List[str], phones: List[str], org: Optional[str], notes: str, tags: List[str]) -> Dict[str, Any]:
        contact = {
            "name": name,
            "emails": emails,
            "phones": phones,
            "org": org,
            "notes": notes,
            "tags": tags,
            "status": "active",
        }
        self.contacts.append(contact)
        print(f"Created contact: {name}")
        return {"status": "success", "contact": contact}


class MockWebTools(WebTools):
    """A mock implementation of WebTools that records calls."""

    def __init__(self):
        self.history: List[Dict[str, Any]] = []

    def get(self, url: str) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "body": f"<html><body>Mock GET {url}</body></html>"}
        self.history.append({"method": "GET", "url": url, "response": response})
        print(f"Mock GET: {url}")
        return response

    def post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "body": {"received": payload}}
        self.history.append({"method": "POST", "url": url, "payload": payload, "response": response})
        print(f"Mock POST: {url} payload={payload}")
        return response

    def screenshot(self, url: str) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "image": f"screenshot-of-{url}"}
        self.history.append({"method": "SCREENSHOT", "url": url, "response": response})
        print(f"Mock SCREENSHOT: {url}")
        return response

    def get_dom(self, url: str) -> Dict[str, Any]:
        html = f"<html><body>Mock DOM for {url}</body></html>"
        screenshot_b64 = base64.b64encode(f"screenshot-{url}".encode()).decode()
        response = {
            "status": 200,
            "url": url,
            "html": html,
            "screenshot_base64": screenshot_b64,
        }
        self.history.append({"method": "GET_DOM", "url": url, "response": response})
        print(f"Mock GET_DOM: {url}")
        return response

    def locate_bounding_box(self, url: str, query: str) -> Dict[str, Any]:
        response = {
            "status": 200,
            "url": url,
            "query": query,
            "bbox": {"x": 10, "y": 20, "width": 100, "height": 20},
        }
        self.history.append({"method": "LOCATE_BBOX", "url": url, "query": query, "response": response})
        print(f"Mock LOCATE_BBOX: {url} {query}")
        return response

    def click_xy(self, url: str, x: int, y: int) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "action": "click_xy", "x": x, "y": y}
        self.history.append({"method": "CLICK_XY", "url": url, "x": x, "y": y, "response": response})
        print(f"Mock CLICK_XY: {url} ({x},{y})")
        return response

    def click_selector(self, url: str, selector: str) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "action": "click_selector", "selector": selector}
        self.history.append({"method": "CLICK_SELECTOR", "url": url, "selector": selector, "response": response})
        print(f"Mock CLICK_SELECTOR: {url} {selector}")
        return response

    def click_xpath(self, url: str, xpath: str) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "action": "click_xpath", "xpath": xpath}
        self.history.append({"method": "CLICK_XPATH", "url": url, "xpath": xpath, "response": response})
        print(f"Mock CLICK_XPATH: {url} {xpath}")
        return response

    def fill(self, url: str, selector: str, text: str) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "action": "fill", "selector": selector, "text": text}
        self.history.append({"method": "FILL", "url": url, "selector": selector, "text": text, "response": response})
        print(f"Mock FILL: {url} {selector}={text}")
        return response

    def wait_for(self, url: str, selector: str, timeout_ms: int = 5000) -> Dict[str, Any]:
        response = {"status": 200, "url": url, "action": "wait_for", "selector": selector, "timeout_ms": timeout_ms}
        self.history.append({"method": "WAIT_FOR", "url": url, "selector": selector, "timeout_ms": timeout_ms, "response": response})
        print(f"Mock WAIT_FOR: {url} {selector} timeout={timeout_ms}")
        return response
