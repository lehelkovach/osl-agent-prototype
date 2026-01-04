from typing import List, Optional
import argparse
import yaml
import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import os
from src.personal_assistant.logging_setup import configure_logging, get_logger

from src.personal_assistant.agent import PersonalAssistantAgent
from src.personal_assistant.events import EventBus
from src.personal_assistant.mock_tools import MockMemoryTools, MockCalendarTools, MockTaskTools, MockContactsTools, MockWebTools, MockShellTools
from dotenv import load_dotenv
from src.personal_assistant.procedure_builder import ProcedureBuilder
from src.personal_assistant.cpms_adapter import CPMSAdapter, CPMSNotInstalled
from src.personal_assistant.openai_client import OpenAIClient, FakeOpenAIClient
from src.personal_assistant.local_embedder import LocalEmbedder
from src.personal_assistant.web_tools import PlaywrightWebTools
from src.personal_assistant.shell_executor import RealShellTools


class ChatRequest(BaseModel):
    message: str


class EventCollectorBus(EventBus):
    def __init__(self, storage: List[dict]):
        super().__init__()
        self.storage = storage

    async def emit(self, event_type, payload):
        self.storage.append({"type": event_type, "payload": payload})
        await super().emit(event_type, payload)


def _build_detailed_response(result: dict, raw_llm: Optional[str], events: List[dict]) -> str:
    """Build a detailed, verbose response for chat display."""
    plan = result.get("plan", {})
    execution_results = result.get("execution_results", {})
    status = execution_results.get("status", "unknown")
    steps = plan.get("steps", [])
    
    parts = []
    
    # Start with raw LLM response if available
    if raw_llm:
        parts.append(raw_llm)
    
    # Add execution summary
    if status == "completed":
        parts.append(f"\n\n**Execution Summary:**")
        parts.append(f"Status: ✅ Completed successfully")
        
        if steps:
            parts.append(f"\n**Steps Executed ({len(steps)}):**")
            for i, step in enumerate(steps, 1):
                tool = step.get("tool", "unknown")
                params = step.get("params", {})
                comment = step.get("comment", "")
                
                # Find corresponding result
                step_result = None
                if isinstance(execution_results.get("steps"), list) and i <= len(execution_results["steps"]):
                    step_result = execution_results["steps"][i - 1]
                
                step_status = "✅" if step_result and step_result.get("status") in ("success", "completed") else "⏳"
                parts.append(f"{step_status} Step {i}: {tool}")
                if comment:
                    parts.append(f"   └─ {comment}")
                if params:
                    # Show key params (truncate long values)
                    key_params = {}
                    for k, v in list(params.items())[:3]:  # Show first 3 params
                        if isinstance(v, str) and len(v) > 50:
                            key_params[k] = v[:47] + "..."
                        else:
                            key_params[k] = v
                    if key_params:
                        parts.append(f"   └─ Params: {json.dumps(key_params, indent=2)}")
    elif status == "error":
        error = execution_results.get("error", "Unknown error")
        parts.append(f"\n\n**Execution Summary:**")
        parts.append(f"Status: ❌ Error")
        parts.append(f"Error: {error}")
    elif status == "ask_user":
        parts.append(f"\n\n**Execution Summary:**")
        parts.append(f"Status: ⏸️ Waiting for input")
    
    # Add event summary if available
    if events:
        event_types = {}
        for event in events:
            event_type = event.get("type", "unknown")
            event_types[event_type] = event_types.get(event_type, 0) + 1
        
        if len(event_types) > 0:
            parts.append(f"\n**Events:** {len(events)} total")
            for event_type, count in list(event_types.items())[:5]:  # Show top 5
                parts.append(f"  - {event_type}: {count}")
    
    return "\n".join(parts) if parts else "Ready to help."


def build_app(agent: PersonalAssistantAgent) -> FastAPI:
    app = FastAPI()
    
    @app.on_event("startup")
    async def startup_event():
        """Initialize service."""
        log = get_logger("service")
        log.info("service_starting")
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
            #mic-btn { padding:8px 12px; min-width:50px; }
            #mic-btn.listening { background:#f00; color:#fff; animation:pulse 1s infinite; }
            @keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
            #stt-status { font-size:12px; color:#666; padding:4px; }
            #stt-status.listening { color:#f00; font-weight:bold; }
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
            <div style="display:flex; flex-direction:column; flex:1;">
              <textarea id="msg" placeholder="Type a message or click mic to speak"></textarea>
              <div id="stt-status"></div>
            </div>
            <button id="mic-btn" onclick="toggleSpeechRecognition()" title="Click to start/stop voice input">🎤</button>
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
            // Speech-to-Text configuration
            let recognition = null;
            let isListening = false;
            let autoSendDelay = 3000; // Default 3 seconds, will be loaded from config
            let autoSendTimer = null;
            let finalTranscript = '';
            
            // Load STT config from server
            async function loadSTTConfig() {
              try {
                const resp = await fetch('/config/stt');
                const config = await resp.json();
                if (config.auto_send_delay) {
                  autoSendDelay = config.auto_send_delay;
                }
                if (!config.enabled) {
                  document.getElementById('mic-btn').style.display = 'none';
                }
              } catch (e) {
                console.warn('Could not load STT config, using defaults');
              }
            }
            loadSTTConfig();
            
            // Initialize Web Speech API
            if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
              const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
              recognition = new SpeechRecognition();
              recognition.continuous = true;
              recognition.interimResults = true;
              recognition.lang = 'en-US';
              
              recognition.onstart = () => {
                isListening = true;
                document.getElementById('mic-btn').classList.add('listening');
                document.getElementById('stt-status').textContent = 'Listening...';
                document.getElementById('stt-status').classList.add('listening');
              };
              
              recognition.onresult = (event) => {
                let interimTranscript = '';
                finalTranscript = '';
                
                for (let i = event.resultIndex; i < event.results.length; i++) {
                  const transcript = event.results[i][0].transcript;
                  if (event.results[i].isFinal) {
                    finalTranscript += transcript + ' ';
                  } else {
                    interimTranscript += transcript;
                  }
                }
                
                // Update textarea with current transcript
                const msgEl = document.getElementById('msg');
                const currentText = finalTranscript + interimTranscript;
                msgEl.value = currentText;
                
                // Update status
                if (interimTranscript) {
                  document.getElementById('stt-status').textContent = 'Listening: ' + interimTranscript;
                } else if (finalTranscript) {
                  document.getElementById('stt-status').textContent = 'Heard: ' + finalTranscript.trim();
                }
                
                // Reset auto-send timer on ANY new speech (interim or final)
                if (autoSendTimer) {
                  clearTimeout(autoSendTimer);
                  autoSendTimer = null;
                }
                
                // Set auto-send timer - will fire after 3 seconds of no new speech
                if (currentText.trim()) {
                  autoSendTimer = setTimeout(() => {
                    const msgValue = document.getElementById('msg').value.trim();
                    if (msgValue && isListening) {
                      console.log('Auto-sending after', autoSendDelay, 'ms of silence');
                      document.getElementById('stt-status').textContent = 'Auto-sending...';
                      send();
                      stopSpeechRecognition();
                    }
                  }, autoSendDelay);
                }
              };
              
              recognition.onerror = (event) => {
                console.error('Speech recognition error:', event.error);
                let errorMsg = 'Error: ' + event.error;
                if (event.error === 'not-allowed') {
                  errorMsg = 'Microphone permission denied. Please allow microphone access.';
                } else if (event.error === 'no-speech') {
                  errorMsg = 'No speech detected. Try again.';
                }
                document.getElementById('stt-status').textContent = errorMsg;
                stopSpeechRecognition();
              };
              
              recognition.onend = () => {
                // If recognition ended but we're still listening (continuous mode), restart
                // Otherwise, if we have text, the auto-send timer should handle it
                if (isListening) {
                  // In continuous mode, restart recognition if it ended unexpectedly
                  // But only if we don't have a pending auto-send
                  if (!autoSendTimer) {
                    const msgValue = document.getElementById('msg').value.trim();
                    if (msgValue) {
                      // We have text but no timer - set one now
                      autoSendTimer = setTimeout(() => {
                        if (document.getElementById('msg').value.trim() && isListening) {
                          document.getElementById('stt-status').textContent = 'Auto-sending...';
                          send();
                          stopSpeechRecognition();
                        }
                      }, autoSendDelay);
                    } else {
                      // No text, just restart
                      recognition.start();
                    }
                  }
                }
              };
            } else {
              document.getElementById('mic-btn').style.display = 'none';
              console.warn('Speech recognition not supported in this browser');
            }
            
            function toggleSpeechRecognition() {
              if (isListening) {
                stopSpeechRecognition();
              } else {
                startSpeechRecognition();
              }
            }
            
            function startSpeechRecognition() {
              if (!recognition) {
                alert('Speech recognition not available in this browser');
                return;
              }
              finalTranscript = '';
              document.getElementById('msg').value = '';
              recognition.start();
            }
            
            function stopSpeechRecognition() {
              if (recognition && isListening) {
                recognition.stop();
              }
              isListening = false;
              document.getElementById('mic-btn').classList.remove('listening');
              document.getElementById('stt-status').classList.remove('listening');
              if (autoSendTimer) {
                clearTimeout(autoSendTimer);
                autoSendTimer = null;
              }
              if (!finalTranscript.trim()) {
                document.getElementById('stt-status').textContent = '';
              }
            }
            
            async function send() {
              const msg = document.getElementById('msg').value;
              if (!msg.trim()) return;
              
              // Stop speech recognition if active
              if (isListening) {
                stopSpeechRecognition();
              }
              
              try {
                const resp = await fetch('/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({message: msg})});
                if (!resp.ok) throw new Error(resp.statusText);
                document.getElementById('msg').value='';
                document.getElementById('stt-status').textContent = '';
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
            log.error("chat_error", error=str(exc), exc_info=True)
            chat_history.append({"role": "user", "content": body.message})
            chat_history.append({"role": "assistant", "content": "Error handling request."})
            return {"plan": {"error": str(exc)}, "results": {"status": "error"}, "events": []}

        raw_llm = result.get("plan", {}).get("raw_llm") or result.get("raw_llm")
        log.info("chat_response", plan=result["plan"], events=len(events))
        chat_history.append({"role": "user", "content": body.message})
        
        # Build detailed response for chat
        assistant_content = _build_detailed_response(result, raw_llm, events)
        
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
    
    @app.get("/config/stt")
    def get_stt_config():
        """Return STT configuration for browser."""
        cfg = load_config(None)
        stt_cfg = cfg.get("stt", {})
        browser_cfg = stt_cfg.get("browser_stt", {})
        return {
            "enabled": browser_cfg.get("enabled", True),
            "auto_send_delay": browser_cfg.get("auto_send_delay", 3000)
        }

    return app


def load_config(config_path: str | None) -> dict:
    cfg: dict = {}
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    default_path = os.path.join(base_dir, "config", "default.yaml")
    for path in [default_path, config_path]:
        if path and os.path.exists(path):
            with open(path, "r") as f:
                cfg.update(yaml.safe_load(f) or {})
    return cfg


def default_agent_from_env(config: dict | None = None) -> PersonalAssistantAgent:
    load_dotenv(".env.local")
    load_dotenv()
    cfg = config or {}
    memory = None
    log = get_logger("service")
    
    # Store TTS/STT capability in memory if not already present (will be called after agent creation)
    embedding_backend = os.getenv("EMBEDDING_BACKEND", cfg.get("embedding_backend", "openai"))
    use_fake_openai = os.getenv("USE_FAKE_OPENAI", str(cfg.get("use_fake_openai", False))).lower() in ("1", "true", "yes")
    use_cpms_for_procs = os.getenv("USE_CPMS_FOR_PROCS", str(cfg.get("use_cpms_for_procs", False))).lower() in ("1", "true", "yes")
    use_playwright = os.getenv("USE_PLAYWRIGHT", str(cfg.get("use_playwright", False))).lower() in ("1", "true", "yes")
    arango_cfg = cfg.get("arango", {}) if isinstance(cfg, dict) else {}
    chroma_cfg = cfg.get("chroma", {}) if isinstance(cfg, dict) else {}
    log.info(
        "startup_flags",
        embedding_backend=embedding_backend,
        use_fake_openai=use_fake_openai,
        use_local_embed=embedding_backend.lower() == "local",
        use_cpms=use_cpms_for_procs,
        use_playwright=use_playwright,
        arango_url=os.getenv("ARANGO_URL", arango_cfg.get("url", "")),
        chroma_enabled=bool(os.getenv("ARANGO_URL") == "" and os.getenv("CHROMA_PATH", chroma_cfg.get("path", ".chroma"))),
    )
    arango_url = os.getenv("ARANGO_URL", arango_cfg.get("url", ""))
    if arango_url:
        try:
            from src.personal_assistant.arango_memory import ArangoMemoryTools
            memory = ArangoMemoryTools(
                db_name=os.getenv("ARANGO_DB", arango_cfg.get("db", "agent_memory")),
                url=arango_url,
                username=os.getenv("ARANGO_USER", arango_cfg.get("user", "")),
                password=os.getenv("ARANGO_PASSWORD", arango_cfg.get("password", "")),
                verify=os.getenv("ARANGO_VERIFY", arango_cfg.get("verify", "")) or True,
            )
            print(f"Using ArangoDB memory at {arango_url} db={memory.db_name}")
        except Exception as e:
            print(f"Arango unavailable, trying ChromaDB (error: {e})")
    if memory is None:
        try:
            from src.personal_assistant.chroma_memory import ChromaMemoryTools
            chroma_path = os.getenv("CHROMA_PATH", chroma_cfg.get("path", ".chroma"))
            memory = ChromaMemoryTools(path=chroma_path)
            print(f"Using ChromaDB-backed memory at {chroma_path}")
        except Exception as e:
            print(f"Falling back to in-memory mock memory (Chroma unavailable: {e})")
            memory = MockMemoryTools()
    calendar = MockCalendarTools()
    tasks = MockTaskTools()
    contacts = MockContactsTools()
    # Use OpenAI embeddings if available; allow forcing fake client via USE_FAKE_OPENAI.
    use_fake = use_fake_openai
    use_local_embed = embedding_backend.lower() == "local"
    local_embedder = LocalEmbedder() if use_local_embed else None
    try:
        if use_fake:
            fake_resp = os.getenv("FAKE_OPENAI_CHAT_RESPONSE", '{"intent":"inform","steps":[]}')
            openai_client = FakeOpenAIClient(chat_response=fake_resp, embedding=[0.0, 0.0, 0.0])
        elif use_local_embed:
            openai_client = OpenAIClient()  # keep chat via OpenAI unless also disabled
        else:
            openai_client = OpenAIClient()
        def _embed(text: str):
            try:
                if local_embedder:
                    return local_embedder.embed(text)
                return openai_client.embed(text)
            except Exception:
                return None
    except Exception:
        openai_client = None
        _embed = lambda text: None

    procedure_builder = ProcedureBuilder(memory, embed_fn=_embed)
    # Select web and shell tools
    web_tools = None
    shell_tools = None
    if use_playwright:
        try:
            web_tools = PlaywrightWebTools(headless=True)
        except Exception as exc:
            log.warning("playwright_unavailable_falling_back_to_mock", error=str(exc))
            web_tools = MockWebTools()
    else:
        web_tools = MockWebTools()
    shell_tools = RealShellTools()

    cpms_adapter = None
    if use_cpms_for_procs:
        try:
            cpms_adapter = CPMSAdapter.from_env()
        except CPMSNotInstalled:
            cpms_adapter = None
    agent = PersonalAssistantAgent(
        memory,
        calendar,
        tasks,
        contacts=contacts,
        web=web_tools,
        shell=shell_tools,
        procedure_builder=procedure_builder,
        cpms=cpms_adapter,
        openai_client=openai_client,
    )
    
    return agent


def run_service(host: str = "0.0.0.0", port: int = 8000, debug: bool = False, log_level: str = "info", config_path: str | None = None):
    """Programmatic entrypoint used by scripts."""
    configure_logging()
    log = get_logger("service")
    cfg = load_config(config_path)
    agent = default_agent_from_env(cfg)
    app = build_app(agent)
    log.info(
        "starting_service",
        host=host,
        port=port,
        debug=debug,
        log_level=log_level,
        config_path=config_path,
    )
    uvicorn.run(app, host=host, port=port, reload=debug, access_log=not debug, log_level=log_level, log_config=None)


def main():
    parser = argparse.ArgumentParser(description="Run the agent service.")
    parser.add_argument("--config", type=str, default=None, help="Path to YAML config file")
    parser.add_argument("--host", type=str, default=os.getenv("HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8000")))
    parser.add_argument("--debug", action="store_true", help="Enable reload/debug")
    parser.add_argument("--log-level", type=str, default=os.getenv("LOG_LEVEL", "info"))
    args = parser.parse_args()
    run_service(host=args.host, port=args.port, debug=args.debug, log_level=args.log_level, config_path=args.config)


if __name__ == "__main__":
    main()

# ASGI app for uvicorn import (avoid nested uvicorn.run in main)
try:
    _default_agent = default_agent_from_env()
    app = build_app(_default_agent)
except Exception:
    app = None
