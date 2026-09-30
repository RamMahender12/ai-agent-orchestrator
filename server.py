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

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from core.database import Database
from core.models import OrchestrationRun
from agents.agent_a_openai import AgentAOpenAI
from agents.agent_b_claude import AgentBClaude
from agents.agent_c_supervisor import AgentCSupervisor

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

# Active SSE subscriber queues keyed by run_id
run_queues: Dict[str, List[asyncio.Queue]] = {}

class OrchestrationRequest(BaseModel):
    task: str
    simulation_mode: bool = True
    model_a: Optional[str] = "gpt-4o"
    model_b: Optional[str] = "claude-3-5-sonnet-20241022"
    quality_threshold: Optional[int] = 80

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "has_openai_key": bool(os.getenv("OPENAI_API_KEY")),
        "has_anthropic_key": bool(os.getenv("ANTHROPIC_API_KEY")),
        "default_mode": "simulation" if os.getenv("SIMULATION_MODE", "true").lower() == "true" else "live"
    }

class ChatRequest(BaseModel):
    agent_target: str = "supervisor"  # "supervisor", "agent_a", "agent_b", "triad"
    message: str
    simulation_mode: Optional[bool] = True
    history: Optional[List[Dict[str, str]]] = None

@app.post("/api/chat")
async def chat_with_agents(req: ChatRequest):
    """Direct interactive chat with individual agents or collaborative triad."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    sim_mode = req.simulation_mode
    if not sim_mode:
        if not os.getenv("OPENAI_API_KEY") or not os.getenv("ANTHROPIC_API_KEY"):
            sim_mode = True

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

    sim_mode = req.simulation_mode
    # Auto-fallback if live selected but keys missing
    if not sim_mode:
        if not os.getenv("OPENAI_API_KEY") or not os.getenv("ANTHROPIC_API_KEY"):
            sim_mode = True

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


# Static files mounting
static_dir = Path(__file__).resolve().parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
