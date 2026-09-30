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
    - Assigns tasks and continuously tracks execution status.
    - Calculates real-time tokens and USD costs for Agent A, Agent B, and Agent C.
    - Analyzes evaluations; if Agent A's output is inadequate, instructs Agent A to revise it.
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
                "Revision orders when quality is too low",
            ],
            description="I am Agent C. I ask A and B what they do, task them over A2A, log the work, track tokens and cost, and tell A to revise when B rejects the draft.",
        )

    def bind_a2a(self):
        """Publish A, B, and C on the shared A2A router."""
        self.a2a.bind("a", card_for(self.agent_a, [
            {"id": "describe", "name": "What I do", "description": "Return capabilities.", "tags": ["discovery"]},
            {"id": "draft", "name": "Draft", "description": "Produce a first deliverable.", "tags": ["create"]},
            {"id": "revise", "name": "Revise", "description": "Redo the work from supervisor critique.", "tags": ["revise"]},
        ]), self._on_a)
        self.a2a.bind("b", card_for(self.agent_b, [
            {"id": "describe", "name": "What I do", "description": "Return capabilities.", "tags": ["discovery"]},
            {"id": "audit", "name": "Audit", "description": "Score a draft from 0 to 100.", "tags": ["review"]},
        ]), self._on_b)
        self.a2a.bind("c", card_for(self, [
            {"id": "describe", "name": "What I do", "description": "Discover A and B and report cost.", "tags": ["discovery"]},
            {"id": "orchestrate", "name": "Orchestrate", "description": "Run A, have B audit, tell A to revise if the score is low.", "tags": ["orchestrate"]},
            {"id": "monitor", "name": "Monitor", "description": "List A2A tasks and token cost for A, B, and C.", "tags": ["monitor"]},
        ]), self._on_c)

    def _usage(self, model: str, prompt: str, completion: str):
        return CostTracker.create_token_usage(
            model,
            CostTracker.estimate_tokens_from_text(prompt),
            CostTracker.estimate_tokens_from_text(completion),
        ).model_dump()

    def _on_a(self, message: Dict[str, Any]) -> Dict[str, Any]:
        from core.a2a import message_data, message_text
        text = message_text(message)
        data = message_data(message)
        skill = (message.get("metadata") or {}).get("skill") or "draft"
        if skill == "describe" or text.lower().strip(" ?.!") in ("what do you do", "who are you"):
            profile = self.agent_a.get_profile()
            body = f"{profile.description} Capabilities: {', '.join(profile.capabilities)}"
            return {"text": body, "usage": self._usage(self.agent_a.model, text, body), "model": self.agent_a.model}
        if skill == "instruct":
            body = "Acknowledged. I will revise the draft against that critique."
            return {"text": body, "usage": self._usage(self.agent_a.model, text, body), "model": self.agent_a.model}
        out, usage = self.agent_a.execute(data.get("task") or text, {
            "revision": data.get("revision", 2 if skill == "revise" else 1),
            "feedback": data.get("feedback"),
        })
        return {"text": out, "usage": usage.model_dump(), "model": self.agent_a.model}

    def _on_b(self, message: Dict[str, Any]) -> Dict[str, Any]:
        from core.a2a import message_data, message_text
        text = message_text(message)
        data = message_data(message)
        skill = (message.get("metadata") or {}).get("skill") or ("audit" if data.get("draft") else "chat")
        if skill == "describe" or text.lower().strip(" ?.!") in ("what do you do", "who are you"):
            profile = self.agent_b.get_profile()
            body = f"{profile.description} Capabilities: {', '.join(profile.capabilities)}"
            return {"text": body, "usage": self._usage(self.agent_b.model, text, body), "model": self.agent_b.model}
        if skill == "audit":
            evaluation = self.agent_b.evaluate_draft(data.get("task") or text, {
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
                "usage": evaluation.token_usage.model_dump() if evaluation.token_usage else self._usage(self.agent_b.model, text, summary),
                "model": self.agent_b.model,
            }
        reply, usage = self.agent_b.chat(text)
        return {"text": reply, "usage": usage.model_dump(), "model": self.agent_b.model}

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
        2. Task Dispatch to Agent A
        3. Audit & Scoring by Agent B
        4. Supervisor Intervention & Feedback loop if score < threshold
        5. Final persistence and telemetry consolidation
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

        step_counter = 1

        # ==========================================
        # STEP 1: Supervisor queries A and B capabilities
        # ==========================================
        emit("status_change", {"status": "DISCOVERY", "message": "Supervisor interrogating Agent A and Agent B..."})

        # Query Agent A over A2A (agent card + message/send)
        card_a = self.a2a.card("a")
        desc_a = self.a2a.send("a", "What do you do?", skill="describe", context_id=run_id)
        profile_a = self._profile_from_card(card_a, task_text(desc_a))
        self.db.register_agent(profile_a)
        run.agent_profiles[profile_a.name] = profile_a

        step_a_disc = StepLog(
            step_index=step_counter,
            sender=self.name,
            receiver=profile_a.name,
            action="CAPABILITY_DISCOVERY",
            content=f"A2A card for {profile_a.name}. Discovered: {', '.join(profile_a.capabilities)}. Model: {profile_a.model}.",
            token_usage=TokenUsage(**(desc_a["metadata"]["usage"])),
            metadata={"profile": profile_a.model_dump(), **self._a2a_meta(desc_a)}
        )
        self._record_step(run, step_a_disc)
        emit("agent_registered", {"agent": profile_a.model_dump(), "step": step_a_disc.model_dump()})
        step_counter += 1

        # Query Agent B over A2A
        card_b = self.a2a.card("b")
        desc_b = self.a2a.send("b", "What do you do?", skill="describe", context_id=run_id)
        profile_b = self._profile_from_card(card_b, task_text(desc_b))
        self.db.register_agent(profile_b)
        run.agent_profiles[profile_b.name] = profile_b

        step_b_disc = StepLog(
            step_index=step_counter,
            sender=self.name,
            receiver=profile_b.name,
            action="CAPABILITY_DISCOVERY",
            content=f"A2A card for {profile_b.name}. Discovered: {', '.join(profile_b.capabilities)}. Model: {profile_b.model}.",
            token_usage=TokenUsage(**(desc_b["metadata"]["usage"])),
            metadata={"profile": profile_b.model_dump(), **self._a2a_meta(desc_b)}
        )
        self._record_step(run, step_b_disc)
        emit("agent_registered", {"agent": profile_b.model_dump(), "step": step_b_disc.model_dump()})
        step_counter += 1

        # ==========================================
        # STEP 2: Iterative Generation & Critique Loop
        # ==========================================
        revision = 1
        current_draft = ""
        current_feedback = None
        is_approved = False

        while revision <= self.max_revisions and not is_approved:
            run.revisions_count = revision
            run.status = f"REVISION_{revision}_GENERATION"
            emit("status_change", {
                "status": run.status,
                "message": f"Supervisor dispatching task to Agent A (Revision {revision})..."
            })

            # Dispatch to Agent A via A2A message/send. Revision > 1 is the "do it better" order.
            a_skill = "revise" if current_feedback else "draft"
            a_task = self.a2a.send("a", task, skill=a_skill, data={
                "task": task,
                "revision": revision,
                "feedback": current_feedback,
            }, context_id=run_id)
            current_draft = task_text(a_task)
            a_usage = TokenUsage(**a_task["metadata"]["usage"])

            step_a_exec = StepLog(
                step_index=step_counter,
                sender=self.agent_a.name,
                receiver=self.name,
                action="DRAFT_SUBMISSION" if a_skill == "draft" else "REVISED_DRAFT",
                content=current_draft,
                token_usage=a_usage,
                metadata={"revision": revision, "had_prior_feedback": bool(current_feedback), **self._a2a_meta(a_task)}
            )
            self._record_step(run, step_a_exec)
            emit("draft_produced", {
                "revision": revision,
                "agent": self.agent_a.name,
                "draft": current_draft,
                "tokens": a_usage.model_dump(),
                "step": step_a_exec.model_dump()
            })
            step_counter += 1

            # Dispatch to Agent B (Claude) for evaluation
            run.status = f"REVISION_{revision}_AUDIT"
            emit("status_change", {
                "status": run.status,
                "message": f"Supervisor routing draft to Agent B (Claude) for critical audit..."
            })

            b_task = self.a2a.send("b", task, skill="audit", data={
                "task": task,
                "draft": current_draft,
                "revision": revision,
                "threshold": self.quality_threshold,
            }, context_id=run_id)
            evaluation = EvaluationResult(**b_task["metadata"]["result"])
            run.evaluations.append(evaluation)
            self.db.log_evaluation(run.run_id, evaluation)

            step_b_audit = StepLog(
                step_index=step_counter,
                sender=self.agent_b.name,
                receiver=self.name,
                action="AUDIT_VERDICT",
                content=(
                    f"Quality Score: {evaluation.score}/100. "
                    f"Passed: {evaluation.passed}. "
                    f"Flaws Detected: {len(evaluation.flaws)}. "
                    f"Recommendation: {evaluation.actionable_feedback}"
                ),
                token_usage=evaluation.token_usage,
                metadata={"evaluation": evaluation.model_dump(), **self._a2a_meta(b_task)}
            )
            self._record_step(run, step_b_audit)
            emit("audit_completed", {
                "revision": revision,
                "evaluation": evaluation.model_dump(),
                "step": step_b_audit.model_dump()
            })
            step_counter += 1

            # Supervisor Quality Gate & Decision
            if evaluation.passed or evaluation.score >= self.quality_threshold:
                is_approved = True
                run.status = "COMPLETED"
                run.final_output = current_draft
                run.completed_at = datetime.utcnow()

                step_approval = StepLog(
                    step_index=step_counter,
                    sender=self.name,
                    receiver="ALL",
                    action="APPROVAL_FINALIZED",
                    content=(
                        f"Deliverable successfully approved at Revision {revision} with Score {evaluation.score}/100. "
                        f"All quality benchmarks met."
                    ),
                    token_usage=CostTracker.create_token_usage(self.model, 60, 40),
                    metadata={"final_revision": revision, "final_score": evaluation.score}
                )
                self._record_step(run, step_approval)
                emit("workflow_completed", {
                    "final_score": evaluation.score,
                    "revisions": revision,
                    "final_output": current_draft,
                    "step": step_approval.model_dump()
                })
                step_counter += 1
            else:
                # Agent A was not doing a good job! Supervisor intervenes
                emit("status_change", {
                    "status": "SUPERVISOR_INTERVENTION",
                    "message": f"Quality score {evaluation.score}/100 failed threshold {self.quality_threshold}. Supervisor instructing Agent A to revise..."
                })

                current_feedback = (
                    f"Supervisor Directive: Revision {revision} fell below quality threshold ({evaluation.score}/{self.quality_threshold}).\n"
                    f"Critique from Agent B:\n"
                    f"- Identified Flaws: {'; '.join(evaluation.flaws)}\n"
                    f"- Actionable Instructions: {evaluation.actionable_feedback}\n"
                    f"Requirement: Incorporate all missing specifications immediately in your next submission."
                )
                order = self.a2a.send("a", current_feedback, skill="instruct", data={
                    "task": task, "revision": revision,
                }, context_id=run_id)

                step_intervention = StepLog(
                    step_index=step_counter,
                    sender=self.name,
                    receiver=self.agent_a.name,
                    action="REVISE_DIRECTIVE",
                    content=current_feedback,
                    token_usage=TokenUsage(**order["metadata"]["usage"]),
                    metadata={"revision": revision, "score": evaluation.score, **self._a2a_meta(order)}
                )
                self._record_step(run, step_intervention)
                emit("supervisor_intervention", {
                    "revision": revision,
                    "critique": current_feedback,
                    "score": evaluation.score,
                    "step": step_intervention.model_dump()
                })
                step_counter += 1
                revision += 1

        if not is_approved:
            run.status = "MAX_REVISIONS_REACHED"
            run.final_output = current_draft
            run.completed_at = datetime.utcnow()

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
                f"• I can direct Agent A (OpenAI) to draft implementations, specs, or proposals.\n"
                f"• I route all drafts to Agent B (Claude) for critical scrutiny and quantitative scoring.\n"
                f"• If Agent A's score is below threshold, I intervene and command revisions until it passes!\n\n"
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
                    f"• I am actively ready to dispatch tasks to **Agent A (Creator)** and **Agent B (Auditor)**.\n"
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

