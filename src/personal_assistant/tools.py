from abc import ABC, abstractmethod
from typing import List, Dict, Any, Union, Optional

from src.personal_assistant.models import Node, Edge, Provenance

class MemoryTools(ABC):
    """Interface for memory read and write operations."""

    @abstractmethod
    def search(
        self,
        query_text: str,
        top_k: int,
        filters: Optional[Dict[str, Any]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Dict[str, Any]]:
        """Searches memory for relevant nodes or edges."""
        pass

    @abstractmethod
    def upsert(self, item: Union[Node, Edge], provenance: Provenance, embedding_request: Optional[bool] = False) -> Dict[str, Any]:
        """Inserts or updates a node or edge in memory."""
        pass

class CalendarTools(ABC):
    """Interface for calendar operations."""

    @abstractmethod
    def list(self, date_range: Dict[str, str]) -> List[Dict[str, Any]]:
        """Lists calendar events within a given date range."""
        pass

    @abstractmethod
    def create_event(self, title: str, start: str, end: str, attendees: List[str], location: str, notes: str) -> Dict[str, Any]:
        """Creates a new calendar event."""
        pass

class TaskTools(ABC):
    """Interface for task management operations."""

    @abstractmethod
    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Lists tasks based on optional filters."""
        pass

    @abstractmethod
    def create(self, title: str, due: Optional[str], priority: int, notes: str, links: List[str]) -> Dict[str, Any]:
        """Creates a new task."""
        pass

class ContactsTools(ABC):
    """Interface for contacts management operations."""

    @abstractmethod
    def list(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Lists contacts based on optional filters."""
        pass

    @abstractmethod
    def create(self, name: str, emails: List[str], phones: List[str], org: Optional[str], notes: str, tags: List[str]) -> Dict[str, Any]:
        """Creates a new contact."""
        pass


class WebTools(ABC):
    """Interface for primitive web commandlets."""

    @abstractmethod
    def get(self, url: str) -> Dict[str, Any]:
        """Fetch a URL and return status/body/headers."""
        pass

    @abstractmethod
    def post(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST a payload to a URL and return status/body/headers."""
        pass

    @abstractmethod
    def screenshot(self, url: str) -> Dict[str, Any]:
        """Capture a screenshot of the DOM at a URL."""
        pass

    @abstractmethod
    def get_dom(self, url: str) -> Dict[str, Any]:
        """Fetch a URL and return html + screenshot for vision-based inspection."""
        pass

    @abstractmethod
    def click_xy(self, url: str, x: int, y: int) -> Dict[str, Any]:
        """Click at coordinates on the page."""
        pass

    @abstractmethod
    def click_selector(self, url: str, selector: str) -> Dict[str, Any]:
        """Click an element by selector."""
        pass

    @abstractmethod
    def click_xpath(self, url: str, xpath: str) -> Dict[str, Any]:
        """Click an element by xpath."""
        pass

    @abstractmethod
    def fill(self, url: str, selector: str, text: str) -> Dict[str, Any]:
        """Fill text into an element."""
        pass

    @abstractmethod
    def wait_for(self, url: str, selector: str, timeout_ms: int = 5000) -> Dict[str, Any]:
        """Wait for selector to appear."""
        pass
