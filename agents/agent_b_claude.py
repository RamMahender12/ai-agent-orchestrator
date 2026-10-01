import os
from typing import Dict, Any, Optional, Tuple, List
from agents.base_agent import BaseAgent
from core.models import AgentProfile, TokenUsage
from core.cost_tracker import CostTracker
from core.llm import NoApiKey, complete

try:
    import anthropic
except ImportError:
    anthropic = None

class AgentBClaude(BaseAgent):
    """
    Agent B: Anthropic Claude Agent.
    Answers the task, revises from feedback, and scores Agent A's answer.
    """
    prefer = "anthropic"

    def __init__(self, model: str = "nvidia/nemotron-3-ultra-550b-a55b:free", simulation_mode: bool = True):
        super().__init__(
            name="Agent B (Claude)",
            provider="Anthropic",
            model=model,
            role="Quality Auditor & Critical Evaluator"
        )
        self.simulation_mode = simulation_mode
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.client = None
        if not self.simulation_mode and self.api_key and anthropic:
            try:
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except Exception:
                self.client = None

    def get_profile(self) -> AgentProfile:
        return AgentProfile(
            name=self.name,
            provider=self.provider,
            model=self.model,
            role=self.role,
            capabilities=[
                "Critical Logic & Architectural Audit",
                "Edge Case & Failure Scenario Discovery",
                "Quantitative Quality Scoring (0-100)",
                "Security & Production Readiness Review",
                "Actionable Defect Formulation",
                "Independent Answer Drafting & Revision"
            ],
            description="I am an Anthropic Claude agent specializing in critical review and evaluation. I write my own answer to the task, examine Agent A's answer for gaps, edge cases, and architectural weaknesses, then generate rigorous quantitative scores and actionable improvement recommendations."
        )

    def chat(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[str, TokenUsage]:
        """Interactive conversational interface with Agent B (Claude)."""
        history = history or []
        if not self.simulation_mode:
            try:
                return complete(
                    "You are Agent B, a critical reviewer. Answer the user's prompt directly. Judge only what they asked.",
                    message,
                    history,
                    prefer="anthropic",
                    model=self.model,
                )
            except NoApiKey as exc:
                return str(exc), CostTracker.create_token_usage(self.model, 0, 0)
            except Exception as exc:
                return f"[Model error: {exc}]", CostTracker.create_token_usage(self.model, 0, 0)
        else:
            # Dynamic simulated audit analysis tailored to user query
            msg_lower = message.lower()
            reply = (
                f"### Quality Audit & Vulnerability Assessment\n"
                f"**Auditor:** Agent B (Anthropic {self.model})\n\n"
                f"**Subject:** *\"{message.splitlines()[0][:60]}\"*\n\n"
                f"#### 1. Critical Risk Breakdown\n"
                f"• **Single Point of Failure (SPOF):** Ensure redundant failover and avoid reliance on single node instances.\n"
                f"• **Concurrency & Race Conditions:** In distributed environments, enforce distributed locking (Redlock) or idempotent transaction tokens.\n"
                f"• **Security & Blast Radius:** Enforce principle of least privilege (IAM) and zero-trust mutual TLS (mTLS) across all RPC boundaries.\n\n"
                f"#### 2. Quantitative Benchmark Targets\n"
                f"• **Availability SLA:** 99.99% uptime with < 5s automatic failover.\n"
                f"• **Latency Targets:** P95 < 25ms, P99 < 80ms under peak 5,000 TPS load.\n\n"
                f"#### 3. Auditor Recommendation\n"
                f"Have **Agent A** draft the technical implementation, and I will perform an automated 0-100 quality score and verification cycle under **Supervisor Agent C**."
            )
            p_tokens = CostTracker.estimate_tokens_from_text(message) + 55
            c_tokens = CostTracker.estimate_tokens_from_text(reply)
            return reply, CostTracker.create_token_usage(self.model, p_tokens, c_tokens)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, TokenUsage]:
        """Base execute implementation."""

        eval_res = self.evaluate_draft(task, context or {})
        summary = (
            f"Audit Complete. Score: {eval_res.score}/100. Verdict: {'APPROVED' if eval_res.passed else 'REJECTED'}.\n"
            f"Flaws: {', '.join(eval_res.flaws)}\n"
            f"Feedback: {eval_res.actionable_feedback}"
        )
        return summary, eval_res.token_usage

