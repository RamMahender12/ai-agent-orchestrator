"""MongoDB store with the same methods and return shapes as the SQLite Database, so the API and UI don't care which one runs."""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo import ASCENDING, DESCENDING, MongoClient

from core.database import Database, _chat_row
from core.models import AgentProfile, EvaluationResult, OrchestrationRun, StepLog

REVIEW_ACTIONS = ["CAPTAIN_RECOMMENDATIONS", "SUPERVISOR_RECOMMENDATIONS", "AUDIT_VERDICT"]
PERIOD_FORMATS = {"day": "%Y-%m-%d", "week": "%G-W%V", "month": "%Y-%m"}


def _ts(value: Optional[datetime]) -> Optional[str]:
    # same "YYYY-MM-DD HH:MM:SS" UTC text SQLite returns; the UI appends the Z
    return value.strftime("%Y-%m-%d %H:%M:%S") if value else None


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    doc.pop("_id", None)
    if isinstance(doc.get("timestamp"), datetime):
        doc["timestamp"] = _ts(doc["timestamp"])
    return doc


class MongoDatabase(Database):
    def __init__(self, uri: str, db_name: str = "agent_orchestrator"):
        self.db = MongoClient(uri, serverSelectionTimeoutMS=10000, tz_aware=False)[db_name]
        self.init_db()

    def init_db(self):
        self.db.steps.create_index([("run_id", ASCENDING), ("step_index", ASCENDING)])
        self.db.steps.create_index("timestamp")
        self.db.steps.create_index("sender")
        self.db.steps.create_index("receiver")
        self.db.evaluations.create_index("run_id")
        self.db.runs.create_index([("created_at", DESCENDING)])
        self.db.chats.create_index([("session_id", ASCENDING), ("timestamp", ASCENDING)])
        self.db.chats.create_index("sender")
        self.db.a2a_log.create_index("ts")

    def register_agent(self, profile: AgentProfile):
        letter = profile.name.split(" (")[0]
        self.db.agents.delete_many({"name": {"$regex": f"^{letter} \\(", "$ne": profile.name}})
        self.db.agents.update_one({"_id": profile.name}, {"$set": {
            **profile.model_dump(), "updated_at": datetime.utcnow(),
        }}, upsert=True)

    def create_run(self, run: OrchestrationRun):
        self.db.runs.insert_one({
            "_id": run.run_id, "run_id": run.run_id, "task": run.task, "status": run.status,
            "revisions_count": run.revisions_count, "total_tokens": run.total_tokens,
            "total_cost_usd": run.total_cost_usd, "final_output": None,
            "created_at": run.created_at.isoformat(), "completed_at": None,
        })

    def update_run(self, run: OrchestrationRun):
        self.db.runs.update_one({"_id": run.run_id}, {"$set": {
            "status": run.status, "revisions_count": run.revisions_count, "total_tokens": run.total_tokens,
            "total_cost_usd": run.total_cost_usd, "final_output": run.final_output,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        }})

    def log_step(self, run_id: str, step: StepLog):
        u = step.token_usage
        self.db.steps.insert_one({
            "run_id": run_id, "step_index": step.step_index, "sender": step.sender, "receiver": step.receiver,
            "action": step.action, "content": step.content,
            "tokens_prompt": u.prompt_tokens if u else 0, "tokens_completion": u.completion_tokens if u else 0,
            "tokens_total": u.total_tokens if u else 0, "cost_usd": u.cost_usd if u else 0.0,
            # stored as a real object so it can be queried in Atlas; returned as JSON text like SQLite
            "metadata": json.loads(json.dumps(step.metadata, default=str)),
            "timestamp": datetime.utcnow(),
        })

    def log_evaluation(self, run_id: str, eval_res: EvaluationResult):
        self.db.evaluations.insert_one({
            "run_id": run_id, "revision": eval_res.revision, "reviewer": eval_res.reviewer,
            "score": eval_res.score, "passed": eval_res.passed, "strengths": eval_res.strengths,
            "flaws": eval_res.flaws, "actionable_feedback": eval_res.actionable_feedback,
            "cost_usd": eval_res.token_usage.cost_usd if eval_res.token_usage else 0.0,
            "timestamp": datetime.utcnow(),
        })

    def log_chat(self, session_id: str, target: str, message: str, responses: List[Dict[str, Any]]):
        keys = ("session_id", "target", "sender", "prompt", "reply", "tokens_total", "cost_usd")
        now = datetime.utcnow()
        docs = [{**dict(zip(keys, _chat_row(session_id, target, message, r))), "timestamp": now} for r in responses]
        if docs:
            self.db.chats.insert_many(docs)

    def log_a2a(self, record: Dict[str, Any]):
        self.db.a2a_log.insert_one(json.loads(json.dumps(record, default=str)))

    def get_registered_agents(self) -> List[Dict[str, Any]]:
        return [{**_clean(a), "updated_at": _ts(a["updated_at"])}
                for a in self.db.agents.find().sort("updated_at", DESCENDING)]

    def delete_runs(self, run_id: Optional[str] = None):
        where = {"run_id": run_id} if run_id else {}
        for name in ("steps", "evaluations", "runs"):
            self.db[name].delete_many(where)

    def get_run_history(self, limit: int = 15) -> List[Dict[str, Any]]:
        return [_clean(r) for r in self.db.runs.find().sort("created_at", DESCENDING).limit(limit)]

    def _step(self, s: Dict[str, Any]) -> Dict[str, Any]:
        s = _clean(s)
        s["metadata"] = json.dumps(s.get("metadata") or {})
        return s

    def get_run_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        run = self.db.runs.find_one({"_id": run_id})
        if not run:
            return None
        usage = self.db.steps.aggregate([
            {"$match": {"run_id": run_id}},
            {"$group": {"_id": "$sender", "steps": {"$sum": 1}, "prompt_tokens": {"$sum": "$tokens_prompt"},
                        "completion_tokens": {"$sum": "$tokens_completion"}, "total_tokens": {"$sum": "$tokens_total"},
                        "cost_usd": {"$sum": "$cost_usd"}}},
        ])
        evaluations = []
        for e in self.db.evaluations.find({"run_id": run_id}).sort("revision", ASCENDING):
            e = _clean(e)
            e["strengths"], e["flaws"] = json.dumps(e["strengths"]), json.dumps(e["flaws"])
            evaluations.append(e)
        return {
            "run": _clean(run),
            "steps": [self._step(s) for s in self.db.steps.find({"run_id": run_id}).sort("step_index", ASCENDING)],
            "evaluations": evaluations,
            "usage": [{"agent": u.pop("_id"), **u, "cost_usd": round(u["cost_usd"], 6)} for u in usage],
        }

    def get_chat_history(self, session_id: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
        rows = self.db.chats.find({"session_id": session_id} if session_id else {}).sort("timestamp", DESCENDING).limit(limit)
        return [_clean(r) for r in rows][::-1]

    def get_agent_history(self, letter: str, limit: int = 200) -> Dict[str, Any]:
        rx = {"$regex": f"^Agent {letter.upper()}"}
        steps = [self._step(s) for s in self.db.steps.find({"$or": [{"sender": rx}, {"receiver": rx}]})
                 .sort("timestamp", DESCENDING).limit(limit)]
        tasks = {r["run_id"]: r["task"] for r in self.db.runs.find(
            {"run_id": {"$in": list({s["run_id"] for s in steps})}}, {"run_id": 1, "task": 1})}
        for s in steps:
            s["task"] = tasks.get(s["run_id"])
        reviews = self.db.steps.find({"action": {"$in": REVIEW_ACTIONS}, "metadata.author": rx},
                                     {"run_id": 1, "timestamp": 1, "metadata.evaluation": 1}).sort("timestamp", DESCENDING).limit(limit)
        return {
            "agent": letter.upper(),
            "steps": steps,
            "chats": [_clean(c) for c in self.db.chats.find({"sender": rx}).sort("timestamp", DESCENDING).limit(limit)],
            "reviews": [{"run_id": r["run_id"], "timestamp": _ts(r["timestamp"]),
                         "evaluation": (r.get("metadata") or {}).get("evaluation")} for r in reviews],
        }

    def get_agent_metrics(self, period: str = "day", limit: int = 12) -> List[Dict[str, Any]]:
        """Per-agent score, pass rate, wins, tokens and cost, grouped by day, ISO week or month (UTC)."""
        p = {"$dateToString": {"format": PERIOD_FORMATS[period], "date": "$timestamp"}}
        # ponytail: scans every step to list periods; add a stored period field + index if steps reach millions
        periods = [d["_id"] for d in self.db.steps.aggregate([
            {"$group": {"_id": p}}, {"$sort": {"_id": -1}}, {"$limit": limit}])]
        if not periods:
            return []
        rows: Dict[tuple, Dict[str, Any]] = {}

        def row(per, agent):
            return rows.setdefault((per, agent), {
                "period": per, "agent": agent, "answers_reviewed": 0, "avg_score": None, "best_score": None,
                "pass_rate": None, "first_try_pass_rate": None, "wins": 0, "tokens": 0, "cost_usd": 0.0,
            })

        def grouped(match, agent_field, **acc):
            return self.db.steps.aggregate([
                {"$match": match}, {"$addFields": {"p": p}}, {"$match": {"p": {"$in": periods}}},
                {"$group": {"_id": {"p": "$p", "agent": agent_field}, **acc}},
                {"$match": {"_id.agent": {"$ne": None}}},
            ])

        passed = {"$cond": ["$metadata.evaluation.passed", 1, 0]}
        pct = lambda v: None if v is None else round(100 * v, 1)
        for r in grouped({"action": {"$in": REVIEW_ACTIONS}}, "$metadata.author",
                         n={"$sum": 1}, avg={"$avg": "$metadata.evaluation.score"}, best={"$max": "$metadata.evaluation.score"},
                         pass_rate={"$avg": passed},
                         first={"$avg": {"$cond": [{"$eq": ["$metadata.evaluation.revision", 1]}, passed, None]}}):
            row(r["_id"]["p"], r["_id"]["agent"]).update(
                answers_reviewed=r["n"], avg_score=None if r["avg"] is None else round(r["avg"], 1), best_score=r["best"],
                pass_rate=pct(r["pass_rate"]), first_try_pass_rate=pct(r["first"]))
        for r in grouped({"action": "WINNER_SELECTED"}, "$metadata.winner", n={"$sum": 1}):
            row(r["_id"]["p"], r["_id"]["agent"])["wins"] = r["n"]
        for r in grouped({"sender": {"$regex": "^Agent ", "$not": {"$regex": "^Agent C"}}}, "$sender",
                         tokens={"$sum": "$tokens_total"}, cost={"$sum": "$cost_usd"}):
            row(r["_id"]["p"], r["_id"]["agent"]).update(tokens=r["tokens"], cost_usd=round(r["cost"], 6))
        return sorted(rows.values(), key=lambda r: (r["period"], r["agent"]), reverse=True)

    def fail_run(self, run_id: str, error: str):
        self.db.runs.update_one({"_id": run_id}, {"$set": {
            "status": "FAILED", "final_output": f"Error: {error}", "completed_at": _ts(datetime.utcnow()),
        }})
