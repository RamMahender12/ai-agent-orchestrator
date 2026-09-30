from typing import Dict, Tuple
from core.models import TokenUsage

# Pricing per 1,000,000 tokens (USD)
# Standard official rates
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    # OpenAI Models
    "gpt-4o": {
        "input_per_million": 2.50,
        "output_per_million": 10.00
    },
    "gpt-4o-mini": {
        "input_per_million": 0.15,
        "output_per_million": 0.60
    },
    "gpt-4-turbo": {
        "input_per_million": 10.00,
        "output_per_million": 30.00
    },
    # Anthropic Models
    "claude-3-5-sonnet-20241022": {
        "input_per_million": 3.00,
        "output_per_million": 15.00
    },
    "claude-3-haiku-20240307": {
        "input_per_million": 0.25,
        "output_per_million": 1.25
    },
    "claude-3-opus-20240229": {
        "input_per_million": 15.00,
        "output_per_million": 75.00
    },
    # Supervisor Internal Meta Model
    "supervisor-engine": {
        "input_per_million": 1.00,
        "output_per_million": 2.00
    },
    "default": {
        "input_per_million": 1.50,
        "output_per_million": 5.00
    }
}

class CostTracker:
    @staticmethod
    def calculate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Calculate total USD cost given a model and token usage."""
        # Find matching model key
        pricing = MODEL_PRICING.get("default")
        for key, price_dict in MODEL_PRICING.items():
            if key in model.lower() or model.lower() in key:
                pricing = price_dict
                break

        input_cost = (prompt_tokens / 1_000_000.0) * pricing["input_per_million"]
        output_cost = (completion_tokens / 1_000_000.0) * pricing["output_per_million"]
        return round(input_cost + output_cost, 6)

    @staticmethod
    def create_token_usage(model: str, prompt_tokens: int, completion_tokens: int) -> TokenUsage:
        """Create TokenUsage object with computed cost."""
        total = prompt_tokens + completion_tokens
        cost = CostTracker.calculate_cost(model, prompt_tokens, completion_tokens)
        return TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total,
            cost_usd=cost
        )

    @staticmethod
    def estimate_tokens_from_text(text: str) -> int:
        """Heuristic token estimation: ~4 chars per token for English."""
        if not text:
            return 0
        return max(1, len(text) // 4)
