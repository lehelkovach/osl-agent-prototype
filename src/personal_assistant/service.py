from typing import List

from fastapi import FastAPI
from pydantic import BaseModel

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.events import EventBus


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
