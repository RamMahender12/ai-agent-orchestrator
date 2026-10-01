import os
from typing import Dict, Any, Optional, Tuple, List
from agents.base_agent import BaseAgent
from core.models import AgentProfile, TokenUsage
from core.cost_tracker import CostTracker
from core.llm import NoApiKey, complete

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

class AgentAOpenAI(BaseAgent):
    """
    Agent A: OpenAI Agent (ChatGPT / GPT-4o).
    Answers the task, revises from feedback, and scores Agent B's answer.
    """
    sim_first_score = 74  # differs from B's 68 so the simulated round 1 has a clear winner

    def __init__(self, model: str = "poolside/laguna-s-2.1:free", simulation_mode: bool = True):
        super().__init__(
            name="Agent A (ChatGPT)",
            provider="OpenAI",
            model=model,
            role="Primary Generator & Technical Creator"
        )
        self.simulation_mode = simulation_mode
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.client = None
        if not self.simulation_mode and self.api_key and OpenAI:
            try:
                self.client = OpenAI(api_key=self.api_key)
            except Exception:
                self.client = None

    def get_profile(self) -> AgentProfile:
        return AgentProfile(
            name=self.name,
            provider=self.provider,
            model=self.model,
            role=self.role,
            capabilities=[
                "Generative Text & Content Drafting",
                "Code Architecture & Implementation",
                "Technical Proposal Generation",
                "Iterative Refinement from Feedback Loops",
                "Quantitative Quality Scoring (0-100) of Agent B's answer"
            ],
            description="I am an OpenAI-powered generator. I specialize in drafting solutions, coding architectures, and producing comprehensive proposals. When provided with critiques, I iteratively refine my work. I also score Agent B's answer to the same task."
        )

    def chat(self, message: str, history: Optional[List[Dict[str, str]]] = None) -> Tuple[str, TokenUsage]:
        """Interactive conversational interface with Agent A."""
        history = history or []
        if not self.simulation_mode:
            try:
                return complete(
                    "You are Agent A. Answer the user's prompt directly. Do not substitute a generic architecture essay.",
                    message,
                    history,
                    prefer="openai",
                    model=self.model,
                )
            except NoApiKey as exc:
                return str(exc), CostTracker.create_token_usage(self.model, 0, 0)
            except Exception as exc:
                return f"[Model error: {exc}]", CostTracker.create_token_usage(self.model, 0, 0)
        else:
            # Dynamic simulated response tailored to user query
            msg_lower = message.lower()
            if any(k in msg_lower for k in ["redis", "cache", "lru", "caching"]):
                reply = (
                    f"### Python In-Memory LRU Cache with TTL Expiration\n"
                    f"**Author:** Agent A (OpenAI {self.model})\n\n"
                    f"Here is a production-ready asynchronous cache implementation:\n"
                    f"```python\n"
                    f"import time\n"
                    f"from collections import OrderedDict\n"
                    f"from typing import Any, Optional\n\n"
                    f"class AsyncLRUCache:\n"
                    f"    def __init__(self, capacity: int = 1000, default_ttl_seconds: int = 300):\n"
                    f"        self.capacity = capacity\n"
                    f"        self.default_ttl = default_ttl_seconds\n"
                    f"        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()\n\n"
                    f"    def get(self, key: str) -> Optional[Any]:\n"
                    f"        if key not in self._store:\n"
                    f"            return None\n"
                    f"        val, expires_at = self._store[key]\n"
                    f"        if time.time() > expires_at:\n"
                    f"            del self._store[key]\n"
                    f"            return None\n"
                    f"        self._store.move_to_end(key)\n"
                    f"        return val\n\n"
                    f"    def set(self, key: str, val: Any, ttl: Optional[int] = None) -> None:\n"
                    f"        expires_at = time.time() + (ttl or self.default_ttl)\n"
                    f"        if key in self._store:\n"
                    f"            self._store.move_to_end(key)\n"
                    f"        elif len(self._store) >= self.capacity:\n"
                    f"            self._store.popitem(last=False)  # Evict least recently used\n"
                    f"        self._store[key] = (val, expires_at)\n"
                    f"```\n\n"
                    f"**Key Highlights:**\n"
                    f"• O(1) average lookup and eviction utilizing `OrderedDict`.\n"
                    f"• Automatic TTL expiration on retrieval.\n"
                    f"• Ready for integration into FastAPI or background async workers."
                )
            elif any(k in msg_lower for k in ["india", "location", "city", "place"]):
                reply = (
                    f"### Geographic & Infrastructure Assessment: India\n"
                    f"**Evaluated by:** Agent A (OpenAI {self.model})\n\n"
                    f"Depending on your objective, here are the top strategic locations in India:\n\n"
                    f"#### 1. Tech & Software Engineering Hubs\n"
                    f"• **Bengaluru (Bangalore):** The premier innovation and startup capital, hosting major R&D centers, AI labs, and unicorn tech stacks.\n"
                    f"• **Hyderabad:** Ultra-modern infrastructure (HITEC City), major cloud hyperscaler data centers (AWS ap-south-2, Microsoft), and enterprise engineering facilities.\n"
                    f"• **Pune:** Thriving engineering ecosystem with strong automotive tech, cloud services, and premier universities.\n\n"
                    f"#### 2. Financial & Cloud Infrastructure Hubs\n"
                    f"• **Mumbai:** The financial capital (RBI, BSE, NSE) and the primary submarine cable landing station hub for AWS ap-south-1 and cloud edge nodes.\n\n"
                    f"#### 3. Tourism & Living\n"
                    f"• **Kerala & Goa:** Renowned for coastal beauty, work-from-anywhere digital nomad hubs, and quality of life.\n"
                    f"• **Himachal & Ladakh:** Spectacular high-altitude landscapes and serene environments.\n\n"
                    f"If you are planning an infrastructure deployment, I recommend a dual-region active-active setup between Mumbai (`ap-south-1`) and Hyderabad (`ap-south-2`) for sub-15ms cross-region latency."
                )
            else:
                reply = (
                    f"### Technical Assessment: {message.splitlines()[0][:60]}\n"
                    f"**Author:** Agent A (OpenAI {self.model})\n\n"
                    f"Regarding your query: *\"{message}\"*\n\n"
                    f"#### 1. Proposed Implementation Strategy\n"
                    f"• **Architecture:** Modular, loosely-coupled microservices design with asynchronous communication.\n"
                    f"• **Reliability:** Built-in circuit breakers, automatic retries with exponential backoff and jitter.\n"
                    f"• **Observability:** Distributed tracing (OpenTelemetry) and structured JSON logging.\n\n"
                    f"#### 2. Next Steps\n"
                    f"You can prompt me for specific code implementations (Python, TypeScript, Go), or dispatch this objective through **Supervisor Agent C** so **Claude Agent B** can audit and score it against enterprise benchmarks!"
                )
            p_tokens = CostTracker.estimate_tokens_from_text(message) + 50
            c_tokens = CostTracker.estimate_tokens_from_text(reply)
            return reply, CostTracker.create_token_usage(self.model, p_tokens, c_tokens)

    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, TokenUsage]:
        return self.draft(task, context)
