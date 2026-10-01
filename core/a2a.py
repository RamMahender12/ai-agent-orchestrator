"""Minimal Agent2Agent (A2A) JSON-RPC surface.

Clients discover an agent card, then call message/send and tasks/get.
Same router serves HTTP and in-process calls from Agent C.
"""
import json
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "a2a.jsonl"

ALIASES = {
    "a": "a", "openai": "a", "agent_a": "a",
    "b": "b", "claude": "b", "agent_b": "b",
    "c": "c", "supervisor": "c", "agent_c": "c",
}


def message_text(message: Dict[str, Any]) -> str:
    parts = message.get("parts") or []
    chunks = []
    for part in parts:
        kind = part.get("kind") or part.get("type")
        if kind in (None, "text") and part.get("text"):
            chunks.append(part["text"])
    return "\n".join(chunks)


def message_data(message: Dict[str, Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for part in message.get("parts") or []:
        kind = part.get("kind") or part.get("type")
        if kind == "data" and isinstance(part.get("data"), dict):
            data.update(part["data"])
    return data


def _text_message(role: str, text: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    msg = {
        "kind": "message",
        "role": role,
        "messageId": uuid.uuid4().hex,
        "parts": [{"kind": "text", "text": text}],
    }
    if metadata:
        msg["metadata"] = metadata
    return msg


def rpc_error(rpc_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}


class A2ARouter:
    def __init__(self):
        self._agents: Dict[str, Dict[str, Any]] = {}
        self.tasks: Dict[str, Dict[str, Any]] = {}

    def bind(self, key: str, card: Dict[str, Any], handler: Callable[[Dict[str, Any]], Dict[str, Any]]):
        self._agents[key] = {"card": card, "handler": handler}

    def resolve(self, key: str) -> str:
        canon = ALIASES.get(key, key)
        if canon not in self._agents:
            raise KeyError(key)
        return canon

    def card(self, key: str) -> Dict[str, Any]:
        return deepcopy(self._agents[self.resolve(key)]["card"])

    def public_card(self, key: str, base_url: str) -> Dict[str, Any]:
        card = self.card(key)
        path = card.get("url") or ""
        if path.startswith("/"):
            card["url"] = base_url.rstrip("/") + path
        return card

    def send(
        self,
        key: str,
        text: str,
        skill: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        context_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        metadata = {"skill": skill} if skill else None
        parts = [{"kind": "text", "text": text}]
        if data:
            parts.append({"kind": "data", "data": data})
        message = _text_message("user", text, metadata)
        message["parts"] = parts
        body = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": "message/send",
            "params": {"message": message},
        }
        if context_id:
            body["params"]["message"]["contextId"] = context_id
        result = self.rpc(key, body)
        if "error" in result:
            raise RuntimeError(result["error"]["message"])
        if result["result"]["status"]["state"] == "failed":
            raise RuntimeError(f"Agent {key.upper()} failed: {task_text(result['result'])}")
        return result["result"]

    def rpc(self, key: str, body: Dict[str, Any]) -> Dict[str, Any]:
        rpc_id = body.get("id") if isinstance(body, dict) else None
        if not isinstance(body, dict) or body.get("jsonrpc") != "2.0" or "method" not in body:
            return rpc_error(rpc_id, -32600, "Invalid Request")
        try:
            canon = self.resolve(key)
        except KeyError:
            return rpc_error(rpc_id, -32602, f"Unknown agent '{key}'")
        method = body["method"]
        params = body.get("params") or {}
        if method == "message/send":
            try:
                task = self._message_send(canon, params)
            except ValueError as exc:
                return rpc_error(rpc_id, -32602, str(exc))
            self._audit({"method": method, "agent": canon, "task": task})
            return {"jsonrpc": "2.0", "id": rpc_id, "result": task}
        if method == "tasks/get":
            task_id = params.get("id") or params.get("taskId")
            task = self.tasks.get(task_id)
            if not task or task.get("metadata", {}).get("agent") != canon:
                return rpc_error(rpc_id, -32001, "Task not found")
            return {"jsonrpc": "2.0", "id": rpc_id, "result": task}
        if method == "tasks/list":
            # ponytail: in-memory list, swap for a task store if history must survive restart
            mine = [t for t in self.tasks.values() if t.get("metadata", {}).get("agent") == canon]
            return {"jsonrpc": "2.0", "id": rpc_id, "result": {"tasks": mine}}
        if method == "tasks/cancel":
            task_id = params.get("id") or params.get("taskId")
            task = self.tasks.get(task_id)
            if not task or task.get("metadata", {}).get("agent") != canon:
                return rpc_error(rpc_id, -32001, "Task not found")
            if task["status"]["state"] not in ("completed", "canceled", "failed"):
                task["status"] = {"state": "canceled", "timestamp": _now()}
            return {"jsonrpc": "2.0", "id": rpc_id, "result": task}
        return rpc_error(rpc_id, -32601, f"Method not found: {method}")

    def _message_send(self, canon: str, params: Dict[str, Any]) -> Dict[str, Any]:
        message = params.get("message") or {}
        if not message_text(message) and not message_data(message):
            raise ValueError("Message is empty")
        task_id = uuid.uuid4().hex
        context_id = message.get("contextId") or uuid.uuid4().hex
        try:
            out = self._agents[canon]["handler"](message)
            text = out.get("text") or ""
            usage = out.get("usage") or {
                "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0
            }
            state = "completed"
            reply = _text_message("agent", text)
            artifact_parts = [{"kind": "text", "text": text}]
            if out.get("data") is not None:
                artifact_parts.append({"kind": "data", "data": out["data"]})
            artifacts = [{
                "artifactId": uuid.uuid4().hex,
                "name": "result",
                "parts": artifact_parts,
            }]
        except Exception as exc:
            text = str(exc)
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "cost_usd": 0.0}
            state = "failed"
            reply = _text_message("agent", text)
            artifacts = []
        task = {
            "kind": "task",
            "id": task_id,
            "contextId": context_id,
            "status": {"state": state, "timestamp": _now(), "message": reply},
            "artifacts": artifacts,
            "history": [message, reply],
            "metadata": {
                "agent": canon,
                "skill": (message.get("metadata") or {}).get("skill"),
                "usage": usage,
                "model": (out.get("model") if state == "completed" else None),
                "result": out.get("data") if state == "completed" else None,
            },
        }
        self.tasks[task_id] = task
        return task

    def _audit(self, record: Dict[str, Any]):
        LOG_PATH.parent.mkdir(exist_ok=True)
        record = {"ts": _now(), **record}
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=str) + "\n")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def card_for(agent, skills) -> Dict[str, Any]:
    profile = agent.get_profile()
    key = {"OpenAI": "a", "Anthropic": "b"}.get(profile.provider, "c")
    return {
        "name": profile.name,
        "description": profile.description,
        "url": f"/a2a/{key}",
        "version": "1.0.0",
        "protocolVersion": "0.3.0",
        "provider": {"organization": profile.provider, "url": f"/a2a/{key}"},
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
            "stateTransitionHistory": True,
        },
        "defaultInputModes": ["text/plain", "application/json"],
        "defaultOutputModes": ["text/plain", "application/json"],
        "skills": skills,
        "metadata": {
            "model": profile.model,
            "role": profile.role,
            "capabilities": profile.capabilities,
        },
    }


router = A2ARouter()


def task_text(task: Dict[str, Any]) -> str:
    msg = (task.get("status") or {}).get("message") or {}
    return message_text(msg)


def demo():
    probe = A2ARouter()

    def handler(message):
        return {
            "text": "ok " + message_text(message),
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2, "cost_usd": 0.01},
            "model": "probe",
        }

    probe.bind("a", {"name": "A", "description": "probe", "url": "/a2a/a", "skills": []}, handler)
    sent = probe.rpc("a", {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "message/send",
        "params": {"message": {"role": "user", "messageId": "m", "parts": [{"kind": "text", "text": "hi"}]}},
    })
    assert sent["result"]["status"]["state"] == "completed", sent
    assert task_text(sent["result"]) == "ok hi"
    fetched = probe.rpc("a", {"jsonrpc": "2.0", "id": 2, "method": "tasks/get", "params": {"id": sent["result"]["id"]}})
    assert fetched["result"]["id"] == sent["result"]["id"]
    missing = probe.rpc("a", {"jsonrpc": "2.0", "id": 3, "method": "nope", "params": {}})
    assert missing["error"]["code"] == -32601

    import tempfile
    from core.database import Database
    from agents.agent_c_supervisor import AgentCSupervisor

    db = Database(Path(tempfile.mkdtemp()) / "t.db")
    supervisor = AgentCSupervisor(database=db, max_revisions=2)
    run = supervisor.run_workflow("Build a rate limiter")
    assert run.status == "COMPLETED", run.status
    assert run.revisions_count == 2
    # B scores A's answer, A scores B's answer, B wins, A re-scores B's revision
    assert [e.score for e in run.evaluations] == [68, 74, 94], run.evaluations
    assert "Agent B" in run.final_output and "Revision 2" in run.final_output
    assert run.total_cost_usd > 0
    assert any(step.metadata.get("a2a") for step in run.steps)
    print("a2a demo ok", run.total_tokens, run.total_cost_usd)


if __name__ == "__main__":
    demo()
