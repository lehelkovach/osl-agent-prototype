from typing import List

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import os
from src.personal_assistant.logging_setup import configure_logging, get_logger

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.events import EventBus
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockContactsTools
from dotenv import load_dotenv
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.cpms_adapter import CPMSAdapter, CPMSNotInstalled
from src.personal_assistant.openai_client import OpenAIClient


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
    configure_logging()
    log = get_logger("service")
    chat_history: List[dict] = []
    log_history: List[dict] = []

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/ui", response_class=HTMLResponse)
    def ui():
        return """
        <!doctype html>
        <html>
        <head>
          <style>
            body { margin:0; font-family: sans-serif; display:flex; height:100vh; }
            #chat, #logs { flex:1; display:flex; flex-direction:column; border:1px solid #ccc; }
            header { padding:8px; background:#f5f5f5; font-weight:bold; }
            #history { flex:1; overflow:auto; padding:8px; }
            #logview { flex:1; overflow:auto; padding:8px; background:#111; color:#0f0; font-family: monospace; }
            #input { display:flex; padding:8px; gap:8px; }
            textarea { flex:1; height:60px; }
            button { padding:8px 12px; }
          </style>
        </head>
        <body>
          <div id="chat">
            <header>Chat</header>
            <div id="history"></div>
            <div id="input">
              <textarea id="msg" placeholder="Type a message"></textarea>
              <button onclick="send()">Send</button>
            </div>
          </div>
          <div id="logs">
            <header>Logs</header>
            <div id="logview"></div>
          </div>
          <script>
            async function refresh() {
              const hist = await fetch('/history').then(r=>r.json());
              const logs = await fetch('/logs').then(r=>r.json());
              const h = document.getElementById('history');
              h.innerHTML = hist.map(entry => '<div><strong>'+entry.role+':</strong> '+entry.content+'</div>').join('');
              const lv = document.getElementById('logview');
              lv.innerText = logs.map(l => JSON.stringify(l)).join('\\n');
            }
            async function send() {
              const msg = document.getElementById('msg').value;
              if (!msg.trim()) return;
              await fetch('/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg})});
              document.getElementById('msg').value='';
              refresh();
            }
            setInterval(refresh, 2000);
            refresh();
          </script>
        </body>
        </html>
        """

    @app.post("/chat")
    def chat(body: ChatRequest):
        events: List[dict] = []
        bus = EventCollectorBus(events)
        agent.event_bus = bus
        log = get_logger("chat")
        log.info("chat_request", message=body.message)
        result = agent.execute_request(body.message)
        log.info("chat_response", plan=result["plan"], events=len(events))
        chat_history.append({"role": "user", "content": body.message})
        chat_history.append({"role": "assistant", "content": str(result["plan"])})
        log_history.extend(events)
        return {"plan": result["plan"], "results": result["execution_results"], "events": events}

    @app.get("/history", response_class=JSONResponse)
    def history():
        return chat_history

    @app.get("/logs", response_class=JSONResponse)
    def logs():
        return log_history[-200:]

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
    # Use OpenAI embeddings if available; fall back to a no-op embedding to avoid failures.
    try:
        openai_client = OpenAIClient()
        def _embed(text: str):
            try:
                return openai_client.embed(text)
            except Exception:
                return None
    except Exception:
        openai_client = None
        _embed = lambda text: None

    procedure_builder = ProcedureBuilder(memory, embed_fn=_embed)
    cpms_adapter = None
    try:
        cpms_adapter = CPMSAdapter.from_env()
    except CPMSNotInstalled:
        cpms_adapter = None
    return PersonalAssistantAgent(
        memory,
        calendar,
        tasks,
        contacts=contacts,
        procedure_builder=procedure_builder,
        cpms=cpms_adapter,
        openai_client=openai_client,
    )


def main():
    configure_logging()
    log = get_logger("service")
    agent = default_agent_from_env()
    app = build_app(agent)
    port = int(os.getenv("PORT", "8000"))
    log.info("starting_service", port=port)
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    main()
