"""One chat call. OpenCode Zen first, then OpenAI, then Anthropic."""
import os
from typing import Dict, List, Optional, Tuple

from core.cost_tracker import CostTracker
from core.models import TokenUsage

ZEN_URL = "https://opencode.ai/zen/v1"
ROUTER_URL = "https://openrouter.ai/api/v1"
LAGUNA = "poolside/laguna-s-2.1:free"
NEMOTRON = "nvidia/nemotron-3-ultra-550b-a55b:free"
_LEGACY = {
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo",
    "claude-3-5-sonnet-20241022", "claude-3-haiku-20240307", "claude-3-opus-20240229",
    "mimo-v2.6-flash-free", "nemotron-3-ultra-free",
}

HELP = (
    "No model answered this prompt. Add OPENROUTER_API_KEY to the .env file, "
    "leave Simulation Mode off, and send the prompt again."
)

_PLACEHOLDERS = {"", "your_openai_api_key_here", "your_anthropic_api_key_here"}


class NoApiKey(RuntimeError):
    pass


def _key(name: str) -> str:
    val = os.getenv(name, "").strip()
    if val.lower() in _PLACEHOLDERS or val.lower().startswith("your_"):
        return ""
    return val


def has_api_key() -> bool:
    return bool(_key("OPENROUTER_API_KEY") or _key("OPENCODE_API_KEY") or _key("OPENAI_API_KEY") or _key("ANTHROPIC_API_KEY"))


def _messages(system: str, user: str, history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    messages = [{"role": "system", "content": system}]
    for turn in history:
        messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})
    messages.append({"role": "user", "content": user})
    return messages


def _chat(api_key: str, base_url: Optional[str], model: str, messages: List[Dict[str, str]]) -> Tuple[str, TokenUsage]:
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
    
    # Model candidates in priority order
    candidates = [model]
    if base_url and "openrouter.ai" in base_url:
        for alt in [
            "nvidia/nemotron-3-ultra-550b-a55b:free",
            "poolside/laguna-s-2.1:free",
            "nvidia/nemotron-3.5-lightning:free",
            "poolside/laguna-xs-2.1:free",
        ]:
            if alt not in candidates:
                candidates.append(alt)

    last_exc = None
    for cand in candidates:
        try:
            resp = client.chat.completions.create(model=cand, messages=messages, temperature=0.7)
            if not getattr(resp, "choices", None) or not len(resp.choices):
                continue
            text = resp.choices[0].message.content or ""
            if not text.strip():
                continue
            usage = resp.usage
            return text, CostTracker.create_token_usage(
                cand,
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
            )
        except Exception as exc:
            last_exc = exc
            text = str(exc)
            if "FreeTierError" in text or "free tier" in text.lower():
                raise RuntimeError(
                    "MiMo V2.6 and Nemotron 3 Ultra are free only inside the OpenCode app. "
                    "This key cannot call them from this project. Add credits and pick a paid OpenCode model, "
                    "or tell me which paid model to use for A and B."
                ) from exc
            # If rate-limited upstream or server error, continue to next candidate
            continue

    if last_exc:
        raise last_exc
    raise RuntimeError(f"All model endpoints failed to return a response for: {model}")


def _pick_model(prefer: str, model: Optional[str]) -> str:
    if model and model not in _LEGACY:
        return model
    if prefer == "anthropic":
        return os.getenv("AGENT_B_MODEL", NEMOTRON)
    return os.getenv("AGENT_A_MODEL", LAGUNA)


def complete(
    system: str,
    user: str,
    history: Optional[List[Dict[str, str]]] = None,
    prefer: str = "openai",
    model: Optional[str] = None,
) -> Tuple[str, TokenUsage]:
    history = history or []
    messages = _messages(system, user, history)
    rkey = _key("OPENROUTER_API_KEY")
    if rkey:
        return _chat(rkey, os.getenv("OPENROUTER_BASE_URL", ROUTER_URL), _pick_model(prefer, model), messages)

    zkey = _key("OPENCODE_API_KEY")
    if zkey:
        return _chat(zkey, os.getenv("OPENCODE_BASE_URL", ZEN_URL), _pick_model(prefer, model), messages)

    okey = _key("OPENAI_API_KEY")
    if okey and prefer != "anthropic":
        return _chat(okey, None, model or os.getenv("AGENT_A_MODEL", "gpt-4o-mini"), messages)
    akey = _key("ANTHROPIC_API_KEY")
    if akey:
        import anthropic
        use_model = model or os.getenv("AGENT_B_MODEL", "claude-3-5-sonnet-20241022")
        resp = anthropic.Anthropic(api_key=akey).messages.create(
            model=use_model, max_tokens=2000, system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text if resp.content else ""
        return text, CostTracker.create_token_usage(use_model, resp.usage.input_tokens, resp.usage.output_tokens)
    if okey:
        return _chat(okey, None, model or os.getenv("AGENT_A_MODEL", "gpt-4o-mini"), messages)
    raise NoApiKey(HELP)
