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

from core import native
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


def speaks_jsonrpc(card: Any, protocol: str = "a2a") -> bool:
    """False when the card declares only other transports (HTTP+JSON, MCP...). No transport stated = A2A default, JSON-RPC."""
    if isinstance(card, str):
        try:
            card = json.loads(card)
        except ValueError:
            card = {}
    if (protocol or "a2a") != "a2a":
        return False
    if not isinstance(card, dict):
        return True
    lst = lambda x: x if isinstance(x, list) else []
    kinds = {str(i.get("transport") or i.get("protocolBinding") or "").upper()
             for i in lst(card.get("supportedInterfaces")) + lst(card.get("additionalInterfaces")) if isinstance(i, dict)}
    kinds.discard("")
    preferred = str(card.get("preferredTransport") or "").upper()
    if preferred:
        return preferred == "JSONRPC" or "JSONRPC" in kinds
    return not kinds or "JSONRPC" in kinds


def _summary(a: Dict[str, Any]) -> Dict[str, Any]:
    row = {k: a.get(k) for k in ("id", "packageName", "displayName", "description", "category",
                                 "verification_level", "lastCheckStatus", "ratingAvg", "ratingCount")}
    return {**row, "messageable": speaks_jsonrpc(a.get("source_agent_card"), a.get("protocolStd"))}


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
    return {**a, "liveCard": live, "liveCardError": error,
            "messageable": speaks_jsonrpc(live or a.get("agentCard"), a.get("protocolStd"))}


def endpoint(card: Dict[str, Any]) -> str:
    """The agent's JSON-RPC address: a 1.0 card lists supportedInterfaces, a 0.x card has a top-level url."""
    for i in card.get("supportedInterfaces") or card.get("additionalInterfaces") or []:
        if isinstance(i, dict) and i.get("url") and (i.get("protocolBinding") or i.get("transport") or "JSONRPC").upper() == "JSONRPC":
            return i["url"]
    if card.get("url"):
        return card["url"]
    raise BadUrl("The agent card does not say where to send messages")


def _rpc(client: httpx.Client, url: str, method: str, message: Dict[str, Any], auth: Dict[str, str] = None) -> Dict[str, Any]:
    _check_public(url)
    body = {"jsonrpc": "2.0", "id": uuid.uuid4().hex, "method": method, "params": {"message": message}}
    headers = {"Accept": "application/json", **({"A2A-Version": "1.0"} if method == "SendMessage" else {}), **(auth or {})}
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
            texts.append(_shorten_text(str(p["text"])))
        elif p.get("data") is not None:
            texts.append(_short(p["data"]))
    return "\n\n".join(texts)


_NAME = ("name", "title", "displayName", "agent_id", "id")
_INFO = ("description", "summary", "provider_type", "type", "category")
_LINK = ("url", "link", "href", "pricing_url")


def _pick(d: Dict[str, Any], keys) -> str:
    return next((str(d[k]).strip() for k in keys if d.get(k) not in (None, "", [], {})), "")


def _short(v: Any) -> str:
    """One short line per item instead of a JSON dump. The UI's Raw reply keeps the full JSON."""
    if isinstance(v, list):
        items = [x for x in v if isinstance(x, dict)]
        if not items:
            return ", ".join(map(str, v))
        return "\n".join(f"{i}. " + " - ".join(s for s in (_pick(x, _NAME) or "item", _pick(x, _INFO)[:120], _pick(x, _LINK)) if s)
                         for i, x in enumerate(items, 1))
    if not isinstance(v, dict):
        return str(v)
    lists = [(k, x) for k, x in v.items() if isinstance(x, list) and any(isinstance(i, dict) for i in x)]
    if lists:  # e.g. {"results": [...]}: the list is the answer
        return "\n".join(_short(x) if len(lists) == 1 else f"{k}:\n{_short(x)}" for k, x in lists)
    if _pick(v, _NAME):
        return _short([v])
    flat = [f"{k}: {x}" for k, x in v.items() if x not in (None, "", [], {}) and not isinstance(x, (dict, list))]
    return "; ".join(flat) or json.dumps(v, ensure_ascii=False)


def _shorten_text(text: str) -> str:
    """Agents often put a JSON blob inside a text part: keep the sentence, shorten the blob."""
    i = text.find("{")
    if i < 0:
        return text
    try:
        obj, end = json.JSONDecoder().raw_decode(text, i)
    except ValueError:
        return text
    return "\n\n".join(s for s in (text[:i].strip(), _short(obj), text[end:].strip()) if s)


def _json_object(text: str) -> Dict[str, Any]:
    try:
        v = json.loads(text)
    except ValueError:
        return {}
    return v if isinstance(v, dict) else {}


def _not_a2a(card: Dict[str, Any]) -> str:
    """Many listed agents expose a plain HTTP API and only use the card as a listing; say that instead of 'no result'."""
    kinds = sorted({str(i.get("transport") or i.get("protocolBinding")) for i in
                    (card.get("supportedInterfaces") or card.get("additionalInterfaces") or [])
                    if isinstance(i, dict) and (i.get("transport") or i.get("protocolBinding"))})
    docs = card.get("documentationUrl")
    return ("This agent does not answer A2A JSON-RPC messages"
            + (f"; its card lists {', '.join(kinds)}" if kinds else "")
            + (f". See how to use it: {docs}" if docs else "."))


def send(agent_id: str, text: str) -> Dict[str, Any]:
    """Send one text message to a registry agent (or a native agent reached by its own card) over A2A. Reply is untrusted data."""
    card_url = native.direct_card(agent_id)  # agents listed elsewhere (a2alist.ai) are reached straight from their card
    if card_url:
        card = live_card(card_url)
    else:
        a = agent(agent_id)
        card = a.get("liveCard") or a.get("agentCard") or {}
    url = normalize(endpoint(card))
    auth = native.headers(agent_id, url)  # vendor-issued key for native agents, only to the vendor's own host
    mid = uuid.uuid4().hex
    data = _json_object(text)  # a JSON object goes as a data part: many agents take {"skill": ..., ...} requests
    attempts = [  # 0.x first since most listed agents speak it, then 1.0
        ("message/send", {"kind": "message", "role": "user", "messageId": mid,
                          "parts": [{"kind": "data", "data": data} if data else {"kind": "text", "text": text}]}),
        ("SendMessage", {"messageId": mid, "role": "ROLE_USER",
                         "parts": [{"data": data, "mediaType": "application/json"} if data else {"text": text}]}),
    ]
    with httpx.Client(timeout=60, follow_redirects=False) as client:
        for method, message in attempts:
            resp = _rpc(client, url, method, message, auth)
            if not isinstance(resp, dict):
                raise BadUrl("The agent did not answer with JSON-RPC")
            err = resp.get("error")
            if not err and "result" not in resp:
                err = {"message": str(resp.get("message") or "The agent's reply had no result") if "jsonrpc" in resp else _not_a2a(card)}
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
                       "artifacts": [{"parts": [{"data": {"n": 1}}]}]}) == 'hi\n\nn: 1'
    assert _shorten_text('1 found.\n{"results": [{"name": "P", "provider_type": "mcp", "url": " https://h.in"}]}') \
        == "1 found.\n\n1. P - mcp - https://h.in"
    assert speaks_jsonrpc({}) and speaks_jsonrpc('{"preferredTransport": "JSONRPC"}')
    assert not speaks_jsonrpc({"additionalInterfaces": [{"transport": "HTTP+JSON"}]})
    assert speaks_jsonrpc({"additionalInterfaces": [{"transport": "HTTP+JSON"}, {"transport": "JSONRPC"}]})
    assert not speaks_jsonrpc({"preferredTransport": "HTTP+JSON"}) and not speaks_jsonrpc({}, "mcp")
    assert _not_a2a({"additionalInterfaces": [{"url": "u", "transport": "HTTP+JSON"}], "documentationUrl": "d"}) \
        == "This agent does not answer A2A JSON-RPC messages; its card lists HTTP+JSON. See how to use it: d"
    assert _json_object('{"skill": "x"}') == {"skill": "x"} and _json_object("hi") == {} and _json_object("[1]") == {}
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
