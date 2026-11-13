import re
from typing import Dict, Any, List, Optional, Tuple
from agents.base_agent import BaseAgent
from core import registry
from core.cost_tracker import CostTracker
from core.models import AgentProfile, TokenUsage

LETTERS = "NOP"  # registry agents take the letters after the free models (A to M), so at most three per run


class RegistryAgent(BaseAgent):
    """A worker hosted by someone else and listed on a2a-registry.org. C reaches it over A2A message/send."""
    fallback = False

    def __init__(self, letter: str, agent_id: str, label: str, description: str = "", simulation_mode: bool = True):
        super().__init__(name=f"Agent {letter} ({label})", provider="A2A Registry", model=agent_id, role="Registry Agent")
        self.key = letter.lower()
        self.agent_id = agent_id
        self.description = description
        self.simulation_mode = simulation_mode

    def get_profile(self) -> AgentProfile:
        return AgentProfile(
            name=self.name,
            provider=self.provider,
            model=self.model,
            role=self.role,
            capabilities=["Answer drafting over A2A", "Revision from captain recommendations"],
            description=self.description or f"An outside agent from the A2A Registry ({self.agent_id}).",
        )

    def chat(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[str, TokenUsage]:
        return self._send(message)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, TokenUsage]:
        return self.draft(task, context)

    def _draft_real(self, task: str, revision: int, feedback: Optional[str], previous: Optional[str]) -> Tuple[str, TokenUsage]:
        text = task
        if feedback:
            text += (f"\n\nYOUR PREVIOUS ANSWER:\n{previous}" if previous else "") + f"\n\n{feedback}\nSend an improved answer."
        return self._send(text)

    def _send(self, text: str) -> Tuple[str, TokenUsage]:
        reply = registry.send(self.agent_id, text)
        if reply["error"]:
            raise RuntimeError(f"The agent answered with an error: {reply['error']}")
        if not reply["text"].strip():
            raise RuntimeError("The agent's reply had no text")
        # the agent reports no tokens or price, so tokens are estimated from the text and cost is 0
        p, c = CostTracker.estimate_tokens_from_text(text), CostTracker.estimate_tokens_from_text(reply["text"])
        return reply["text"], TokenUsage(prompt_tokens=p, completion_tokens=c, total_tokens=p + c)


def registry_agents(picked: List[Dict[str, Any]], simulation_mode: bool = True) -> List[RegistryAgent]:
    """picked: registry entries ({packageName, displayName, description}) in the order the user chose them."""
    # "(" and ")" are stripped from the label: the UI reads it back out of "Agent N (label)"
    return [RegistryAgent(letter, a["packageName"], re.sub(r"[()]", "", a.get("displayName") or a["packageName"]).strip(), a.get("description") or "", simulation_mode)
            for letter, a in zip(LETTERS, picked)]
