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
    runs: dict = {}

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
            body { margin:0; font-family: sans-serif; display:flex; flex-direction:column; height:100vh; }
            #tabs { display:flex; border-bottom:1px solid #ccc; }
            .tab { padding:8px 12px; cursor:pointer; }
            .tab.active { background:#e0e0e0; font-weight:bold; }
            .pane { display:none; flex:1; overflow:auto; }
            .pane.active { display:flex; flex-direction:column; }
            #history, #logview, #runslist, #rundeets { flex:1; overflow:auto; padding:8px; }
            #logview { background:#111; color:#0f0; font-family: monospace; }
            #chat-output { flex:1; overflow:auto; padding:8px; }
            #chat-actions { flex:0 0 120px; overflow:auto; padding:8px; background:#f9f9f9; }
            #input { display:flex; padding:8px; gap:8px; border-top:1px solid #ccc; }
            textarea { flex:1; height:60px; }
            button { padding:8px 12px; }
            #runslist { border-right:1px solid #ccc; min-width:200px; }
            #runcontainer { display:flex; flex:1; }
          </style>
        </head>
        <body>
          <div id="tabs">
            <div class="tab active" data-pane="chat">Chat</div>
            <div class="tab" data-pane="logs">Console Logs</div>
            <div class="tab" data-pane="runs">Runs</div>
          </div>
          <div id="chat" class="pane active">
            <div id="chat-output"></div>
            <div id="chat-actions"></div>
          </div>
          <div id="logs" class="pane">
            <div id="logview"></div>
          </div>
          <div id="runs" class="pane">
            <div id="runcontainer">
              <div id="runslist"></div>
              <div id="rundeets"></div>
            </div>
          </div>
          <div id="input">
            <textarea id="msg" placeholder="Type a message"></textarea>
            <button onclick="send()">Send</button>
          </div>
          <script>
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(t => t.addEventListener('click', () => {
              tabs.forEach(x => x.classList.remove('active'));
              document.querySelectorAll('.pane').forEach(p => p.classList.remove('active'));
              t.classList.add('active');
              document.getElementById(t.dataset.pane).classList.add('active');
            }));

            async function safeFetch(url, options) {
              try {
                const resp = await fetch(url, options);
                if (!resp.ok) throw new Error(resp.statusText);
                return await resp.json();
              } catch (e) {
                console.error("Fetch error", url, e);
                return [];
              }
            }

            async function refresh() {
              const hist = await safeFetch('/history');
              const logs = await safeFetch('/logs');
              const runs = await safeFetch('/runs');
              const co = document.getElementById('chat-output');
              co.innerHTML = hist.map(entry => '<div><strong>'+entry.role+':</strong> '+entry.content+'</div>').join('');
              const ca = document.getElementById('chat-actions');
              const toolEvents = logs.filter(l => l.type === 'tool_invoked');
              ca.innerHTML = '<div><strong>Actions:</strong></div>' + toolEvents.map(e => '<div>'+JSON.stringify(e.payload||e)+'</div>').join('');
              const lv = document.getElementById('logview');
              lv.innerText = logs.map(l => JSON.stringify(l)).join('\\n');
              const rl = document.getElementById('runslist');
              rl.innerHTML = runs.map(r => '<div><a href="#" onclick="loadRun(\\''+r.trace_id+'\\')">'+r.trace_id+'</a> ('+r.events+' events)</div>').join('');
            }
            async function send() {
              const msg = document.getElementById('msg').value;
              if (!msg.trim()) return;
              try {
                const resp = await fetch('/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg})});
                if (!resp.ok) throw new Error(resp.statusText);
                document.getElementById('msg').value='';
                refresh();
              } catch (e) {
                console.error("Chat send failed", e);
              }
            }
            async function loadRun(tid) {
              const data = await safeFetch('/runs/'+tid);
              const rd = document.getElementById('rundeets');
              const ev = (data.events||[]).map(e => '<div><code>'+e.type+'</code> '+JSON.stringify(e.payload||e)+'</div>').join('');
              rd.innerHTML = '<div><strong>Trace:</strong> '+tid+'</div><div><strong>Plan:</strong><pre>'+JSON.stringify(data.plan,null,2)+'</pre></div><div><strong>Events:</strong>'+ev+'</div>';
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
        try:
            result = agent.execute_request(body.message)
        except Exception as exc:
            log.error("chat_error", error=str(exc))
            chat_history.append({"role": "user", "content": body.message})
            chat_history.append({"role": "assistant", "content": "Error handling request."})
            return {"plan": {"error": str(exc)}, "results": {"status": "error"}, "events": []}

        raw_llm = result.get("plan", {}).get("raw_llm") or result.get("raw_llm")
        log.info("chat_response", plan=result["plan"], events=len(events))
        chat_history.append({"role": "user", "content": body.message})
        assistant_content = ""
        if raw_llm:
            assistant_content = raw_llm
        else:
            try:
                assistant_content = json.dumps(result["plan"])
            except Exception:
                assistant_content = str(result.get("plan", "")) or "Ready to help."
        if not assistant_content.strip():
            assistant_content = "Ready to help."
        chat_history.append({"role": "assistant", "content": assistant_content})
        log_history.extend(events)
        trace_id = result["plan"].get("trace_id") or result["execution_results"].get("trace_id") if isinstance(result["execution_results"], dict) else None
        if trace_id:
            runs[trace_id] = {"events": events, "plan": result["plan"], "results": result["execution_results"]}
        return {"plan": result["plan"], "results": result["execution_results"], "events": events}

    @app.get("/history", response_class=JSONResponse)
    def history():
        return chat_history

    @app.get("/logs", response_class=JSONResponse)
    def logs():
        return log_history[-200:]

    @app.get("/runs")
    def list_runs():
        return [{"trace_id": tid, "events": len(data.get("events", []))} for tid, data in runs.items()]

    @app.get("/runs/{trace_id}")
    def get_run(trace_id: str):
        return runs.get(trace_id, {})

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

# ASGI app for uvicorn import (avoid nested uvicorn.run in main)
try:
    _default_agent = default_agent_from_env()
    app = build_app(_default_agent)
except Exception:
    app = None
