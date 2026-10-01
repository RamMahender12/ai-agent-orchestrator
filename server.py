import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv

# Ensure root directory is on Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

load_dotenv()

from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database import Database
from core.models import OrchestrationRun
from agents.agent_a_openai import AgentAOpenAI
from agents.agent_b_claude import AgentBClaude
from agents.agent_c_supervisor import AgentCSupervisor
from core import a2a as a2a_proto
from core.llm import HELP, _key, has_api_key

app = FastAPI(title="AI Agent Supervisor & Multi-Agent Orchestrator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_no_cache_headers(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

db = Database()
_supervisor = AgentCSupervisor(database=db)
_supervisor.bind_a2a()

# Active SSE subscriber queues keyed by run_id
run_queues: Dict[str, List[asyncio.Queue]] = {}

class OrchestrationRequest(BaseModel):
    task: str
    simulation_mode: bool = False
    model_a: Optional[str] = "poolside/laguna-s-2.1:free"
    model_b: Optional[str] = "nvidia/nemotron-3-ultra-550b-a55b:free"
    quality_threshold: Optional[int] = 80

@app.get("/api/health")
async def health_check():
    load_dotenv(override=True)
    return {
        "status": "healthy",
        "has_openai_key": bool(_key("OPENAI_API_KEY")),
        "has_anthropic_key": bool(_key("ANTHROPIC_API_KEY")),
        "default_mode": "live" if has_api_key() else "needs_key"
    }

class ChatRequest(BaseModel):
    agent_target: str = "supervisor"  # "supervisor", "agent_a", "agent_b", "triad"
    message: str
    simulation_mode: Optional[bool] = False
    history: Optional[List[Dict[str, str]]] = None

@app.post("/api/chat")
async def chat_with_agents(req: ChatRequest):
    """Direct interactive chat with individual agents or collaborative triad."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    load_dotenv(override=True)
    sim_mode = bool(req.simulation_mode)

    agent_a = AgentAOpenAI(simulation_mode=sim_mode)
    agent_b = AgentBClaude(simulation_mode=sim_mode)
    supervisor = AgentCSupervisor(agent_a=agent_a, agent_b=agent_b, database=db)

    target = req.agent_target.lower()

    if target in ["agent_a", "openai"]:
        reply, usage = agent_a.chat(req.message, req.history)
        return {
            "responses": [{
                "sender": agent_a.name,
                "provider": "OpenAI",
                "role": "Creator & Implementer",
                "reply": reply,
                "tokens": usage.model_dump()
            }]
        }
    elif target in ["agent_b", "claude"]:
        reply, usage = agent_b.chat(req.message, req.history)
        return {
            "responses": [{
                "sender": agent_b.name,
                "provider": "Anthropic",
                "role": "Quality Auditor & Evaluator",
                "reply": reply,
                "tokens": usage.model_dump()
            }]
        }
    elif target in ["triad", "all"]:
        responses = supervisor.triad_chat(req.message)
        return {"responses": responses}
    else:  # default supervisor
        resp = supervisor.chat(req.message)
        return {"responses": [resp]}


@app.get("/api/agents")
async def get_agents():
    """Retrieve all discovered and registered agents from SQLite."""
    return db.get_registered_agents()

@app.get("/api/runs")
async def get_runs():
    """Retrieve recent runs from SQLite."""
    return db.get_run_history(limit=25)

@app.delete("/api/runs")
async def delete_all_runs():
    """Clear the run history."""
    db.delete_runs()
    return {"deleted": "all"}

@app.delete("/api/runs/{run_id}")
async def delete_run(run_id: str):
    db.delete_runs(run_id)
    return {"deleted": run_id}

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Retrieve detailed execution log, steps, and evaluations for a run."""
    details = db.get_run_details(run_id)
    if not details:
        raise HTTPException(status_code=404, detail="Run not found")
    return details

@app.post("/api/orchestrate")
async def start_orchestration(req: OrchestrationRequest, background_tasks: BackgroundTasks):
    """Initiates a multi-agent orchestration workflow."""
    if not req.task.strip():
        raise HTTPException(status_code=400, detail="Task cannot be empty")

    load_dotenv(override=True)
    sim_mode = bool(req.simulation_mode)
    if not sim_mode and not has_api_key():
        raise HTTPException(status_code=400, detail=HELP)

    # Pre-generate run_id so client can subscribe to SSE immediately
    import uuid
    run_id = f"run_{uuid.uuid4().hex[:8]}"
    run_queues[run_id] = []

    background_tasks.add_task(
        execute_orchestration_background,
        run_id,
        req.task,
        sim_mode,
        req.model_a,
        req.model_b,
        req.quality_threshold
    )

    return {
        "run_id": run_id,
        "status": "QUEUED",
        "simulation_mode": sim_mode,
        "stream_url": f"/api/stream/{run_id}"
    }

async def execute_orchestration_background(
    run_id: str,
    task: str,
    simulation_mode: bool,
    model_a: str,
    model_b: str,
    threshold: int
):
    loop = asyncio.get_event_loop()

    def dispatch_event(event_type: str, data: Dict[str, Any]):
        data_json = json.dumps({"event": event_type, **data}, default=str)
        if run_id in run_queues:
            for q in run_queues[run_id]:
                loop.call_soon_threadsafe(q.put_nowait, data_json)

    # Initialize agents
    agent_a = AgentAOpenAI(model=model_a, simulation_mode=simulation_mode)
    agent_b = AgentBClaude(model=model_b, simulation_mode=simulation_mode)
    supervisor = AgentCSupervisor(
        agent_a=agent_a,
        agent_b=agent_b,
        database=db,
        quality_threshold=threshold,
        max_revisions=3
    )

    # Wrap the synchronous supervisor workflow
    await asyncio.sleep(0.4)
    # Patch supervisor to reuse pre-allocated run_id
    supervisor_run_method = supervisor.run_workflow
    
    def run_with_id():
        return supervisor_run_method(task, event_callback=dispatch_event, run_id=run_id)


    try:
        run = await loop.run_in_executor(None, run_with_id)
        # Notify subscribers workflow finished
        dispatch_event("stream_ended", {"run_id": run_id, "final_status": run.status})
    except Exception as exc:
        db.fail_run(run_id, str(exc))
        dispatch_event("error", {"run_id": run_id, "error": str(exc)})
    finally:
        await asyncio.sleep(1.0)
        # Clean up queue after grace period
        if run_id in run_queues:
            del run_queues[run_id]

@app.get("/api/stream/{run_id}")
async def stream_run_events(run_id: str):
    """Server-Sent Events stream for live orchestration telemetry."""
    queue = asyncio.Queue()
    if run_id not in run_queues:
        run_queues[run_id] = []
    run_queues[run_id].append(queue)

    async def event_generator():
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
                parsed = json.loads(data)
                if parsed.get("event") in ["stream_ended", "error"]:
                    break
        except asyncio.CancelledError:
            pass
        finally:
            if run_id in run_queues and queue in run_queues[run_id]:
                run_queues[run_id].remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/.well-known/agent-card.json")
async def root_agent_card(request: Request):
    """A2A agent card for Agent C, the client-facing supervisor."""
    return a2a_proto.router.public_card("c", str(request.base_url))


@app.get("/a2a")
async def a2a_catalog(request: Request):
    base = str(request.base_url)
    return {"agents": [a2a_proto.router.public_card(key, base) for key in ("a", "b", "c")]}


@app.get("/a2a/{agent_id}/.well-known/agent-card.json")
async def a2a_agent_card(agent_id: str, request: Request):
    try:
        return a2a_proto.router.public_card(agent_id, str(request.base_url))
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_id}'")


@app.post("/a2a/{agent_id}")
async def a2a_rpc(agent_id: str, request: Request):
    """JSON-RPC 2.0: message/send, tasks/get, tasks/list, tasks/cancel."""
    try:
        body = json.loads(await request.body() or b"null")
    except json.JSONDecodeError:
        return JSONResponse(a2a_proto.rpc_error(None, -32700, "Parse error"))
    return JSONResponse(a2a_proto.router.rpc(agent_id, body))


# Static files mounting
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
