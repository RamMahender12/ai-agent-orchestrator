import uuid
import json
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
from core.a2a import card_for, router as a2a_router, task_text

class AgentCSupervisor:
    """
    Agent C: Meta-Orchestrator & Supervisor Agent.
    - Interrogates Agent A and Agent B to discover capabilities and logs them to Database.
    - Has A and B both answer the task and score each other's answer.
    - Calculates real-time tokens and USD costs for Agent A, Agent B, and Agent C.
    - Continues with the higher-scored answer; if it is below the pass score, instructs its author to revise it.
    - Commits full audit logs and metrics to SQLite and disk.
    """
    def __init__(
        self,
        agent_a: Optional[AgentAOpenAI] = None,
        agent_b: Optional[AgentBClaude] = None,
        database: Optional[Database] = None,
        quality_threshold: int = 80,
        max_revisions: int = 3
    ):
        self.name = "Agent C (Supervisor)"
        self.provider = "Orchestration-Core"
        self.model = "supervisor-engine"
        self.agent_a = agent_a or AgentAOpenAI()
        self.agent_b = agent_b or AgentBClaude()
        self.db = database or Database()
        self.quality_threshold = quality_threshold
        self.max_revisions = max_revisions
        self.a2a = a2a_router

    def get_profile(self):
        from core.models import AgentProfile
        return AgentProfile(
            name=self.name,
            provider=self.provider,
            model=self.model,
            role="Supervisor",
            capabilities=[
                "A2A discovery of Agent A and Agent B",
                "Task dispatch via message/send",
                "Token and USD cost tracking",
                "Cross-review: each agent scores the other's answer",
                "Revision orders when quality is too low",
            ],
            description="I am Agent C. I ask A and B what they do, have both answer the task over A2A, have each score the other's answer, log the work, track tokens and cost, and tell the author of the stronger answer to revise it when its score is too low.",
        )

    def bind_a2a(self):
        """Publish A, B, and C on the shared A2A router."""
        worker_skills = [
            {"id": "describe", "name": "What I do", "description": "Return capabilities.", "tags": ["discovery"]},
            {"id": "draft", "name": "Draft", "description": "Answer the task.", "tags": ["create"]},
            {"id": "audit", "name": "Audit", "description": "Score the other agent's answer from 0 to 100.", "tags": ["review"]},
            {"id": "revise", "name": "Revise", "description": "Redo the work from supervisor critique.", "tags": ["revise"]},
        ]
        self.a2a.bind("a", card_for(self.agent_a, worker_skills), lambda m: self._on_worker(self.agent_a, m))
        self.a2a.bind("b", card_for(self.agent_b, worker_skills), lambda m: self._on_worker(self.agent_b, m))
        self.a2a.bind("c", card_for(self, [
            {"id": "describe", "name": "What I do", "description": "Discover A and B and report cost.", "tags": ["discovery"]},
            {"id": "orchestrate", "name": "Orchestrate", "description": "Have A and B both answer, score each other, and revise the stronger answer until it passes.", "tags": ["orchestrate"]},
            {"id": "monitor", "name": "Monitor", "description": "List A2A tasks and token cost for A, B, and C.", "tags": ["monitor"]},
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
            cards = {key: self.a2a.card(key) for key in ("a", "b")}
            for key, card in cards.items():
                self.db.register_agent(self._profile_from_card(card, task_text(self.a2a.send(key, "What do you do?", skill="describe"))))
            body = (
                "I am Agent C. I discover A (OpenAI) and B (Claude) from their A2A agent cards, "
                "task them with message/send, log every task, and sum token cost. "
                f"A: {cards['a']['description']} B: {cards['b']['description']}"
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
        2. Agent A and Agent B each answer the task
        3. Cross-review: B scores A's answer, A scores B's answer
        4. Supervisor continues with the higher-scored answer
        5. While that score < threshold, its author revises from the other agent's critique
        6. Final output is the best-scoring draft; persistence and telemetry consolidation
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

        workers = {"a": self.agent_a, "b": self.agent_b}
        other = {"a": "b", "b": "a"}

        # ==========================================
        # STEP 1: Supervisor queries A and B capabilities
        # ==========================================
        emit("status_change", {"status": "DISCOVERY", "message": "Supervisor interrogating Agent A and Agent B..."})

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

        def write(key: str, revision: int, feedback: Optional[str] = None, previous: Optional[str] = None) -> str:
            """Have one agent answer the task (or revise its answer) over A2A message/send."""
            agent = workers[key]
            run.status = f"REVISION_{revision}_GENERATION_{key.upper()}"
            self.db.update_run(run)
            emit("status_change", {
                "status": run.status,
                "message": f"Supervisor dispatching task to {agent.name} (Revision {revision})..."
            })
            if not feedback:  # on later rounds the REVISE_DIRECTIVE step is C's message
                log(self.name, agent.name, "TASK_DISPATCH", f"Do this task and send me your draft:\n{task}", revision=revision)
            sent = self.a2a.send(key, task, skill="revise" if feedback else "draft", data={
                "task": task,
                "revision": revision,
                "feedback": feedback,
                "previous": previous,
            }, context_id=run_id)
            draft = task_text(sent)
            usage = TokenUsage(**sent["metadata"]["usage"])
            step = log(
                agent.name, self.name, "REVISED_DRAFT" if feedback else "DRAFT_SUBMISSION", draft, usage,
                revision=revision, **self._a2a_meta(sent),
            )
            emit("draft_produced", {
                "revision": revision,
                "agent": agent.name,
                "draft": draft,
                "tokens": usage.model_dump(),
                "step": step.model_dump()
            })
            return draft

        def score(author: str, draft: str, revision: int) -> EvaluationResult:
            """Have the other agent score this author's draft, so nobody grades their own work."""
            reviewer = workers[other[author]]
            run.status = f"REVISION_{revision}_AUDIT_{other[author].upper()}"
            self.db.update_run(run)
            emit("status_change", {
                "status": run.status,
                "message": f"Supervisor routing {workers[author].name}'s draft to {reviewer.name} for critical audit..."
            })
            log(
                self.name, reviewer.name, "AUDIT_REQUEST",
                f"Score {workers[author].name}'s attempt {revision} from 0 to 100 against the task. List the problems. Pass score is {self.quality_threshold}.",
                revision=revision,
            )
            sent = self.a2a.send(other[author], task, skill="audit", data={
                "task": task,
                "draft": draft,
                "revision": revision,
                "threshold": self.quality_threshold,
            }, context_id=run_id)
            evaluation = EvaluationResult(**sent["metadata"]["result"])
            run.evaluations.append(evaluation)
            self.db.log_evaluation(run.run_id, evaluation)
            step = log(
                reviewer.name, self.name, "AUDIT_VERDICT",
                (
                    f"Quality Score: {evaluation.score}/100. "
                    f"Passed: {evaluation.passed}. "
                    f"Flaws Detected: {len(evaluation.flaws)}. "
                    f"Recommendation: {evaluation.actionable_feedback}"
                ),
                evaluation.token_usage,
                evaluation=evaluation.model_dump(), author=workers[author].name, **self._a2a_meta(sent),
            )
            emit("audit_completed", {
                "revision": revision,
                "author": workers[author].name,
                "evaluation": evaluation.model_dump(),
                "step": step.model_dump()
            })
            return evaluation

        # ==========================================
        # STEP 2: Both agents answer, then score each other's answer
        # ==========================================
        # ponytail: A and B are called one after the other; run them in threads if the wait matters
        revision = 1
        run.revisions_count = revision
        drafts = {key: write(key, revision) for key in workers}
        verdicts = {key: score(key, drafts[key], revision) for key in workers}

        # Supervisor picks the stronger answer (a tie goes to A)
        lead = max(workers, key=lambda key: verdicts[key].score)
        author = workers[lead]
        draft, evaluation = drafts[lead], verdicts[lead]
        best_draft, best = draft, evaluation
        step = log(
            self.name, "ALL", "WINNER_SELECTED",
            (
                f"{self.agent_a.name} scored {verdicts['a'].score}/100 and {self.agent_b.name} scored {verdicts['b'].score}/100. "
                f"Continuing with {author.name}'s answer."
            ),
            winner=author.name, scores={workers[key].name: verdicts[key].score for key in workers},
        )
        emit("winner_selected", {
            "winner": author.name,
            "scores": step.metadata["scores"],
            "step": step.model_dump()
        })

        # ==========================================
        # STEP 3: Quality gate. The winner revises from the other agent's critique until it passes
        # ==========================================
        while evaluation.score < self.quality_threshold and revision < self.max_revisions:
            emit("status_change", {
                "status": "SUPERVISOR_INTERVENTION",
                "message": f"Quality score {evaluation.score}/100 failed threshold {self.quality_threshold}. Supervisor instructing {author.name} to revise..."
            })

            feedback = (
                f"Supervisor Directive: Revision {revision} fell below quality threshold ({evaluation.score}/{self.quality_threshold}).\n"
                f"Critique from {workers[other[lead]].name}:\n"
                f"- Identified Flaws: {'; '.join(evaluation.flaws)}\n"
                f"- Actionable Instructions: {evaluation.actionable_feedback}\n"
                f"Requirement: Incorporate all missing specifications immediately in your next submission."
            )
            order = self.a2a.send(lead, feedback, skill="instruct", data={
                "task": task, "revision": revision,
            }, context_id=run_id)
            step = log(
                self.name, author.name, "REVISE_DIRECTIVE", feedback, TokenUsage(**order["metadata"]["usage"]),
                revision=revision, score=evaluation.score, **self._a2a_meta(order),
            )
            emit("supervisor_intervention", {
                "revision": revision,
                "agent": author.name,
                "critique": feedback,
                "score": evaluation.score,
                "step": step.model_dump()
            })

            revision += 1
            run.revisions_count = revision
            draft = write(lead, revision, feedback, previous=draft)
            evaluation = score(lead, draft, revision)
            if evaluation.score > best.score:  # a revision can score lower; keep the best one
                best_draft, best = draft, evaluation

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

