from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from core.models import AgentProfile, TokenUsage

class BaseAgent(ABC):
    def __init__(self, name: str, provider: str, model: str, role: str):
        self.name = name
        self.provider = provider
        self.model = model
        self.role = role

    @abstractmethod
    def get_profile(self) -> AgentProfile:
        """Returns the capabilities and role of the agent when asked by the supervisor."""
        pass

    @abstractmethod
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, TokenUsage]:
        """Executes a task and returns output with token telemetry."""
        pass
