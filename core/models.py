from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

class AgentProfile(BaseModel):
    name: str
    provider: str  # "OpenAI", "Anthropic", "Supervisor-Engine"
    model: str
    role: str
    capabilities: List[str]
    description: str

class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0

class StepLog(BaseModel):
    step_index: int
    sender: str
    receiver: str
    action: str
    content: str
    token_usage: Optional[TokenUsage] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class EvaluationResult(BaseModel):
    revision: int
    reviewer: str
    score: int  # 0 to 100
    passed: bool
    strengths: List[str]
    flaws: List[str]
    actionable_feedback: str
    token_usage: Optional[TokenUsage] = None

class OrchestrationRun(BaseModel):
    run_id: str
    task: str
    status: str  # PENDING, RUNNING, REVISING, COMPLETED, FAILED
    current_step: str = ""
    revisions_count: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    agent_profiles: Dict[str, AgentProfile] = Field(default_factory=dict)
    steps: List[StepLog] = Field(default_factory=list)
    evaluations: List[EvaluationResult] = Field(default_factory=list)
    final_output: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
