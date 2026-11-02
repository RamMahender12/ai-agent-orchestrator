"""Read-only view of the public A2A Registry (a2a-registry.org): categories, agents per category, one agent's details."""
import json
import os
import threading
import time
import uuid
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, List
from urllib.parse import quote, urljoin

import httpx

from core.sites import BadUrl, _check_public, normalize

BASE = "https://api.a2a-registry.org/public/agents"
PAGE = 100  # the registry's largest page size
TTL = 600
MAX_CARD = 500_000

_cache: Dict[str, Any] = {"at": 0.0, "agents": []}
_lock = threading.Lock()


def _auth() -> Dict[str, str]:
    key = os.getenv("A2A_REGISTRY_API_KEY", "")
    return {"Authorization": f"Bearer {key}"} if key.startswith("zv_") else {}


def _page(n: int) -> Dict[str, Any]:
    r = httpx.get(BASE, params={"limit": PAGE, "page": n}, headers=_auth(), timeout=30)
    r.raise_for_status()
    return r.json()


def all_agents() -> List[Dict[str, Any]]:
    """Every listed agent; the registry has no category endpoint, so categories come from this list."""
    # ponytail: whole registry (~1.1k agents, 12 pages) cached in memory for 10 min; page through per category if it grows a lot
    with _lock:
        if time.time() - _cache["at"] < TTL and _cache["agents"]:
            return _cache["agents"]
        first = _page(1)
        pages = -(-int(first.get("total") or 0) // PAGE)
        with ThreadPoolExecutor(6) as pool:
            rest = list(pool.map(_page, range(2, pages + 1)))
        agents = [a for p in [first, *rest] for a in p.get("agents") or []]
        _cache.update(at=time.time(), agents=agents)
        return agents


def _summary(a: Dict[str, Any]) -> Dict[str, Any]:
    return {k: a.get(k) for k in ("id", "packageName", "displayName", "description", "category",
                                  "verification_level", "lastCheckStatus", "ratingAvg", "ratingCount")}


def categories() -> List[Dict[str, Any]]:
    counts = Counter((a.get("category") or "Uncategorised") for a in all_agents())
    return [{"name": c, "count": n} for c, n in counts.most_common()]


def agents_in(category: str) -> List[Dict[str, Any]]:
    rows = [_summary(a) for a in all_agents() if (a.get("category") or "Uncategorised") == category]
    return sorted(rows, key=lambda a: (a["displayName"] or "").lower())


def live_card(url: str) -> Dict[str, Any]:
    """Fetch the agent's own card from its server. Public addresses only, size capped, untrusted data."""
    url = normalize(url)
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        for _ in range(4):
            _check_public(url)
            with client.stream("GET", url, headers={"Accept": "application/json"}) as r:
                if r.is_redirect:
                    url = normalize(urljoin(url, r.headers.get("location", "")))
                    continue
                if r.status_code >= 400:
                    raise BadUrl(f"The agent answered HTTP {r.status_code}")
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > MAX_CARD:
                        raise BadUrl("The agent card is too large")
                try:
                    return json.loads(body)
                except ValueError:
                    raise BadUrl("The agent card is not valid JSON")
    raise BadUrl("Too many redirects")


def agent(agent_id: str) -> Dict[str, Any]:
    r = httpx.get(f"{BASE}/{quote(agent_id, safe='')}", headers=_auth(), timeout=20)
    if r.status_code == 404:
        raise KeyError(agent_id)
    r.raise_for_status()
    a = r.json().get("agent") or {}
    live, error = None, None
    if a.get("manifestUrl"):
        try:
            live = live_card(a["manifestUrl"])
        except (BadUrl, httpx.HTTPError) as exc:
            error = str(exc) or type(exc).__name__
    return {**a, "liveCard": live, "liveCardError": error}


def endpoint(card: Dict[str, Any]) -> str:
    """The agent's JSON-RPC address: a 1.0 card lists supportedInterfaces, a 0.x card has a top-level url."""
    for i in card.get("supportedInterfaces") or card.get("additionalInterfaces") or []:
        if isinstance(i, dict) and i.get("url") and (i.get("protocolBinding") or i.get("transport") or "JSONRPC").upper() == "JSONRPC":
            return i["url"]
    if card.get("url"):
        return card["url"]
    raise BadUrl("The agent card does not say where to send messages")


def _rpc(client: httpx.Client, url: str, method: str, message: Dict[str, Any]) -> Dict[str, Any]:
    _check_public(url)
    body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method, "params": {"message": message}}
    headers = {"Accept": "application/json", **({"A2A-Version": "1.0"} if method == "SendMessage" else {})}
    with client.stream("POST", url, json=body, headers=headers) as r:
        data = b""
        for chunk in r.iter_bytes():
            data += chunk
            if len(data) > MAX_CARD:
                raise BadUrl("The agent's reply is too large")
        if r.status_code in (401, 403):
            raise BadUrl(f"The agent needs its own API key or payment (HTTP {r.status_code})")
        try:
            return json.loads(data)
        except ValueError:
            raise BadUrl(f"The agent did not answer with JSON-RPC (HTTP {r.status_code})")


def reply_text(result: Any) -> str:
    """Pull readable text out of an A2A reply, whether it is a Message, a Task, or a 1.0 {message|task} wrapper."""
    if not isinstance(result, dict):
        return ""
    result = result.get("message") or result.get("task") or result
    parts = list(result.get("parts") or [])
    parts += ((result.get("status") or {}).get("message") or {}).get("parts") or []
    for art in result.get("artifacts") or []:
        parts += art.get("parts") or []
    texts = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        if p.get("text"):
            texts.append(str(p["text"]))
        elif p.get("data") is not None:
            texts.append(json.dumps(p["data"], ensure_ascii=False, indent=2))
    return "\n\n".join(texts)


def send(agent_id: str, text: str) -> Dict[str, Any]:
    """Send one text message to a registry agent over A2A. Its reply is untrusted data, shown, never acted on."""
    a = agent(agent_id)
    url = normalize(endpoint(a.get("liveCard") or a.get("agentCard") or {}))
    mid = uuid.uuid4().hex
    attempts = [  # 0.x first since most listed agents speak it, then 1.0
        ("message/send", {"kind": "message", "role": "user", "messageId": mid, "parts": [{"kind": "text", "text": text}]}),
        ("SendMessage", {"messageId": mid, "role": "ROLE_USER", "parts": [{"text": text}]}),
    ]
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        for method, message in attempts:
            resp = _rpc(client, url, method, message)
            if not isinstance(resp, dict):
                raise BadUrl("The agent did not answer with JSON-RPC")
            err = resp.get("error")
            if not err and "result" not in resp:
                err = {"message": str(resp.get("message") or "The agent's reply had no result")}
            if err and not isinstance(err, dict):
                err = {"message": str(err)}  # some agents send a bare string
            if err and method != attempts[-1][0]:
                continue  # agents word "wrong protocol version" differently, so any 0.x error gets a 1.0 retry
            return {"endpoint": url, "method": method, "text": "" if err else reply_text(resp.get("result")),
                    "error": err.get("message") if err else None, "raw": resp}
    raise BadUrl("The agent rejected both A2A message formats")


if __name__ == "__main__":
    assert endpoint({"supportedInterfaces": [{"url": "https://x.io/rpc", "protocolBinding": "JSONRPC"}]}) == "https://x.io/rpc"
    assert endpoint({"url": "https://y.io/a2a"}) == "https://y.io/a2a"
    assert reply_text({"kind": "task", "status": {"message": {"parts": [{"kind": "text", "text": "hi"}]}},
                       "artifacts": [{"parts": [{"data": {"n": 1}}]}]}) == 'hi\n\n{\n  "n": 1\n}'
    assert reply_text({"message": {"parts": [{"text": "v1"}]}}) == "v1"
    cats = categories()
    assert cats and sum(c["count"] for c in cats) == len(all_agents())
    first = agents_in(cats[0]["name"])
    assert first and all(a["category"] == cats[0]["name"] for a in first)
    d = agent(first[0]["packageName"])
    assert d["displayName"] == first[0]["displayName"]
    for bad in ("http://127.0.0.1/x", "http://localhost/card.json"):
        try:
            live_card(bad)
            raise AssertionError(bad)
        except BadUrl:
            pass
    print("ok", len(all_agents()), "agents,", len(cats), "categories; live card:", "yes" if d["liveCard"] else d["liveCardError"])
