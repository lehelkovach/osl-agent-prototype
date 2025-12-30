from typing import List

from fastapi import FastAPI
from pydantic import BaseModel
import uvicorn
import os

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.events import EventBus
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockContactsTools
from dotenv import load_dotenv


class ChatRequest(BaseModel):
    message: str


class EventCollectorBus(EventBus):
    def __init__(self, storage: List[dict]):
        super().__init__()
        self.storage = storage

    async def emit(self, event_type, payload):
        self.storage.append({"type": event_type, "payload": payload})
        await super().emit(event_type, payload)


def build_app(agent: PersonalAssistantAgent) -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/chat")
    def chat(body: ChatRequest):
        events: List[dict] = []
        bus = EventCollectorBus(events)
        agent.event_bus = bus
        result = agent.execute_request(body.message)
        return {"plan": result["plan"], "results": result["execution_results"], "events": events}

    return app


def default_agent_from_env() -> PersonalAssistantAgent:
    load_dotenv(".env.local")
    load_dotenv()
    memory = None
    if os.getenv("ARANGO_URL"):
        try:
            from src.personal_assistant.arango_memory import ArangoMemoryTools
            memory = ArangoMemoryTools()
            print(f"Using ArangoDB memory at {os.getenv('ARANGO_URL')} db={os.getenv('ARANGO_DB', 'agent_memory')}")
        except Exception as e:
            print(f"Arango unavailable, trying ChromaDB (error: {e})")
    if memory is None:
        try:
            from src.personal_assistant.chroma_memory import ChromaMemoryTools
            memory = ChromaMemoryTools()
            print("Using ChromaDB-backed memory at ./.chroma")
        except Exception as e:
            print(f"Falling back to in-memory mock memory (Chroma unavailable: {e})")
            memory = MockMemoryTools()
    calendar = MockCalendarTools()
    tasks = MockTaskTools()
    contacts = MockContactsTools()
    return PersonalAssistantAgent(memory, calendar, tasks, contacts=contacts)


def main():
    agent = default_agent_from_env()
    app = build_app(agent)
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
