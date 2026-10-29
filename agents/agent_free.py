import os
from typing import Dict, Any, List, Optional, Tuple
from agents.base_agent import BaseAgent
from core.models import AgentProfile, TokenUsage
from core.llm import complete

# Free OpenRouter chat models that answer alongside A and B. Override a model with AGENT_D_MODEL etc.
FREE_MODELS = [
    ("D", "Flint", "recursive/flint-v1.0:free"),
    ("E", "Xing", "xingchen-agi/xing4.0-29b-a4b:free"),
    ("F", "Dots", "dots-studio/dots-3-note-preview:free"),
    ("G", "Nemotron Lightning", "nvidia/nemotron-3.5-lightning:free"),
    ("H", "Laguna XS", "poolside/laguna-xs-2.1:free"),
    ("I", "Gemma", "google/gemma-4-31b-it:free"),
    ("J", "North", "cohere/north-mini-code:free"),
    ("K", "Nemotron Super", "nvidia/nemotron-3.5-super-vl:free"),
    ("L", "Nemotron Nano", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free"),
    ("M", "Gemma Small", "google/gemma-4-26b-a4b-it:free"),
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
            capabilities=["Answer drafting", "Revision from captain recommendations"],
            description=f"I answer the task with the free model {self.model} and revise it from Agent C's recommendations.",
        )

    def chat(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[str, TokenUsage]:
        return complete(f"You are {self.name}. Answer the user's prompt directly.", message, history, model=self.model, fallback=False)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, TokenUsage]:
        return self.draft(task, context)


def free_agents(simulation_mode: bool = True) -> List[FreeAgent]:
    return [FreeAgent(letter, label, os.getenv(f"AGENT_{letter}_MODEL", model), simulation_mode) for letter, label, model in FREE_MODELS]
