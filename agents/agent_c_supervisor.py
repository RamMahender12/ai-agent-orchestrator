import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from core.models import (
    OrchestrationRun,
    StepLog,
    TokenUsage,
    EvaluationResult
)
from core.database import Database
from core.cost_tracker import CostTracker
from agents.agent_a_openai import AgentAOpenAI
from agents.agent_b_claude import AgentBClaude
from agents.agent_free import free_agents
from agents.base_agent import BaseAgent
from core.a2a import card_for, router as a2a_router, task_text

class AgentCSupervisor:
    """
    Agent C: Meta-Orchestrator & Supervisor Agent.
    - Interrogates every worker (A, B, and the free-model agents D, E, F) and logs their capabilities to Database.
    - Has all workers answer the task at once, then reviews each answer itself and sends that agent recommendations.
    - Calculates real-time tokens and USD costs for every agent.
    - Each agent below the pass score revises from C's recommendations; the higher-scored answer wins.
    - Commits full audit logs and metrics to SQLite and disk.
    """
    def __init__(
        self,
        agent_a: Optional[AgentAOpenAI] = None,
        agent_b: Optional[AgentBClaude] = None,
        database: Optional[Database] = None,
        quality_threshold: int = 80,
        max_revisions: int = 3,
        extra_agents: Optional[List[BaseAgent]] = None,
    ):
        self.name = "Agent C (Supervisor)"
        self.provider = "Orchestration-Core"
        self.model = "supervisor-engine"
        self.agent_a = agent_a or AgentAOpenAI()
        self.agent_b = agent_b or AgentBClaude()
        # free-model workers; default to the FREE_MODELS list, in the same simulation mode as A
        self.extra_agents = free_agents(self.agent_a.simulation_mode) if extra_agents is None else extra_agents
        self.db = database or Database()
        self.quality_threshold = quality_threshold
        self.max_revisions = max_revisions
        self.a2a = a2a_router

    @property
    def workers(self) -> Dict[str, BaseAgent]:
        """Every agent that answers the task, keyed by its letter."""
        return {"a": self.agent_a, "b": self.agent_b, **{agent.key: agent for agent in self.extra_agents}}

    def get_profile(self):
        from core.models import AgentProfile
        return AgentProfile(
            name=self.name,
            provider=self.provider,
            model=self.model,
            role="Supervisor",
            capabilities=[
                "A2A discovery of every worker agent",
                "Task dispatch via message/send",
                "Token and USD cost tracking",
                "Reviews both answers and recommends concrete improvements to each agent",
                "Revision orders when quality is too low",
            ],
            description="I am Agent C. I ask every worker agent what it does, have them all answer the task over A2A at once, score each answer myself and give each agent recommendations to improve it, log the work, track tokens and cost, and have every agent below the pass score revise.",
        )

    def bind_a2a(self):
        """Publish every worker and C on the shared A2A router."""
        worker_skills = [
            {"id": "describe", "name": "What I do", "description": "Return capabilities.", "tags": ["discovery"]},
            {"id": "draft", "name": "Draft", "description": "Answer the task.", "tags": ["create"]},
            {"id": "audit", "name": "Audit", "description": "Score the other agent's answer from 0 to 100.", "tags": ["review"]},
            {"id": "revise", "name": "Revise", "description": "Redo the work from supervisor critique.", "tags": ["revise"]},
        ]
        for key, agent in self.workers.items():
            self.a2a.bind(key, card_for(agent, worker_skills), lambda m, agent=agent: self._on_worker(agent, m))
        self.a2a.bind("c", card_for(self, [
            {"id": "describe", "name": "What I do", "description": "Discover A and B and report cost.", "tags": ["discovery"]},
            {"id": "orchestrate", "name": "Orchestrate", "description": "Have every worker answer, recommend improvements to each, and have them revise until they pass.", "tags": ["orchestrate"]},
            {"id": "monitor", "name": "Monitor", "description": "List A2A tasks and token cost for every agent.", "tags": ["monitor"]},
        ]), self._on_c)

    def _usage(self, model: str, prompt: str, completion: str):
        return CostTracker.create_token_usage(
            model,
            CostTracker.estimate_tokens_from_text(prompt),
            CostTracker.estimate_tokens_from_text(completion),
        ).model_dump()

    def _on_worker(self, agent, message: Dict[str, Any]) -> Dict[str, Any]:
        """A2A handler shared by A and B: both can describe, draft, revise, and audit."""
        from core.a2a import message_data, message_text
        text = message_text(message)
        data = message_data(message)
        default = "audit" if data.get("draft") else ("draft" if agent is self.agent_a else "chat")
        skill = (message.get("metadata") or {}).get("skill") or default
        if skill == "describe" or text.lower().strip(" ?.!") in ("what do you do", "who are you"):
            profile = agent.get_profile()
            body = f"{profile.description} Capabilities: {', '.join(profile.capabilities)}"
            return {"text": body, "usage": self._usage(agent.model, text, body), "model": agent.model}
        if skill == "instruct":
            body = "Acknowledged. I will revise the draft against that critique."
            return {"text": body, "usage": self._usage(agent.model, text, body), "model": agent.model}
        if skill == "audit":
            evaluation = agent.evaluate_draft(data.get("task") or text, {
                "draft": data.get("draft", ""),
                "revision": data.get("revision", 1),
                "threshold": data.get("threshold", self.quality_threshold),
            })
            summary = (
                f"Quality Score: {evaluation.score}/100. Passed: {evaluation.passed}. "
                f"Feedback: {evaluation.actionable_feedback}"
            )
            return {
                "text": summary,
                "data": evaluation.model_dump(),
                "usage": evaluation.token_usage.model_dump() if evaluation.token_usage else self._usage(agent.model, text, summary),
                "model": agent.model,
            }
        if skill == "chat":
            reply, usage = agent.chat(text)
            return {"text": reply, "usage": usage.model_dump(), "model": agent.model}
        out, usage = agent.draft(data.get("task") or text, {
            "revision": data.get("revision", 2 if skill == "revise" else 1),
            "feedback": data.get("feedback"),
            "previous": data.get("previous"),
        })
        return {"text": out, "usage": usage.model_dump(), "model": agent.model}

    def _on_c(self, message: Dict[str, Any]) -> Dict[str, Any]:
        from core.a2a import message_text
        text = message_text(message)
        skill = (message.get("metadata") or {}).get("skill") or "orchestrate"
        if skill == "monitor":
            tasks = [t for t in self.a2a.tasks.values()]
            cost = round(sum((t.get("metadata") or {}).get("usage", {}).get("cost_usd", 0) or 0 for t in tasks), 6)
            tokens = sum((t.get("metadata") or {}).get("usage", {}).get("total_tokens", 0) or 0 for t in tasks)
            body = f"Tracking {len(tasks)} A2A tasks. Tokens {tokens}. Cost ${cost}."
            return {"text": body, "data": {"tasks": len(tasks), "total_tokens": tokens, "total_cost_usd": cost}, "usage": self._usage(self.model, text, body), "model": self.model}
        if skill == "describe" or text.lower().strip(" ?.!") in ("what do you do", "who are you"):
            self.bind_a2a()
            cards = {key: self.a2a.card(key) for key in self.workers}
            for key, card in cards.items():
                self.db.register_agent(self._profile_from_card(card, task_text(self.a2a.send(key, "What do you do?", skill="describe"))))
            body = (
                "I am Agent C. I discover every worker from its A2A agent card, "
                "task them with message/send, log every task, and sum token cost. "
                + " ".join(f"{key.upper()}: {card['description']}" for key, card in cards.items())
            )
            return {"text": body, "data": {"cards": cards}, "usage": self._usage(self.model, text, body), "model": self.model}
        run = self.run_workflow(text)
        by_agent: Dict[str, float] = {}
        for step in run.steps:
            if step.token_usage:
                by_agent[step.sender] = round(by_agent.get(step.sender, 0) + step.token_usage.cost_usd, 6)
        summary = (
            f"Run {run.run_id} {run.status}. Revisions {run.revisions_count}. "
            f"Tokens {run.total_tokens}. Cost ${run.total_cost_usd}."
        )
        return {
            "text": run.final_output or summary,
            "data": {
                "run_id": run.run_id,
                "status": run.status,
                "revisions": run.revisions_count,
                "total_tokens": run.total_tokens,
                "total_cost_usd": run.total_cost_usd,
                "cost_by_sender": by_agent,
                "summary": summary,
            },
            "usage": self._usage(self.model, text, summary),
            "model": self.model,
        }

    def _profile_from_card(self, card: Dict[str, Any], description: str):
        from core.models import AgentProfile
        meta = card.get("metadata") or {}
        return AgentProfile(
            name=card["name"],
            provider=card["provider"]["organization"],
            model=meta.get("model", ""),
            role=meta.get("role", ""),
            capabilities=meta.get("capabilities") or [s["name"] for s in card.get("skills", [])],
            description=description or card.get("description", ""),
        )

    def _a2a_meta(self, task: Dict[str, Any]) -> Dict[str, Any]:
        usage = (task.get("metadata") or {}).get("usage") or {}
        return {"a2a": {"method": "message/send", "taskId": task["id"], "state": task["status"]["state"], "usage": usage}}

    def run_workflow(
        self,
        task: str,
        event_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
        run_id: Optional[str] = None
    ) -> OrchestrationRun:
        """
        Executes the full multi-agent orchestration lifecycle:
        1. Discovery & Capability Registration (stores in DB)
        2. Every worker answers the task, all at the same time
        3. C scores each answer and sends its author recommendations to improve it
        4. Every agent below threshold revises from C's recommendations, up to max_revisions
        5. Final output is the best-scoring draft; persistence and telemetry consolidation
        """
        self.bind_a2a()
        run_id = run_id or f"run_{uuid.uuid4().hex[:8]}"
        run = OrchestrationRun(
            run_id=run_id,
            task=task,
            status="INITIALIZING",
            current_step="System Boot & Agent Discovery"
        )

        self.db.create_run(run)

        def emit(event_type: str, data: Dict[str, Any]):
            if event_callback:
                event_callback(event_type, {
                    "run_id": run_id,
                    "event": event_type,
                    "timestamp": datetime.utcnow().isoformat(),
                    "total_tokens": run.total_tokens,
                    "total_cost_usd": run.total_cost_usd,
                    **data
                })

        def log(sender: str, receiver: str, action: str, content: str,
                usage: Optional[TokenUsage] = None, **metadata) -> StepLog:
            step = StepLog(
                step_index=len(run.steps) + 1,
                sender=sender,
                receiver=receiver,
                action=action,
                content=content,
                token_usage=usage,
                metadata=metadata,
            )
            self._record_step(run, step)
            return step

        workers = self.workers

        def fan_out(fn: Callable[[str], Any], keys: List[str]) -> Dict[str, Any]:
            """Call fn for every agent at once, so one slow free model doesn't hold up the rest. Errors come back as values."""
            if not keys:
                return {}
            with ThreadPoolExecutor(max_workers=len(keys)) as pool:
                futures = {key: pool.submit(fn, key) for key in keys}
            results = {}
            for key, future in futures.items():
                try:
                    results[key] = future.result()
                except Exception as exc:
                    results[key] = exc
            return results

        def set_status(status: str, message: str):
            run.status = status
            self.db.update_run(run)
            emit("status_change", {"status": status, "message": message})

        def failed(key: str, revision: int, what: str, exc: Exception):
            agent = workers[key]
            step = log(
                agent.name, self.name, "AGENT_FAILED", f"{agent.name} ({agent.model}) {what}: {exc}",
                revision=revision, model=agent.model, error=str(exc),
            )
            emit("agent_failed", {"revision": revision, "agent": agent.name, "error": str(exc), "step": step.model_dump()})

        # ==========================================
        # STEP 1: Supervisor queries every worker's capabilities
        # ==========================================
        emit("status_change", {"status": "DISCOVERY", "message": f"Supervisor interrogating {len(workers)} agents..."})

        for key in workers:
            # Query the agent over A2A (agent card + message/send)
            desc = self.a2a.send(key, "What do you do?", skill="describe", context_id=run_id)
            profile = self._profile_from_card(self.a2a.card(key), task_text(desc))
            self.db.register_agent(profile)
            run.agent_profiles[profile.name] = profile
            step = log(
                self.name, profile.name, "CAPABILITY_DISCOVERY",
                f'C asked: "What do you do?"\n{profile.name} answered: {task_text(desc)}\nModel: {profile.model}',
                TokenUsage(**(desc["metadata"]["usage"])),
                profile=profile.model_dump(), **self._a2a_meta(desc),
            )
            emit("agent_registered", {"agent": profile.model_dump(), "step": step.model_dump()})

        def write_all(keys: List[str], revision: int, feedback: Optional[Dict[str, str]] = None,
                      previous: Optional[Dict[str, str]] = None) -> Dict[str, str]:
            """Have these agents answer the task (or revise) over A2A at the same time. Agents that fail are left out."""
            feedback, previous = feedback or {}, previous or {}
            set_status(f"REVISION_{revision}_GENERATION_ALL", f"Supervisor dispatching task to {len(keys)} agents (Revision {revision})...")
            for key in keys:
                if key not in feedback:  # on later rounds the REVISE_DIRECTIVE step is C's message
                    log(self.name, workers[key].name, "TASK_DISPATCH", f"Do this task and send me your draft:\n{task}", revision=revision)
            sent = fan_out(lambda key: self.a2a.send(key, task, skill="revise" if key in feedback else "draft", data={
                "task": task,
                "revision": revision,
                "feedback": feedback.get(key),
                "previous": previous.get(key),
            }, context_id=run_id), keys)
            drafts = {}
            for key, result in sent.items():
                if isinstance(result, Exception):
                    failed(key, revision, "did not answer", result)
                    continue
                agent = workers[key]
                draft = task_text(result)
                usage = TokenUsage(**result["metadata"]["usage"])
                step = log(
                    agent.name, self.name, "REVISED_DRAFT" if key in feedback else "DRAFT_SUBMISSION", draft, usage,
                    revision=revision, model=agent.model, **self._a2a_meta(result),
                )
                emit("draft_produced", {
                    "revision": revision,
                    "agent": agent.name,
                    "draft": draft,
                    "tokens": usage.model_dump(),
                    "step": step.model_dump()
                })
                drafts[key] = draft
            return drafts

        def review_all(drafts: Dict[str, str], revision: int) -> Dict[str, EvaluationResult]:
            """C scores every draft itself and writes each agent tips for a better answer."""
            set_status(f"REVISION_{revision}_REVIEW_ALL", f"Supervisor reviewing {len(drafts)} answers and writing recommendations...")
            results = fan_out(lambda key: self.recommend(task, drafts[key], revision), list(drafts))
            verdicts = {}
            for key, evaluation in results.items():
                if isinstance(evaluation, Exception):
                    failed(key, revision, "could not be reviewed by C", evaluation)
                    continue
                agent = workers[key]
                run.evaluations.append(evaluation)
                self.db.log_evaluation(run.run_id, evaluation)
                step = log(
                    self.name, agent.name, "SUPERVISOR_RECOMMENDATIONS",
                    f"Quality Score: {evaluation.score}/100. Passed: {evaluation.passed}.\nRecommendations:\n"
                    + "\n".join(f"- {tip}" for tip in evaluation.flaws),
                    evaluation.token_usage,
                    evaluation=evaluation.model_dump(), author=agent.name, revision=revision,
                )
                emit("audit_completed", {
                    "revision": revision,
                    "author": agent.name,
                    "evaluation": evaluation.model_dump(),
                    "step": step.model_dump()
                })
                verdicts[key] = evaluation
            return verdicts

        # ==========================================
        # STEP 2: Every agent answers; C reviews each answer and sends that agent its recommendations
        # ==========================================
        revision = 1
        run.revisions_count = revision
        drafts = write_all(list(workers), revision)
        verdicts = review_all(drafts, revision)
        if not verdicts:
            raise RuntimeError("No agent produced an answer C could score. See the AGENT_FAILED steps.")
        best = {key: (drafts[key], verdicts[key]) for key in verdicts}

        # ==========================================
        # STEP 3: Every agent still below the pass score revises from C's recommendations
        # ==========================================
        while revision < self.max_revisions:
            lagging = [key for key in verdicts if verdicts[key].score < self.quality_threshold]
            if not lagging:
                break
            feedback = {}
            for key in lagging:
                evaluation = verdicts[key]
                emit("status_change", {
                    "status": "SUPERVISOR_INTERVENTION",
                    "message": f"{workers[key].name} scored {evaluation.score}/{self.quality_threshold}. Supervisor sending recommendations..."
                })
                feedback[key] = (
                    f"Supervisor Recommendations for Revision {revision + 1} (you scored {evaluation.score}/{self.quality_threshold}):\n"
                    + "\n".join(f"- {tip}" for tip in evaluation.flaws)
                    + f"\nKeep what works: {'; '.join(evaluation.strengths)}\n"
                    f"Summary: {evaluation.actionable_feedback}"
                )
                order = self.a2a.send(key, feedback[key], skill="instruct", data={
                    "task": task, "revision": revision,
                }, context_id=run_id)
                step = log(
                    self.name, workers[key].name, "REVISE_DIRECTIVE", feedback[key], TokenUsage(**order["metadata"]["usage"]),
                    revision=revision, score=evaluation.score, **self._a2a_meta(order),
                )
                emit("supervisor_intervention", {
                    "revision": revision,
                    "agent": workers[key].name,
                    "critique": feedback[key],
                    "score": evaluation.score,
                    "step": step.model_dump()
                })
            revision += 1
            run.revisions_count = revision
            revised = write_all(lagging, revision, feedback, {key: drafts[key] for key in lagging})
            drafts.update(revised)
            new_verdicts = review_all(revised, revision)
            verdicts.update(new_verdicts)  # an agent whose revision failed keeps its last verdict
            for key, evaluation in new_verdicts.items():
                if evaluation.score > best[key][1].score:  # a revision can score lower; keep the best one
                    best[key] = (drafts[key], evaluation)

        # Supervisor picks the strongest final answer (a tie goes to the earlier agent: A, then B, ...)
        scores = {workers[key].name: best[key][1].score for key in best}
        lead = max(best, key=lambda key: best[key][1].score)
        author = workers[lead]
        best_draft, best = best[lead]
        step = log(
            self.name, "ALL", "WINNER_SELECTED",
            ", ".join(f"{name} scored {score}/100" for name, score in scores.items()) + f". Going with {author.name}'s answer.",
            winner=author.name, scores=scores,
        )
        emit("winner_selected", {
            "winner": author.name,
            "scores": step.metadata["scores"],
            "step": step.model_dump()
        })

        run.final_output = best_draft
        run.completed_at = datetime.utcnow()
        if best.score >= self.quality_threshold:
            run.status = "COMPLETED"
            step = log(
                self.name, "ALL", "APPROVAL_FINALIZED",
                (
                    f"{author.name}'s deliverable successfully approved at Revision {best.revision} with Score {best.score}/100. "
                    f"All quality benchmarks met."
                ),
                CostTracker.create_token_usage(self.model, 60, 40),
                final_revision=best.revision, final_score=best.score, author=author.name,
            )
            emit("workflow_completed", {
                "final_score": best.score,
                "revisions": revision,
                "author": author.name,
                "final_output": best_draft,
                "step": step.model_dump()
            })
        else:
            run.status = "MAX_REVISIONS_REACHED"

        self.db.update_run(run)
        return run

    def recommend(self, task: str, draft: str, revision: int) -> EvaluationResult:
        """Score a draft and list concrete improvements, e.g. "wear a helmet and you won't get hurt when you fall"."""
        if self.agent_a.simulation_mode:
            done = revision > 1
            usage = CostTracker.create_token_usage(self.model, 450 + CostTracker.estimate_tokens_from_text(draft), 180)
            parsed = {
                "score": 93 if done else 70,
                "strengths": ["Clear structure", "Covers the core of the task"],
                "recommendations": [] if done else [
                    "Add retries with exponential backoff and jitter so a flaky dependency doesn't fail the whole request.",
                    "Put numbers on it (P95/P99 latency, uptime target) so the design can be checked against goals.",
                    "Show a short code or pseudocode snippet so the reader can see how the core path works.",
                    "Say what gets logged and traced so failures can be found quickly in production.",
                ],
                "summary": "Ready to ship." if done else "Solid outline; the tips above turn it into something production-ready.",
            }
        else:
            from core.llm import complete
            text, usage = complete(
                "You are Agent C, a supervisor coaching another agent. Do not just list flaws: give concrete, "
                "practical recommendations that would make the answer better, each phrased as an action plus its payoff "
                "(e.g. 'Wear a helmet so a fall doesn't hurt you', 'Keep a firm grip so you can ride faster'). "
                "Respond ONLY with valid JSON:\n"
                '{"score": int (0-100), "strengths": [string], "recommendations": [string], "summary": string}',
                f"TASK:\n{task}\n\nANSWER (attempt {revision}):\n{draft}",
                prefer="openai",
            )
            try:
                parsed = json.loads(text[text.find("{"):text.rfind("}") + 1])
            except Exception:
                parsed = {"score": 70, "strengths": [], "recommendations": [], "summary": text.strip()}
        score = int(parsed.get("score", 70))
        return EvaluationResult(
            revision=revision,
            reviewer=self.name,
            score=score,
            passed=score >= self.quality_threshold,
            strengths=parsed.get("strengths") or [],
            flaws=parsed.get("recommendations") or [],  # stored in the flaws column; shown as recommendations
            actionable_feedback=parsed.get("summary", ""),
            token_usage=usage,
        )

    def _record_step(self, run: OrchestrationRun, step: StepLog):
        """Append step, aggregate telemetry, and persist to SQLite."""
        run.steps.append(step)
        if step.token_usage:
            run.total_tokens += step.token_usage.total_tokens
            run.total_cost_usd = round(run.total_cost_usd + step.token_usage.cost_usd, 6)
        self.db.log_step(run.run_id, step)
        self.db.update_run(run)

    def chat(self, message: str) -> Dict[str, Any]:
        """Direct conversational query to Agent C (Supervisor)."""
        if self.agent_a.simulation_mode:
            registered = self.db.get_registered_agents()
            agents_summary = ", ".join([f"{a['name']} ({a['model']})" for a in registered]) if registered else "Agent A (OpenAI) and Agent B (Claude)"
            reply = (
                f"Hello! I am Agent C, the Supervisory Meta-Agent. "
                f"I actively manage: {agents_summary}.\n\n"
                f"Regarding: '{message}'\n"
                f"• I have Agent A (OpenAI) and Agent B (Claude) each answer the task.\n"
                f"• Each agent scores the other's answer from 0 to 100, and I continue with the stronger one.\n"
                f"• If that score is below threshold, I intervene and command revisions until it passes!\n\n"
                f"To launch a full self-correcting cycle, send your goal via the Live Orchestration tab or ask me to coordinate both agents."
            )
            usage = CostTracker.create_token_usage(self.model, 45, 120)
        else:
            from core.llm import NoApiKey, complete
            try:
                reply, usage = complete(
                    "You are Agent C, the supervisor of Agent A (builder) and Agent B (reviewer). "
                    "Answer the user's message directly. Do not reply with a canned status speech.",
                    message,
                    prefer="openai",
                )
            except NoApiKey as exc:
                reply, usage = str(exc), CostTracker.create_token_usage(self.model, 0, 0)
            except Exception as exc:
                reply = (
                    f"Hello! I am Agent C, your Supervisory Meta-Orchestrator.\n\n"
                    f"Regarding your query: \"{message}\"\n\n"
                    f"• I am actively ready to dispatch tasks to **Agent A (ChatGPT)** and **Agent B (Claude)**.\n"
                    f"• You can test each agent individually or select **Triad Council** to see them collaborate.\n"
                    f"*(Upstream notice: {exc})*"
                )
                usage = CostTracker.create_token_usage(self.model, 25, 45)
        return {
            "sender": self.name,
            "role": "Supervisor",
            "reply": reply,
            "tokens": usage.model_dump()
        }

    def triad_chat(self, message: str) -> List[Dict[str, Any]]:
        """Multi-agent collaborative conversation: C directs -> A drafts -> B reviews."""
        # 1. Supervisor acknowledges and assigns
        c_usage = CostTracker.create_token_usage(self.model, 40, 60)
        c_msg = {
            "sender": self.name,
            "role": "Supervisor",
            "reply": f"Directive received: '{message}'. Delegating initial solution to Agent A (OpenAI), followed by critical audit from Agent B (Claude).",
            "tokens": c_usage.model_dump()
        }

        # 2. Agent A drafts solution
        a_reply, a_usage = self.agent_a.chat(message)
        a_msg = {
            "sender": self.agent_a.name,
            "role": "Creator",
            "reply": a_reply,
            "tokens": a_usage.model_dump()
        }

        # 3. Agent B reviews
        b_prompt = f"Audit this response for '{message}':\n\n{a_reply}"
        b_reply, b_usage = self.agent_b.chat(b_prompt)
        b_msg = {
            "sender": self.agent_b.name,
            "role": "Auditor",
            "reply": b_reply,
            "tokens": b_usage.model_dump()
        }

        return [c_msg, a_msg, b_msg]

