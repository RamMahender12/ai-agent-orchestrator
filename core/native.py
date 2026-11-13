"""Native agents: hand-picked A2A agents we talk to directly. Found on a registry, keyed (if at all) by the vendor's own site."""
import os
from urllib.parse import urlparse
from typing import Any, Dict, List

from core.native_a2alist import A2ALIST

# ponytail: catalog lives in code; move to the database when non-developers need to add agents
NATIVE: List[Dict[str, Any]] = [
    {
        "id": "com.andru_ai.andru",  # a2a-registry.org package name; registry.send resolves the endpoint from it
        "title": "Andru",
        "tagline": "Enterprise buyer specialist for complex B2B deals",
        "description": "Knows your buyers and scores deals: ICP qualification, buyer personas, buying-committee maps, "
                       "deal-health red flags, meeting prep, investor and market signals, and 139 generated sales assets "
                       "(email sequences, board decks and more).",
        "vendor": "Andru (H&S)", "site": "https://andru-ai.com", "docs": "https://andru-ai.com/docs/a2a",
        "card": "https://api.andru-ai.com/.well-known/agent-card.json",
        "source": "a2a-registry.org (verified)", "source_url": "https://www.a2a-registry.org/",
        "key_env": "ANDRU_API_KEY", "key_header": "X-API-Key",
        "key_url": "https://platform.andru-ai.com/settings/developer",
        "skills": ["ICP & buyer personas", "Tech-to-value messaging", "Buying committee navigation",
                   "Deal health & red flags", "Meeting prep", "Investor intelligence", "Market intelligence"],
        "example": "Website: example.com. Vertical: car insurance. Target role: VP of Claims. Product: software that automates "
                   "garage repair claims. Give me the buyer persona and my ICP fit score.",
        "note": "On a first call it asks for your product context (website, vertical, target role, product); "
                "include those in your message and it remembers them for later calls.",
    },
    {
        "id": "spot.piknik.piknikspot",
        "title": "Piknik.Spot",
        "tagline": "Local food places, listings, events and jobs",
        "description": "Finds local farms, bakeries, markets, shops and restaurants by name, place or product, plus "
                       "surplus / wanted / for-sale listings, public events, jobs, volunteer posts and professional "
                       "profiles. Please cite Piknik and link each place it returns.",
        "vendor": "Piknik.Spot", "site": "https://piknik.spot", "docs": "https://piknik.spot/llms.txt",
        "card": "https://piknik.spot/.well-known/agent-card.json",
        "source": "a2a-registry.org (verified) and a2alist.ai", "source_url": "https://www.a2a-registry.org/",
        "key_env": None, "key_header": None, "key_url": "https://piknik.spot",  # reads need no key
        "skills": ["Local food places", "Marketplace listings", "Events", "Jobs & volunteering", "Professionals"],
        "json_skills": [  # it takes {"skill", "q"} requests, not free text
            ["search-local-food-places", "Local food places (try: bakery Waterloo)"],
            ["search-marketplace-listings", "Marketplace listings (try: tomatoes)"],
            ["search-events", "Events (try: Waterloo)"],
            ["search-jobs", "Jobs and volunteering (try: farm)"],
            ["search-professionals", "Professionals (try: Elmira)"],
        ],
    },
    {
        "id": "ai.foodbe.foodbe",
        "title": "Foodbe",
        "tagline": "Cited food facts, grocery list analysis, recipes and meal plans",
        "description": "Built on thousands of hand-curated facts about food science, food culture and cooking technique; "
                       "every answer comes with its sources and the same input always gives the same output. Analyses "
                       "grocery lists (health, carbon and water, food groups, diets, swaps), answers food questions, and "
                       "builds grocery lists, meal plans and recipes. If no approved answer exists it says \"refused\" "
                       "instead of guessing.",
        "vendor": "Foodbe", "site": "https://www.foodbe.ai", "docs": "https://www.foodbe.ai/developers/docs",
        "card": "https://www.foodbe.ai/.well-known/agent-card.json",
        "source": "a2a-registry.org (verified)", "source_url": "https://www.a2a-registry.org/",
        "key_env": "FOODBE_API_KEY", "key_header": "x-foodbe-key", "key_url": "https://www.foodbe.ai/developers",
        "key_hosts": ["foodbe-v3-production.up.railway.app"],  # its card points the A2A endpoint here, not at foodbe.ai
        "skills": ["Grocery list report", "Food Q&A with sources", "Ingredient profile", "Recipe finder",
                   "Meal plan", "Grocery list"],
        "example": "Why does salt make caramel taste better?",
    },
    {
        "id": "uk.co.algovoi.algovoi_payment_agent",
        "title": "AlgoVoi Payment Agent",
        "tagline": "Crypto payment verification and hosted checkout links",
        "description": "Verifies on-chain payments on Algorand, VOI, Hedera, Stellar, Base, Solana, Tempo and ARC, and "
                       "gates access to resources with x402, MPP (IETF) or AP2 (Google Agentic Payments). Also creates "
                       "hosted checkout links for an amount and checks whether they have been paid.",
        "vendor": "AlgoVoi", "site": "https://algovoi.co.uk", "docs": "https://api.algovoi.co.uk/.well-known/agent-card.json",
        "card": "https://api.algovoi.co.uk/.well-known/agent-card.json",
        "source": "a2a-registry.org (verified)", "source_url": "https://www.a2a-registry.org/",
        "key_env": "ALGOVOI_API_KEY", "key_header": "Authorization", "key_prefix": "Bearer ",
        "key_url": "https://api.algovoi.co.uk/signup",
        "skills": ["Verify on-chain payment", "Create hosted checkout", "Check payment status", "Post checkout to X",
                   "Agent Trust Bench"],
        "example": "Create a checkout link for £9.99 (amount: 9.99, currency: GBP)",
        "note": "Creating a checkout makes a real payment link on your AlgoVoi account.",
    },
]
NATIVE += A2ALIST
_BY_ID = {a["id"]: a for a in NATIVE}


def _key(a: Dict[str, Any]) -> str:
    return os.getenv(a["key_env"], "").strip() if a.get("key_env") else ""


def direct_card(agent_id: str) -> str:
    """Card URL for catalog agents that are not on a2a-registry.org; empty for registry agents."""
    a = _BY_ID.get(agent_id)
    return a["card"] if a and a.get("direct") else ""


def headers(agent_id: str, url: str) -> Dict[str, str]:
    """Auth header for a native agent, from .env, only when url is on the vendor's own domain (a swapped card can't steal it)."""
    a = _BY_ID.get(agent_id)
    key = _key(a) if a else ""
    host = urlparse(url).hostname or ""
    domain = urlparse(a["site"]).hostname.removeprefix("www.") if a else ""
    ok = host == domain or host.endswith("." + domain) or host in (a or {}).get("key_hosts", [])
    return {a["key_header"]: a.get("key_prefix", "") + key} if key and ok else {}


def public() -> List[Dict[str, Any]]:
    """Catalog for the UI: says whether a key is loaded, never the key itself."""
    return [{**{k: v for k, v in a.items() if k != "key_env"},
             "needs_key": bool(a.get("key_env")), "has_key": bool(_key(a)), "key_name": a.get("key_env")} for a in NATIVE]


if __name__ == "__main__":
    os.environ["ANDRU_API_KEY"] = "sk_test"
    assert headers("com.andru_ai.andru", "https://api.andru-ai.com/api/a2a/tasks") == {"X-API-Key": "sk_test"}
    assert headers("com.andru_ai.andru", "https://evil.com/andru-ai.com") == {}
    assert headers("com.andru_ai.andru", "https://notandru-ai.com/x") == {}
    assert headers("spot.piknik.piknikspot", "https://piknik.spot/api/a2a") == {} and headers("nope", "https://x.io") == {}
    os.environ["FOODBE_API_KEY"] = os.environ["ALGOVOI_API_KEY"] = "sk_test"
    assert headers("ai.foodbe.foodbe", "https://foodbe-v3-production.up.railway.app/v1/a2a") == {"x-foodbe-key": "sk_test"}
    assert headers("ai.foodbe.foodbe", "https://other.up.railway.app/v1/a2a") == {}
    assert headers("uk.co.algovoi.algovoi_payment_agent", "https://api.algovoi.co.uk/a2a/jsonrpc") == {"Authorization": "Bearer sk_test"}
    assert all("sk_test" not in str(a) for a in public())
    print("ok")
