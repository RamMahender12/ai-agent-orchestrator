"""Website directory: fetch a site, Agent A's model summarises and categorises it, Agent B's model reviews and scores it."""
import ipaddress
import json
import os
import socket
from html.parser import HTMLParser
from typing import Any, Dict, List, Tuple
from urllib.parse import urljoin, urlparse

import httpx

from core.cost_tracker import CostTracker
from core.llm import complete

CATEGORIES = [
    "Dev Tools", "AI", "Productivity", "Finance", "E-commerce", "Education",
    "News & Media", "Social", "Design", "Health", "Travel", "Entertainment", "Other",
]
CRITERIA = {
    "Clarity": "is it obvious what the site offers and to whom",
    "Usefulness": "real value for its audience, depth of features or content",
    "Trust": "pricing, contact details, company info, policies, social proof",
    "Quality": "content and design quality; deduct for scam signals, spam, thin or broken content",
}
MAX_BYTES = 1_000_000
MAX_TEXT = 6000


class BadUrl(ValueError):
    pass


class _Page(HTMLParser):
    """Title, meta description and visible text of an HTML page."""

    def __init__(self):
        super().__init__()
        self.title, self.description, self.parts, self._skip, self._in_title = "", "", [], 0, False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "svg"):
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta" and (a.get("name") or a.get("property") or "").lower() in ("description", "og:description"):
            self.description = self.description or (a.get("content") or "").strip()

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "svg"):
            self._skip = max(0, self._skip - 1)
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()
        elif not self._skip and data.strip():
            self.parts.append(data.strip())


def normalize(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.hostname:
        raise BadUrl("Enter a web address like example.com or https://example.com")
    return url


def _check_public(url: str):
    """Refuse addresses on this machine or its private network, so the server can't be used to read internal services."""
    host = urlparse(url).hostname
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise BadUrl(f"Could not find {host}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise BadUrl(f"{host} points to a private address")


def fetch_site(url: str) -> Dict[str, str]:
    # ponytail: DNS is checked before each request, not pinned, so a rebinding host could slip through; pin the IP if this ever takes public submissions
    url = normalize(url)
    with httpx.Client(timeout=15, follow_redirects=False, headers={"User-Agent": "Mozilla/5.0 (site-directory-bot)"}) as client:
        for _ in range(5):
            _check_public(url)
            with client.stream("GET", url) as resp:
                if resp.is_redirect:
                    url = urljoin(url, resp.headers.get("location", ""))
                    normalize(url)
                    continue
                if resp.status_code >= 400:
                    raise BadUrl(f"The site answered HTTP {resp.status_code}")
                body = b""
                for chunk in resp.iter_bytes():
                    body += chunk
                    if len(body) >= MAX_BYTES:
                        break
                page = _Page()
                page.feed(body.decode(resp.encoding or "utf-8", errors="replace"))
                return {"url": url, "title": page.title[:200], "description": page.description[:500],
                        "text": " ".join(page.parts)[:MAX_TEXT]}
    raise BadUrl("Too many redirects")


def _json(text: str) -> Dict[str, Any]:
    try:
        return json.loads(text[text.find("{"):text.rfind("}") + 1])
    except ValueError:
        return {}


def _ask(system: str, page: Dict[str, str], prefer: str) -> Tuple[Dict[str, Any], Any]:
    user = f"URL: {page['url']}\nTITLE: {page['title']}\nMETA DESCRIPTION: {page['description']}\nPAGE TEXT:\n{page['text']}"
    text, usage = complete(system, user, prefer=prefer)
    return _json(text), usage


def _breakdown(scores: Any) -> List[Dict[str, Any]]:
    """One row per criterion, each clamped to 0-25; the overall score is their sum so it always matches the reasons."""
    scores = scores if isinstance(scores, dict) else {}
    rows = []
    for c in CRITERIA:
        s = scores.get(c) if isinstance(scores.get(c), dict) else {}
        try:
            n = max(0, min(25, int(s.get("score", 0))))
        except (TypeError, ValueError):
            n = 0
        rows.append({"criterion": c, "score": n, "max": 25, "reason": str(s.get("reason") or "Not given")[:500]})
    return rows


def review_site(url: str, simulation_mode: bool = False) -> Dict[str, Any]:
    page = fetch_site(url)
    if simulation_mode:
        info = {"name": page["title"] or urlparse(page["url"]).hostname, "category": "Other",
                "summary": page["description"] or "Simulation mode: no model was called.",
                "about": "Simulation mode: no model read this page."}
        review = {"scores": {c: {"score": 17, "reason": "Simulation mode, not judged."} for c in CRITERIA},
                  "pros": ["Page loaded"], "cons": ["Not reviewed by a model (simulation)"],
                  "reasoning": "Simulation mode gives every criterion the same placeholder score.",
                  "verdict": "Simulation mode review."}
        usages = [CostTracker.create_token_usage(os.getenv("AGENT_A_MODEL", "simulation"), 0, 0)]
    else:
        info, u1 = _ask(
            "You catalogue websites. Describe only what the page content shows; never invent features or prices. Reply with JSON only: "
            '{"name": "site or product name", "category": one of ' + json.dumps(CATEGORIES) + ', '
            '"summary": "2 sentences on what the site is and who it is for", '
            '"about": "one paragraph (4-6 sentences) explaining what the site does and how people use it", '
            '"audience": "who it is for", "features": ["main features or offerings"], '
            '"pricing": "pricing model if the page shows one, else \\"Not shown\\""}',
            page, "openai")
        review, u2 = _ask(
            "You review websites for a public directory. Judge from the page content only. Score each criterion 0-25 "
            "and give a specific reason that cites what you saw (or did not see) on the page: "
            + "; ".join(f"{c}: {d}" for c, d in CRITERIA.items()) + ". "
            'Reply with JSON only: {"scores": {' + ", ".join(f'"{c}": {{"score": 0-25, "reason": "..."}}' for c in CRITERIA)
            + '}, "pros": ["..."], "cons": ["..."], '
            '"reasoning": "one paragraph explaining why the site earns this overall score", "verdict": "one sentence"}',
            page, "anthropic")
        usages = [u1, u2]
    category = info.get("category") if info.get("category") in CATEGORIES else "Other"
    breakdown = _breakdown(review.get("scores"))
    score = sum(b["score"] for b in breakdown)
    return {
        "url": page["url"],
        "name": str(info.get("name") or page["title"] or urlparse(page["url"]).hostname)[:120],
        "category": category,
        "summary": str(info.get("summary") or page["description"])[:600],
        "score": score,
        "pros": [str(p) for p in review.get("pros") or []][:6],
        "cons": [str(c) for c in review.get("cons") or []][:6],
        "verdict": str(review.get("verdict") or "")[:300],
        "brief": {
            "about": str(info.get("about") or "")[:1500],
            "audience": str(info.get("audience") or "")[:300],
            "features": [str(f)[:200] for f in info.get("features") or []][:8],
            "pricing": str(info.get("pricing") or "Not shown")[:300],
            "breakdown": breakdown,
            "reasoning": str(review.get("reasoning") or "")[:1500],
        },
        "tokens": sum(u.total_tokens for u in usages),
        "cost_usd": round(sum(u.cost_usd for u in usages), 6),
    }


if __name__ == "__main__":
    for bad in ("ftp://x.com", "http://127.0.0.1", "http://localhost:8000", "http://10.0.0.5"):
        try:
            _check_public(normalize(bad))
            raise AssertionError(f"{bad} was allowed")
        except BadUrl:
            pass
    assert normalize("example.com") == "https://example.com"
    p = _Page()
    p.feed('<html><head><title>Hi</title><meta name="description" content="Desc"><script>x()</script></head><body><p>Body text</p></body></html>')
    assert (p.title, p.description, p.parts) == ("Hi", "Desc", ["Body text"])
    assert _json('sure! {"score": 5} done') == {"score": 5}
    b = _breakdown({"Clarity": {"score": 30, "reason": "x"}, "Trust": {"score": "12"}, "Quality": "junk"})
    assert [r["score"] for r in b] == [25, 0, 12, 0] and sum(r["score"] for r in b) == 37
    print("ok")
