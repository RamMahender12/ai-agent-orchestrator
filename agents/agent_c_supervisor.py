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

        # Query Agent A
        profile_a = self.agent_a.get_profile()
        self.db.register_agent(profile_a)
        run.agent_profiles[profile_a.name] = profile_a

        step_a_disc = StepLog(
            step_index=step_counter,
            sender=self.name,
            receiver=profile_a.name,
            action="CAPABILITY_DISCOVERY",
            content=f"Queried capabilities for {profile_a.name}. Discovered: {', '.join(profile_a.capabilities)}. Model: {profile_a.model}.",
            token_usage=CostTracker.create_token_usage(self.model, 45, 80),
            metadata={"profile": profile_a.model_dump()}
        )
        self._record_step(run, step_a_disc)
        emit("agent_registered", {"agent": profile_a.model_dump(), "step": step_a_disc.model_dump()})
        step_counter += 1

        # Query Agent B
        profile_b = self.agent_b.get_profile()
        self.db.register_agent(profile_b)
        run.agent_profiles[profile_b.name] = profile_b

        step_b_disc = StepLog(
            step_index=step_counter,
            sender=self.name,
            receiver=profile_b.name,
            action="CAPABILITY_DISCOVERY",
            content=f"Queried capabilities for {profile_b.name}. Discovered: {', '.join(profile_b.capabilities)}. Model: {profile_b.model}.",
            token_usage=CostTracker.create_token_usage(self.model, 45, 85),
            metadata={"profile": profile_b.model_dump()}
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

            # Dispatch to Agent A
            a_context = {"revision": revision, "feedback": current_feedback}
            current_draft, a_usage = self.agent_a.execute(task, a_context)

            step_a_exec = StepLog(
                step_index=step_counter,
                sender=self.agent_a.name,
                receiver=self.name,
                action="DRAFT_SUBMISSION",
                content=current_draft,
                token_usage=a_usage,
                metadata={"revision": revision, "had_prior_feedback": bool(current_feedback)}
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

            b_context = {
                "draft": current_draft,
                "revision": revision,
                "threshold": self.quality_threshold
            }
            evaluation = self.agent_b.evaluate_draft(task, b_context)
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
                metadata={"evaluation": evaluation.model_dump()}
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

                step_intervention = StepLog(
                    step_index=step_counter,
                    sender=self.name,
                    receiver=self.agent_a.name,
                    action="REVISE_DIRECTIVE",
                    content=current_feedback,
                    token_usage=CostTracker.create_token_usage(self.model, 85, 120),
                    metadata={"revision": revision, "score": evaluation.score}
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

