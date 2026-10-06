import os
from typing import Dict, Any, List, Optional, Tuple
from agents.base_agent import BaseAgent
from core.models import AgentProfile, TokenUsage
from core.llm import complete

# Free OpenRouter chat models that answer alongside A and B. Override a model with AGENT_D_MODEL etc.
FREE_MODELS = [
    ("D", "Apodex", "apodex/apodex-1.1-mini:free"),
    ("E", "Ling", "inclusionai/ling-3.0-flash-sante:free"),
    ("F", "Dots", "dots-studio/dots-3-note-preview:free"),
]


class FreeAgent(BaseAgent):
    """A worker backed by one free OpenRouter model. Answers the task and revises from C's recommendations."""
    fallback = False  # a failure must show up as this model failing, not be answered by another model

    def __init__(self, letter: str, label: str, model: str, simulation_mode: bool = True):
        super().__init__(name=f"Agent {letter} ({label})", provider="OpenRouter", model=model, role="Free-Model Generator")
        self.key = letter.lower()
        self.simulation_mode = simulation_mode

    def get_profile(self) -> AgentProfile:
        return AgentProfile(
            name=self.name,
            provider=self.provider,
            model=self.model,
            role=self.role,
            capabilities=["Answer drafting", "Revision from supervisor recommendations"],
            description=f"I answer the task with the free model {self.model} and revise it from Agent C's recommendations.",
        )

    def chat(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[str, TokenUsage]:
        return complete(f"You are {self.name}. Answer the user's prompt directly.", message, history, model=self.model, fallback=False)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, TokenUsage]:
        return self.draft(task, context)


def free_agents(simulation_mode: bool = True) -> List[FreeAgent]:
    return [FreeAgent(letter, label, os.getenv(f"AGENT_{letter}_MODEL", model), simulation_mode) for letter, label, model in FREE_MODELS]
