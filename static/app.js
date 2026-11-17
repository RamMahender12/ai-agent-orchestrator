// Dashboard for Agent C. Everything shown here is read back from the database C writes to.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const money = (n) => "$" + +(n || 0).toFixed(6);
const num = (n) => (n || 0).toLocaleString();
const when = (ts) => (ts ? new Date(ts.replace(" ", "T") + "Z").toLocaleString() : "");
const keyOf = (name) => (/Agent ([A-Z])/.exec(name || "") || [, "c"])[1].toLowerCase();

const DONE = new Set(["COMPLETED", "MAX_REVISIONS_REACHED", "FAILED"]);
const STATUS_LABEL = { COMPLETED: "Approved", MAX_REVISIONS_REACHED: "Not approved", FAILED: "Failed" };
const ROLES = { a: "Laguna", b: "Nemotron", c: "Captain" };
const C_DESCRIPTION =
  "Sends your prompt to every agent at once, scores each answer and gives that agent " +
  "recommendations, logs every step, adds up tokens and cost, and has every agent below the pass score revise.";
// A and B have friendly names; the free-model agents use the label in their name, e.g. "Agent D (Flint)"
const who = (name) => ROLES[keyOf(name)] || (/\(([^)]*)\)/.exec(name || "") || [, keyOf(name).toUpperCase()])[1];
// free-model agents from agents/agent_free.py FREE_MODELS, so their cards show before C has registered them
const FREE = { d: "Flint", e: "Xing", f: "Dots", g: "Nemotron Lightning", h: "Laguna XS", i: "Gemma", j: "North", k: "Nemotron Super", l: "Nemotron Nano", m: "Gemma Small" };
// registry agents picked for the next run take N, O, P in pick order (agents/agent_registry.py LETTERS)
const REG = "nop";
let picked = []; // [{id, name}]
const pickOf = (k) => picked[REG.indexOf(k)];
const label = (k) => ROLES[k] || pickOf(k)?.name || (agents[k] ? who(agents[k].name) : FREE[k] || k.toUpperCase());
// default model ids (core/llm.py, agents/agent_free.py) until C has registered the agent with its real one
const MODELS = {
  a: "poolside/laguna-s-2.1:free", b: "nvidia/nemotron-3-ultra-550b-a55b:free",
  d: "recursive/flint-v1.0:free", e: "xingchen-agi/xing4.0-29b-a4b:free", f: "dots-studio/dots-3-note-preview:free",
  g: "nvidia/nemotron-3.5-lightning:free", h: "poolside/laguna-xs-2.1:free", i: "google/gemma-4-31b-it:free",
  j: "cohere/north-mini-code:free", k: "nvidia/nemotron-3.5-super-vl:free",
  l: "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free", m: "google/gemma-4-26b-a4b-it:free",
};
// who made and hosts the model originally (OpenRouter only relays it)
const VENDORS = {
  nvidia: "NVIDIA cloud", poolside: "Poolside cloud", google: "Google cloud", cohere: "Cohere cloud",
  recursive: "Recursive cloud", "xingchen-agi": "Xingchen AGI cloud", "dots-studio": "Dots Studio cloud",
};
// "nvidia/nemotron-3-ultra-550b-a55b:free" -> "NVIDIA cloud v3"; the first number that isn't a size like 550b
const modelText = (id) => {
  if (!id) return "";
  if (!id.includes("/")) return "A2A Registry"; // registry agents use their package name as the model
  const [vendor, model = ""] = id.replace(/:free$/, "").split("/");
  const v = /(\d+(?:\.\d+)*)(?![\d.]*b)/.exec(model);
  return `${VENDORS[vendor] || vendor}${v ? ` v${v[1]}` : ""}`;
};
const modelOf = (k) => pickOf(k)?.id || agents[k]?.model || MODELS[k];
const title = (k) => (modelOf(k) ? `${label(k)} - ${modelText(modelOf(k))}` : label(k));
const rival = (name) => ROLES[keyOf(name) === "a" ? "b" : "a"];
const STEP_TITLE = {
  CAPABILITY_DISCOVERY: (s) => `C asked ${who(s.receiver)} what it does`,
  DRAFT_SUBMISSION: (s) => `${who(s.sender)} wrote its answer`,
  REVISED_DRAFT: (s) => `${who(s.sender)} wrote a revised answer`,
  AUDIT_VERDICT: (s) => `${who(s.sender)} scored ${rival(s.sender)}'s answer`,
  CAPTAIN_RECOMMENDATIONS: (s) => `C scored ${who(s.receiver)}'s answer and gave recommendations`,
  WINNER_SELECTED: () => "C picked the strongest answer",
  AGENT_FAILED: (s) => `${who(s.sender)} failed`,
  REVISE_DIRECTIVE: (s) => `C told ${who(s.receiver)} to do it better`,
  APPROVAL_FINALIZED: () => "C approved the result",
  TASK_DISPATCH: (s) => `C gave ${who(s.receiver)} the task`,
  AUDIT_REQUEST: (s) => `C asked ${who(s.receiver)} to score ${rival(s.receiver)}'s answer`,
};
const REPLIES = new Set(["DRAFT_SUBMISSION", "REVISED_DRAFT", "AUDIT_VERDICT", "AGENT_FAILED"]);
const date = (ts) => new Date(ts.replace(" ", "T") + "Z");
const spinner = '<span class="spinner" aria-hidden="true"></span>';
const dots = '<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>';
const SEND = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 19V5M5 12l7-7 7 7"/></svg>`;
const COPY = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>`;
const LOGO = `<svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor" aria-hidden="true"><path d="M12 2l2.2 6.3L20.5 10l-6.3 2.2L12 18.5l-2.2-6.3L3.5 10l6.3-1.7z"/><path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" opacity=".7"/></svg>`;
const SUGGEST = [
  "Implement an in-memory cache in Python with TTL expiration and LRU eviction",
  "Write a SQL query that returns each customer's three most recent orders",
  "Design a rate limiter for a public REST API and explain the trade-offs",
  "Explain the CAP theorem with a real-world example",
];
let seen = { id: null, n: 0 }; // steps already on screen, so only new ones animate in

function welcome(note) {
  $("summary").innerHTML = `<div class="welcome">
    <span class="logo lg">${LOGO}</span>
    <h1>What should the agents work on?</h1>
    <p class="muted">${note || "Captain C sends your task to every agent at once, scores each answer, has anyone below the pass score revise, and tracks tokens and cost."}</p>
    <div class="suggest">${SUGGEST.map((s) => `<button type="button" data-suggest="${esc(s)}">${esc(s)}</button>`).join("")}</div>
  </div>`;
}

let agents = {}; // what C recorded about A and B, keyed a/b
let liveId = null; // run being polled
let shownId = null;
let lastSig = "";
let liveSince = 0; // when the current live step started, for the ticking timers
let runStart = 0; // when the shown run started, for the "thinking" timer
// 3400 -> "3s", 75000 -> "1m 15s"
const dur = (ms) => {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${s % 60}s`;
};
const CHEVRON = `<svg class="chev" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>`;

setInterval(() => {
  const secs = `${Math.round((Date.now() - liveSince) / 1000)}s`;
  document.querySelectorAll(".tick").forEach((el) => (el.textContent = secs));
  document.querySelectorAll(".tick-total").forEach((el) => (el.textContent = dur(Date.now() - runStart)));
}, 1000);

function liveText(run) {
  const attempt = run.revisions_count;
  const k = workingAgent(run.status);
  if (k === "all") return attempt > 1 ? `Agents below the pass score are rewriting their answers (attempt ${attempt})` : "Every agent is writing its answer";
  if (run.status.endsWith("REVIEW_ALL")) return `Captain is reviewing every answer (attempt ${attempt})`;
  if (run.status.includes("GENERATION")) return attempt > 1 ? `${ROLES[k]} is rewriting its answer (attempt ${attempt})` : `${ROLES[k]} is writing its answer`;
  if (run.status.includes("REVIEW")) return `Captain is reviewing ${ROLES[run.status.slice(-1).toLowerCase()]}'s attempt ${attempt}`;
  if (run.status.includes("AUDIT")) return `${ROLES[k]} is scoring ${ROLES[k === "a" ? "b" : "a"]}'s attempt ${attempt}`;
  return "Captain C is sending the task to every agent";
}

async function api(path, options) {
  const res = await fetch(path, options);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `HTTP ${res.status}`);
  return body;
}

function workingAgent(status) {
  if (DONE.has(status)) return null;
  // statuses end with who is working: _GENERATION_ALL (every agent at once), _REVIEW_* (C);
  // older runs logged one agent, e.g. REVISION_1_GENERATION_B, or nothing (A wrote and B scored)
  const m = /_(GENERATION|AUDIT|REVIEW)(?:_([A-Z]+))?$/.exec(status);
  if (!m || m[1] === "REVIEW") return "c";
  if (m[2] === "ALL") return "all";
  return (m[2] || (m[1] === "AUDIT" ? "b" : "a")).toLowerCase();
}

function renderAgents(run, usage = []) {
  const working = run ? workingAgent(run.status) : null;
  const ran = new Set(usage.map((u) => keyOf(u.agent)));
  // a registry agent's card shows while it is picked, or for a run it took part in
  const keys = [...new Set(["a", "b", ...Object.keys(FREE), ...Object.keys(agents).filter((k) => !REG.includes(k)),
    ...[...REG].filter((k) => pickOf(k) || ran.has(k))].sort()), "c"];
  $("agents").innerHTML = keys.map((k) => {
    const busy = working === k || (working === "all" && k !== "c");
    const info = agents[k];
    const used = usage.find((u) => keyOf(u.agent) === k) || {};
    const about = k === "c" ? C_DESCRIPTION
      : info ? esc(info.description)
      : "Not run yet. Run a task and C will send it to this agent.";
    return `
      <article class="card agent agent-${k} ${busy ? "working" : ""}">
        <header>
          <span class="badge badge-${k}">${k.toUpperCase()}</span>
          <h3 title="${esc(modelOf(k))}">${esc(title(k))}</h3>
          <span class="state">${busy ? `${spinner} Working <span class="tick">0s</span>` : "Idle"}</span>
        </header>
        <p class="about">${about}</p>
        <dl>
          <div><dt>Steps</dt><dd>${num(used.steps)}</dd></div>
          <div><dt>Tokens</dt><dd>${num(used.total_tokens)}</dd></div>
          <div><dt>Cost</dt><dd>${money(used.cost_usd)}</dd></div>
        </dl>
      </article>`;
  }).join("");
}

// C's own messages name the agents "Agent A (...)", "Agent D (Flint)"; show them as Laguna, Flint.
// Drafts are left untouched, they are the model's own words.
const friendly = (text) => text.replace(/Agent ([ABD-Z])(?: \(([^)]*)\))?/g, (m, k, n) => ROLES[k.toLowerCase()] || n || m);

function stepBody(step) {
  const content = keyOf(step.sender) === "c" ? friendly(step.content) : step.content;
  const meta = JSON.parse(step.metadata || "{}");
  const ev = meta.evaluation;
  if (ev) {
    const list = (title, items) =>
      items?.length ? `<p class="small"><strong>${title}</strong></p><ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "";
    const cls = ev.passed ? "pass" : "fail";
    return `
      <div class="scorebar ${cls}"><span class="score ${cls}">${ev.score}/100</span><span class="bar"><i style="--w:${Math.max(0, Math.min(100, +ev.score || 0))}%"></i></span>
        <span class="muted small">${ev.passed ? "Passed" : "Below the pass score"}</span></div>
      ${list(keyOf(ev.reviewer) === "c" ? "Recommendations" : "Problems", ev.flaws)}${list("Strengths", ev.strengths)}
      <p class="small"><strong>Feedback</strong> ${esc(ev.actionable_feedback)}</p>`;
  }
  if (step.content.length > 800) {
    return `<details><summary>Show full text (${num(step.content.length)} characters)</summary><pre>${esc(content)}</pre></details>`;
  }
  return `<p class="pre">${esc(content)}</p>`;
}

function renderRun({ run, steps, evaluations, usage }) {
  const sig = `${run.run_id}|${run.status}|${steps.length}`;
  if (sig === lastSig) return; // keep opened <details> open between polls
  lastSig = sig;
  liveSince = Date.now();
  const from = seen.id === run.run_id ? seen.n : 0;
  seen = { id: run.run_id, n: steps.length };
  const sc = $("tab-main");
  const nearBottom = sc.scrollHeight - sc.scrollTop - sc.clientHeight < 200;

  renderAgents(run, usage);
  // the final output is always the best-scoring draft, so its score is the highest one logged
  const lastScore = evaluations.length ? `${Math.max(...evaluations.map((e) => e.score))}/100` : "–";
  const done = DONE.has(run.status);
  const finalStep = steps.findLast((s) => s.content === run.final_output);
  $("summary").innerHTML = `<div class="msg-user ${from ? "" : "enter"}">${esc(run.task)}</div>`;
  const start = date(run.created_at);
  runStart = start.getTime();

  // every step between C and the agents lives in the collapsed "thinking" trace
  $("timeline").innerHTML = steps.map((s, i) => {
    const k = keyOf(s.sender);
    const took = REPLIES.has(s.action) && i ? ` · took ${dur(date(s.timestamp) - date(steps[i - 1].timestamp))}` : "";
    const spent = s.tokens_total ? ` · ${num(s.tokens_total)} tokens · ${money(s.cost_usd)}` : "";
    const fresh = i >= from ? `enter" style="--d:${Math.min(i - from, 10) * 45}ms` : "";
    return `
    <li class="step step-${k} ${s.action === "REVISE_DIRECTIVE" ? "directive" : ""} ${fresh}">
      <span class="badge badge-${k}">${k.toUpperCase()}</span>
      <div class="step-main">
        <header><span class="step-title">${(STEP_TITLE[s.action] || (() => esc(s.action)))(s)}</span>
          <span class="step-time">${dur(date(s.timestamp) - start)}</span></header>
        <div class="step-body">${stepBody(s)}</div>
        <p class="meta-line">${date(s.timestamp).toLocaleTimeString()}${took}${spent}</p>
      </div>
    </li>`;
  }).join("");

  const failed = run.status === "FAILED";
  const live = !done && run.run_id === liveId;
  const agentsUsed = new Set(steps.map((s) => keyOf(s.sender))).size;
  const count = `${steps.length} step${steps.length === 1 ? "" : "s"} · ${agentsUsed} agent${agentsUsed === 1 ? "" : "s"}`;
  $("trace").hidden = false;
  $("trace").classList.toggle("running", live);
  $("trace-sum").innerHTML = live
    ? `${dots}<span class="shimmer">${liveText(run)}</span><span class="muted tick-total">${dur(Date.now() - runStart)}</span>${CHEVRON}`
    : done
      ? `<span class="trace-icon ${failed ? "bad" : ""}">${failed ? "!" : "✓"}</span><span>${failed ? "Failed after" : "Worked for"} ${dur(date(run.completed_at || run.created_at) - start)}</span>
         <span class="muted">· ${count}</span>${CHEVRON}`
      : `<span class="trace-icon bad">!</span><span>Stopped before finishing</span><span class="muted">· ${count}</span>${CHEVRON}`;

  const fk = finalStep ? keyOf(finalStep.sender) : "c";
  $("live").innerHTML = done && run.final_output ? `
    <div class="answer ${failed ? "failed" : ""}">
      <span class="badge badge-${fk}">${fk.toUpperCase()}</span>
      <div class="msg-body">
        ${failed ? `<p class="fail-note">The run failed: ${esc(run.final_output)}</p>` : `<div class="md">${md(run.final_output)}</div>`}
        <div class="answer-meta">
          ${failed ? "" : `<button type="button" class="icon-btn" data-copy aria-label="Copy answer" title="Copy">${COPY}</button>`}
          <span class="status status-${run.status}">${STATUS_LABEL[run.status]}</span>
          <span>${failed ? "" : `${finalStep ? `by ${esc(who(finalStep.sender))} · ` : ""}score ${lastScore} · `}${run.revisions_count} round${run.revisions_count === 1 ? "" : "s"} · ${num(run.total_tokens)} tokens · ${money(run.total_cost_usd)}</span>
        </div>
      </div>
    </div>` : "";

  if (!from) sc.scrollTop = 0;
  else if (nearBottom) sc.scrollTo({ top: sc.scrollHeight, behavior: "smooth" });
}

$("live").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-copy]");
  if (!btn) return;
  navigator.clipboard.writeText(btn.closest(".answer").querySelector(".md").innerText).then(() => {
    btn.classList.add("done");
    setTimeout(() => btn.classList.remove("done"), 1500);
  });
});

$("summary").addEventListener("click", (e) => {
  const s = e.target.closest("[data-suggest]");
  if (!s) return;
  $("task").value = s.dataset.suggest;
  $("task").focus();
});

function newRun() {
  showTab("main");
  if (liveId) { // a run is going: show it instead of dropping its polling
    if (shownId !== liveId) { lastSig = ""; showRun(liveId).then(loadRuns); }
    return $("task").focus();
  }
  shownId = null;
  lastSig = "";
  seen = { id: null, n: 0 };
  renderAgents(null);
  $("timeline").innerHTML = $("live").innerHTML = "";
  $("trace").hidden = true;
  welcome();
  document.querySelectorAll("#runs .selected").forEach((b) => b.classList.remove("selected"));
  $("task").focus();
}
$("new-run").addEventListener("click", newRun);

async function loadRuns() {
  const runs = await api("/api/runs");
  $("runs").innerHTML = runs.length ? runs.map((r) => `
    <li class="run-row"><button type="button" data-run="${esc(r.run_id)}" class="${r.run_id === shownId ? "selected" : ""}">
      <span class="run-task">${esc(r.task)}</span>
      <span class="muted small">${STATUS_LABEL[r.status] || "Unfinished"} · ${num(r.total_tokens)} tokens · ${money(r.total_cost_usd)} · ${when(r.created_at)}</span>
    </button><button type="button" class="danger" data-delete="${esc(r.run_id)}" data-task="${esc(r.task)}" aria-label="Delete this run" title="Delete this run">${TRASH}</button></li>`).join("") : `<li class="muted">No runs yet.</li>`;
  $("clear-runs").hidden = !runs.length;
  loadMetrics().catch(() => {});
  return runs;
}

async function loadMetrics() {
  const rows = await api(`/api/metrics?period=${$("period").value}`);
  if (!rows.length) return ($("metrics").innerHTML = `<p class="muted">No scored answers yet. Finish a run to see metrics.</p>`);
  const pct = (n) => (n == null ? "–" : `${n}%`);
  // the leader of a period has the higher average score, then more wins
  const lead = {};
  rows.forEach((r) => {
    const cur = lead[r.period];
    if (r.avg_score != null && (!cur || r.avg_score > cur.avg_score || (r.avg_score === cur.avg_score && r.wins > cur.wins))) lead[r.period] = r;
  });
  $("metrics").innerHTML = `<table>
    <thead><tr><th>Period</th><th>Agent</th><th>Avg score</th><th>Best</th><th>Pass rate</th><th>First-try pass</th>
      <th>Wins</th><th>Answers</th><th>Tokens</th><th>Cost</th></tr></thead>
    <tbody>${rows.map((r) => `<tr class="${lead[r.period] === r ? "leader" : ""}">
      <td>${esc(r.period)}</td>
      <td><span class="badge badge-${keyOf(r.agent)}"></span> ${who(r.agent)}${lead[r.period] === r ? " <strong>★ leader</strong>" : ""}</td>
      <td>${r.avg_score ?? "–"}</td><td>${r.best_score ?? "–"}</td><td>${pct(r.pass_rate)}</td><td>${pct(r.first_try_pass_rate)}</td>
      <td>${r.wins}</td><td>${r.answers_reviewed}</td><td>${num(r.tokens)}</td><td>${money(r.cost_usd)}</td>
    </tr>`).join("")}</tbody></table>`;
}

$("period").addEventListener("change", () => loadMetrics().catch(() => {}));

async function showRun(runId) {
  shownId = runId;
  let details = null;
  try {
    details = await api(`/api/runs/${runId}`);
  } catch (err) {
    if (runId !== liveId) throw err; // a just-launched run may not be in the DB yet
  }
  if (shownId !== runId) return;
  // a page reload mid-run picks the run back up; older unfinished runs are treated as dead
  if (details && !DONE.has(details.run.status) && Date.now() - date(details.run.created_at) < 600000) liveId = runId;
  if (details) renderRun(details);
  if (runId !== liveId) return;
  if (details && DONE.has(details.run.status)) {
    liveId = null;
    $("run-btn").disabled = false;
    await loadAgents();
    lastSig = "";
    renderRun(details);
    loadRuns();
  } else {
    // ponytail: 1s polling of the DB, switch to the /api/stream SSE feed if this ever feels slow
    setTimeout(() => shownId === runId && showRun(runId), 1000);
  }
}

async function loadAgents() {
  agents = {};
  // newest first; skip rows left over from older agent names
  for (const a of await api("/api/agents")) if (/Agent [ABD-Z]/.test(a.name)) agents[keyOf(a.name)] ??= a;
}

const TRASH = `<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v6M14 11v6"/></svg>`;

function ask(title, text) {
  const dialog = $("confirm");
  $("confirm-title").textContent = title;
  $("confirm-text").textContent = text;
  dialog.returnValue = "";
  dialog.showModal();
  return new Promise((resolve) => dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), { once: true }));
}

function historyError(message) {
  $("history-error").textContent = message;
  $("history-error").hidden = !message;
}

async function deleteRuns(runId, task) {
  historyError("");
  if (liveId && (!runId || runId === liveId)) return historyError("A run is still in progress. Wait for it to finish, then delete.");
  const ok = runId
    ? await ask("Delete this run?", `"${task}" and its logged steps will be removed for good.`)
    : await ask("Delete all run history?", "Every run and its logged steps will be removed for good.");
  if (!ok) return;
  try {
    await api(runId ? `/api/runs/${runId}` : "/api/runs", { method: "DELETE" });
  } catch (err) {
    return historyError(`Could not delete (${err.message}). If the app was just updated, restart the server and try again.`);
  }
  const runs = await loadRuns();
  if (runId && runId !== shownId) return;
  lastSig = "";
  if (runs.length) return showRun(runs[0].run_id).then(loadRuns);
  shownId = null;
  renderAgents(null);
  $("timeline").innerHTML = $("live").innerHTML = "";
  $("trace").hidden = true;
  welcome();
}

$("clear-runs").addEventListener("click", () => deleteRuns());

$("runs").addEventListener("click", (e) => {
  const del = e.target.closest("button[data-delete]");
  if (del) return deleteRuns(del.dataset.delete, del.dataset.task);
  const btn = e.target.closest("button[data-run]");
  if (!btn) return;
  lastSig = "";
  showTab("main");
  showRun(btn.dataset.run).then(loadRuns);
});

$("run-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("error").hidden = true;
  $("run-btn").disabled = true;
  try {
    const { run_id } = await api("/api/orchestrate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        task: $("task").value,
        simulation_mode: false,
        quality_threshold: Number($("threshold").value),
        registry_agents: picked.map((p) => p.id),
      }),
    });
    liveId = run_id;
    lastSig = "";
    seen = { id: run_id, n: 0 };
    $("summary").innerHTML = `<div class="msg-user enter">${esc($("task").value)}</div>`;
    $("task").value = "";
    $("timeline").innerHTML = "";
    liveSince = runStart = Date.now();
    $("live").innerHTML = "";
    $("trace").hidden = false;
    $("trace").classList.add("running");
    $("trace-sum").innerHTML = `${dots}<span class="shimmer">Captain is sending the task to every agent</span><span class="muted tick-total">0s</span>${CHEVRON}`;
    showRun(run_id);
  } catch (err) {
    $("error").textContent = err.message;
    $("error").hidden = false;
    $("run-btn").disabled = false;
  }
});

// Website directory
function brief(s) {
  const b = s.brief || {};
  const list = (items) => (items || []).map((i) => `<li>${esc(i)}</li>`).join("");
  return `
    <h4>What the site does</h4>
    ${b.about ? `<p class="small">${esc(b.about)}</p>` : ""}
    ${b.audience ? `<p class="small"><strong>For</strong> ${esc(b.audience)}</p>` : ""}
    ${b.features?.length ? `<p class="small"><strong>Features</strong></p><ul>${list(b.features)}</ul>` : ""}
    ${b.pricing ? `<p class="small"><strong>Pricing</strong> ${esc(b.pricing)}</p>` : ""}
    <h4>Why ${s.score}/100</h4>
    ${(b.breakdown || []).map((r) => `
      <div class="crit"><div><strong>${esc(r.criterion)}</strong><span>${r.score}/${r.max}</span></div>
        <meter min="0" max="${r.max}" value="${r.score}" aria-label="${esc(r.criterion)} score"></meter>
        <p class="small muted">${esc(r.reason)}</p></div>`).join("")}
    ${b.reasoning ? `<p class="small">${esc(b.reasoning)}</p>` : ""}
    <p class="small"><strong>Pros</strong></p><ul class="pros">${list(s.pros)}</ul>
    <p class="small"><strong>Cons</strong></p><ul class="cons">${list(s.cons)}</ul>`;
}

async function loadSites() {
  const { categories, sites } = await api(`/api/sites?category=${encodeURIComponent($("site-category").value)}`);
  const sel = $("site-category");
  if (sel.options.length === 1) sel.insertAdjacentHTML("beforeend", categories.map((c) => `<option>${esc(c)}</option>`).join(""));
  $("sites").innerHTML = sites.length ? sites.map((s) => `
    <article class="site">
      <header>
        <a href="${esc(s.url)}" target="_blank" rel="noopener noreferrer"><strong>${esc(s.name)}</strong></a>
        <span class="score ${s.score >= 70 ? "pass" : "fail"}">${s.score}/100</span>
        <button type="button" class="danger" data-site="${esc(s.url)}" aria-label="Remove ${esc(s.name)}" title="Remove">${TRASH}</button>
      </header>
      <p class="muted small">${esc(s.category)} · ${esc(new URL(s.url).hostname)} · reviewed ${when(s.reviewed_at)}</p>
      <p class="small">${esc(s.summary)}</p>
      ${s.verdict ? `<p class="small"><strong>Verdict</strong> ${esc(s.verdict)}</p>` : ""}
      <details><summary>Full brief</summary>${brief(s)}</details>
    </article>`).join("") : `<p class="muted">No sites${sel.value ? " in this category" : ""} yet. Enter a web address above.</p>`;
}

$("site-category").addEventListener("change", () => loadSites().catch(() => {}));

$("site-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("site-error").hidden = true;
  $("site-btn").disabled = true;
  $("site-btn").innerHTML = `${spinner} Reviewing…`;
  try {
    await api("/api/sites", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: $("site-url").value, simulation_mode: false }),
    });
    $("site-url").value = "";
    await loadSites();
  } catch (err) {
    $("site-error").textContent = err.message;
    $("site-error").hidden = false;
  } finally {
    $("site-btn").disabled = false;
    $("site-btn").textContent = "Review site";
  }
});

$("sites").addEventListener("click", async (e) => {
  const del = e.target.closest("button[data-site]");
  if (!del || !(await ask("Remove this site?", del.dataset.site))) return;
  await api(`/api/sites?url=${encodeURIComponent(del.dataset.site)}`, { method: "DELETE" });
  loadSites();
});

(async function init() {
  renderAgents(null);
  try {
    await loadAgents();
    loadSites().catch(() => {});
    const runs = await loadRuns();
    renderAgents(null);
    if (runs.length) showRun(runs[0].run_id).then(loadRuns);
    else welcome();
  } catch (err) {
    welcome("Can't reach the server. Start it with <code>python server.py</code> and reload.");
  }
})();

// A2A Registry tab
const reg = { cat: null, agents: [], sel: null, seq: 0, listSeq: 0 };
const href = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
const out = (u) => (href(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>` : "Not listed");
const regError = (err) => { $("reg-error").textContent = err ? err.message : ""; $("reg-error").hidden = !err; };

const TABS = ["main", "native", "registry", "metrics", "sites"];
const setNav = (open) => {
  document.body.classList.toggle("nav-open", open);
  $("nav-toggle").setAttribute("aria-expanded", String(open));
};
$("nav-toggle").addEventListener("click", () => setNav(!document.body.classList.contains("nav-open")));
$("scrim").addEventListener("click", () => setNav(false));

function showTab(name) {
  for (const t of TABS) {
    $(`tab-${t}`).hidden = t !== name;
    $(`tab-btn-${t}`).setAttribute("aria-selected", String(t === name));
  }
  setNav(false);
  if (name === "main") history.replaceState(null, "", location.pathname);
  else if (location.hash !== `#${name}`) history.replaceState(null, "", `#${name}`);
  if (name === "registry" && !$("reg-cat").options.length) loadRegistryCategories();
  if (name === "native" && !$("native-list").children.length) loadNative();
}
for (const t of TABS) $(`tab-btn-${t}`).addEventListener("click", () => showTab(t));
if (TABS.includes(location.hash.slice(1))) showTab(location.hash.slice(1));

// Native Agents tab: catalog from /api/native; messages go through the registry route, which adds the vendor key server side
const nativeKey = (a) => !a.needs_key ? `<span class="pill ok">No key needed</span>`
  : a.has_key ? `<span class="pill ok">Key loaded from .env (${esc(a.key_name)})</span>`
  : a.key_optional ? `<span class="pill">Optional key: ${esc(a.key_name)} in .env</span>`
  : `<span class="pill warn">Key missing: add ${esc(a.key_name)} to .env</span>`;
let nativeAgents = [];
const nativeThreads = {}; // agent id -> chat HTML, so filtering the list keeps conversations

// Tiny, safe markdown for chat answers: escape first, then bold, links (http/https only), bullets, headings
function md(text) {
  const inline = (t) => esc(t)
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*\w])\*([^*\s][^*]*?)\*(?![*\w])/g, "$1<em>$2</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener noreferrer">$2</a>');
  let html = "", list = null, code = null;
  const endList = () => { if (list) { html += `</${list}>`; list = null; } };
  const block = (lines) => `<pre><code>${esc(lines.join("\n"))}</code></pre>`;
  for (const line of String(text).split("\n")) {
    if (/^\s*```/.test(line)) { // fenced code block
      if (code) { html += block(code); code = null; } else { endList(); code = []; }
      continue;
    }
    if (code) { code.push(line); continue; }
    if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { endList(); html += "<hr>"; continue; }
    const item = line.match(/^\s*(?:[-*•]|(\d+)[.)])\s+(.*)/);
    if (item) {
      const tag = item[1] ? "ol" : "ul";
      if (list !== tag) { endList(); html += `<${tag}>`; list = tag; }
      html += `<li>${inline(item[2])}</li>`;
      continue;
    }
    endList();
    const h = line.match(/^(#{1,6})\s+(.*)/);
    const q = line.match(/^>\s?(.*)/);
    if (h) html += h[1].length <= 2 ? `<h3>${inline(h[2])}</h3>` : `<h4>${inline(h[2])}</h4>`;
    else if (q) html += `<blockquote>${inline(q[1])}</blockquote>`;
    else if (line.trim()) html += `<p>${inline(line)}</p>`;
  }
  endList();
  return html + (code ? block(code) : "");
}

let nativeSel = null;
const hue = (s) => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7);
const avatar = (a, cls = "") => `<span class="avatar ${cls}" style="--h:${hue(a.id)}" aria-hidden="true">${esc((a.title || "?")[0].toUpperCase())}</span>`;
const blocked = (a) => a.needs_key && !a.has_key && !a.key_optional;

function renderNativeChat() {
  const a = nativeAgents.find((x) => x.id === nativeSel);
  if (!a) return ($("native-chat").innerHTML = `<p class="empty-pane">Pick an agent to start a conversation.</p>`);
  const thread = nativeThreads[a.id] || "";
  const input = a.json_skills
    ? `<div class="composer-fields"><select name="skill" aria-label="Skill">${a.json_skills.map(([v, l]) => `<option value="${esc(v)}">${esc(l)}</option>`).join("")}</select>
       <input type="text" name="q" required maxlength="200" aria-label="Search for" placeholder="Search for…"></div>`
    : `<textarea name="text" rows="1" required maxlength="4000" aria-label="Message to ${esc(a.title)}" placeholder="Message ${esc(a.title)}…">${esc(a.example || "")}</textarea>`;
  $("native-chat").innerHTML = `
    <header class="chat-head">
      ${avatar(a)}
      <div><h2>${esc(a.title)}</h2><p class="muted small">${esc(a.tagline)}</p></div>
      <details class="about-agent"><summary>About</summary>
        <div class="about-pop">
          <div class="reg-badges"><span class="pill">A2A</span><span class="pill">From ${esc(a.source)}</span>${nativeKey(a)}</div>
          <p class="small">${esc(a.description)}</p>
          <h4>What it can do</h4>
          <div class="reg-badges">${a.skills.map((s) => `<span class="pill">${esc(s)}</span>`).join("")}</div>
          <h4>Where it comes from</h4>
          <dl>
            <dt>Made by</dt><dd>${esc(a.vendor)} · ${out(a.site)}</dd>
            <dt>Found on</dt><dd>${href(a.source_url) ? `<a href="${esc(a.source_url)}" target="_blank" rel="noopener noreferrer">${esc(a.source)}</a>` : esc(a.source)}</dd>
            <dt>API key from</dt><dd>${a.needs_key ? out(a.key_url) : "Not needed"}</dd>
            <dt>Agent card</dt><dd>${out(a.card)}</dd>
            <dt>Docs</dt><dd>${out(a.docs)}</dd>
          </dl>
        </div>
      </details>
    </header>
    <div class="chat-scroll">
      ${thread ? "" : `<div class="chat-hero">${avatar(a, "lg")}<h2>${esc(a.title)}</h2><p class="muted">${esc(a.description)}</p>
        <div class="reg-badges">${a.skills.slice(0, 6).map((s) => `<span class="pill">${esc(s)}</span>`).join("")}</div></div>`}
      <div class="chat" data-thread="${esc(a.id)}">${thread}</div>
    </div>
    <form class="composer native-send" data-agent="${esc(a.id)}">
      ${a.note ? `<p class="hint" style="margin:0 0 8px">${esc(a.note)}</p>` : ""}
      <div class="composer-box">${input}
        <div class="composer-row">${nativeKey(a)}
          <button type="submit" class="send" aria-label="Send" ${blocked(a) ? "disabled" : ""}>${SEND}</button></div>
      </div>
    </form>`;
  $("native-chat").querySelector(".chat").lastElementChild?.scrollIntoView({ block: "end" });
}

async function loadNative() {
  $("native-list").innerHTML = `<li class="muted small">${spinner} Loading…</li>`;
  try {
    nativeAgents = (await api("/api/native")).agents;
    nativeSel ??= nativeAgents[0]?.id;
    renderNativeList();
    renderNativeChat();
  } catch (err) {
    $("native-list").innerHTML = `<li class="error small">${esc(err.message)}</li>`;
  }
}

function renderNativeList() {
  const q = $("native-filter").value.trim().toLowerCase();
  const rows = nativeAgents.filter((a) => !q || [a.title, a.tagline, a.description, a.source, ...a.skills].join(" ").toLowerCase().includes(q));
  $("native-count").textContent = `${rows.length} of ${nativeAgents.length} agents`;
  $("native-list").innerHTML = rows.length ? rows.map((a, i) => `
    <li style="animation-delay:${Math.min(i, 12) * 25}ms"><button type="button" data-native="${esc(a.id)}" aria-current="${a.id === nativeSel}">
      ${avatar(a)}<span class="nl-text"><strong>${esc(a.title)}</strong><span>${esc(a.tagline)}</span></span>
      <span class="key-dot ${blocked(a) ? "warn" : ""}" title="${blocked(a) ? "API key missing" : "Ready"}"></span>
    </button></li>`).join("") : `<li class="muted small">No agents match.</li>`;
}
$("native-filter").addEventListener("input", renderNativeList);
$("native-list").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-native]");
  if (!btn) return;
  nativeSel = btn.dataset.native;
  $("native-list").querySelectorAll("button[data-native]").forEach((b) => b.setAttribute("aria-current", String(b === btn)));
  renderNativeChat();
});

// Copy a chat reply (native and registry chats)
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-copy-msg]");
  if (!btn) return;
  navigator.clipboard.writeText(btn.closest(".msg-body").querySelector(".md").innerText).then(() => {
    btn.classList.add("done");
    setTimeout(() => btn.classList.remove("done"), 1500);
  });
});

// One message round trip in a chat pane; threads[id] keeps the conversation when the pane re-renders
async function chatSend(form, { threads, ag, url, text, shown }) {
  const btn = form.querySelector("button[type=submit]");
  const thread = form.parentElement.querySelector(".chat");
  const add = (html) => {
    thread.parentElement.querySelector(".chat-hero")?.remove();
    thread.insertAdjacentHTML("beforeend", html);
    thread.lastElementChild.scrollIntoView({ behavior: "smooth", block: "end" });
    threads[ag.id] = thread.innerHTML;
  };
  const reply = (body, cls = "") => `<div class="msg agent ${cls}">${avatar(ag, "sm")}<div class="msg-body">${body}</div></div>`;
  add(`<div class="msg me">${esc(shown)}</div>`);
  const field = form.querySelector("textarea, input[name=q]");
  if (field) field.value = "";
  btn.disabled = true;
  btn.innerHTML = spinner;
  thread.insertAdjacentHTML("beforeend", reply(dots, "pending"));
  thread.lastElementChild.scrollIntoView({ behavior: "smooth", block: "end" });
  try {
    const r = await api(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    thread.querySelector(".pending")?.remove();
    add(r.error ? reply(`The agent answered with an error: ${esc(r.error)}`, "err")
      : reply(`<div class="md">${md(r.answer || r.text || "The agent sent no text.")}</div>
          <div class="msg-actions"><button type="button" class="icon-btn" data-copy-msg aria-label="Copy reply" title="Copy">${COPY}</button></div>`));
  } catch (err) {
    thread.querySelector(".pending")?.remove();
    add(reply(esc(err.message), "err"));
  } finally {
    btn.disabled = false;
    btn.innerHTML = SEND;
  }
}

$("native-chat").addEventListener("submit", (e) => {
  const form = e.target.closest("form.native-send");
  if (!form) return;
  e.preventDefault();
  const f = new FormData(form);
  const text = f.has("skill") ? JSON.stringify({ skill: f.get("skill"), q: f.get("q").trim() }) : f.get("text").trim();
  if (!text) return;
  const id = form.dataset.agent;
  chatSend(form, {
    threads: nativeThreads, text, shown: f.has("skill") ? f.get("q") : text,
    ag: nativeAgents.find((x) => x.id === id) || { id, title: "?" },
    url: `/api/native/${encodeURIComponent(id)}/message`,
  });
});

// Enter sends, Shift+Enter makes a new line, like a chat box
document.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey && !e.isComposing && e.target.matches(".composer textarea")) {
    if (e.target.form.querySelector("button[type=submit]").disabled) return e.preventDefault();
    e.preventDefault();
    e.target.form.requestSubmit();
  }
});

const regThreads = {}; // agent id -> chat HTML
const regCards = {}; // agent id -> registry entry with its live card, fetched once
const regId = (a) => a.packageName || a.id;
const regName = (a) => a.displayName || a.packageName || "Agent";

async function loadRegistryCategories() {
  regError(null);
  $("reg-agents").innerHTML = `<li class="muted small">${spinner} Loading the registry…</li>`;
  try {
    const { categories } = await api("/api/registry/categories");
    $("reg-cat").innerHTML = categories.map((c) => `<option value="${esc(c.name)}">${esc(c.name)} (${c.count})</option>`).join("");
    loadRegistryAgents();
  } catch (err) {
    $("reg-agents").innerHTML = `<li><button type="button" class="link-btn" id="reg-retry">Try again</button></li>`;
    regError(err);
  }
}

async function loadRegistryAgents() {
  reg.cat = $("reg-cat").value;
  const seq = ++reg.listSeq;
  regError(null);
  $("reg-agents").innerHTML = `<li class="muted small">${spinner} Loading…</li>`;
  try {
    const { agents } = await api(`/api/registry/agents?category=${encodeURIComponent(reg.cat)}`);
    if (seq !== reg.listSeq) return;
    reg.agents = agents;
    $("reg-filter").value = "";
    renderRegistryAgents();
    if (!reg.sel && agents.length) openRegistryAgent(regId(agents[0]));
  } catch (err) {
    if (seq === reg.listSeq) { $("reg-agents").innerHTML = ""; regError(err); }
  }
}

function renderRegistryAgents() {
  const q = $("reg-filter").value.trim().toLowerCase();
  const rows = reg.agents.filter((a) => !q || `${a.displayName} ${a.description}`.toLowerCase().includes(q));
  $("reg-count").textContent = `${rows.length} of ${reg.agents.length} agents`;
  $("reg-agents").innerHTML = rows.length ? rows.map((a, i) => {
    const id = regId(a);
    const dot = a.messageable === false ? ["off", "No A2A messages"] : a.lastCheckStatus === "ok" ? ["", "Health check OK"] : ["warn", `Health check: ${a.lastCheckStatus || "not checked"}`];
    return `<li style="animation-delay:${Math.min(i, 12) * 25}ms"><button type="button" data-agent="${esc(id)}" aria-current="${id === reg.sel}">
      ${avatar({ id, title: regName(a) })}<span class="nl-text"><strong>${esc(regName(a))}</strong><span>${esc(a.description || "")}</span></span>
      <span class="key-dot ${dot[0]}" title="${esc(dot[1])}"></span></button></li>`;
  }).join("") : `<li class="muted small">No agents match.</li>`;
}

$("reg-cat").addEventListener("change", loadRegistryAgents);
$("reg-filter").addEventListener("input", renderRegistryAgents);
$("reg-agents").addEventListener("click", (e) => {
  if (e.target.closest("#reg-retry")) return loadRegistryCategories();
  const btn = e.target.closest("button[data-agent]");
  if (btn) openRegistryAgent(btn.dataset.agent);
});

async function openRegistryAgent(id) {
  reg.sel = id;
  $("reg-agents").querySelectorAll("button[data-agent]").forEach((b) => b.setAttribute("aria-current", String(b.dataset.agent === id)));
  if (regCards[id]) return renderRegistryChat(regCards[id]);
  const listed = reg.agents.find((a) => regId(a) === id) || { id };
  renderRegistryChat({ ...listed, loading: true });
  const seq = ++reg.seq;
  regError(null);
  try {
    const a = await api(`/api/registry/agents/${encodeURIComponent(id)}`);
    regCards[id] = a;
    if (seq === reg.seq) renderRegistryChat(a);
  } catch (err) {
    if (seq === reg.seq) { regError(err); renderRegistryChat(listed); }
  }
}

function registryAbout(a) {
  const card = a.liveCard || a.agentCard || {};
  const skills = Array.isArray(card.skills) ? card.skills : [];
  const endpoints = [card.url, ...(card.supportedInterfaces || card.additionalInterfaces || []).map((i) => i && i.url)].filter(href);
  const org = a.organization || {};
  const rating = a.ratingCount ? `${(+a.ratingAvg).toFixed(1)} from ${a.ratingCount}` : "No ratings yet";
  const created = a.createdAt ? new Date(a.createdAt > 1e12 ? a.createdAt : a.createdAt * 1000).toLocaleDateString() : "";
  return `
    <div class="reg-badges">
      <span class="pill">${esc(a.category || "Uncategorised")}</span>
      ${a.verification_level ? `<span class="pill">${esc(a.verification_level)}</span>` : ""}
      <span class="pill ${a.lastCheckStatus === "ok" ? "ok" : "warn"}">Health check: ${esc(a.lastCheckStatus || "not checked")}</span>
    </div>
    <p class="small">${esc(a.description)}</p>
    <dl>
      <dt>Organisation</dt><dd>${esc(org.name || a.owner_org || "Not listed")}${href(org.website) ? ` · ${out(org.website)}` : ""}</dd>
      <dt>Audience</dt><dd>${esc(a.targetAudience || "Not stated")}</dd>
      <dt>Package</dt><dd><code>${esc(a.packageName)}</code></dd>
      <dt>Agent card</dt><dd>${out(a.manifestUrl)}</dd>
      <dt>API</dt><dd>${out(a.openapiUrl)}</dd>
      ${endpoints.length ? `<dt>Endpoints</dt><dd>${endpoints.map(out).join("<br>")}</dd>` : ""}
      <dt>Version</dt><dd>${esc(card.version || "Not stated")}</dd>
      <dt>Rating</dt><dd>${esc(rating)}</dd>
      ${created ? `<dt>Listed</dt><dd>${esc(created)}</dd>` : ""}
    </dl>
    <h4>Skills (${skills.length})</h4>
    ${skills.length ? `<div class="skill-list">${skills.map((s) => `
      <div class="skill"><strong class="small">${esc(s.name || s.id)}</strong>
        ${s.description ? `<span class="small muted">${esc(s.description)}</span>` : ""}</div>`).join("")}</div>`
      : `<p class="muted small">The agent card lists no skills.</p>`}
    <p class="small muted">${a.liveCard ? "Card fetched live from the agent's own server." :
      `Could not fetch the card live (${esc(a.liveCardError || "no card address")}), so this is the registry's copy.`}</p>`;
}

function renderRegistryChat(a) {
  const id = regId(a);
  const name = regName(a);
  const ag = { id, title: name };
  const card = a.liveCard || a.agentCard || {};
  const skills = Array.isArray(card.skills) ? card.skills : [];
  const thread = regThreads[id] || "";
  const closed = a.messageable === false;
  $("reg-chat").innerHTML = `
    <header class="chat-head">
      ${avatar(ag)}
      <div><h2>${esc(name)}</h2><p class="muted small">${esc(a.category || reg.cat || "")}${a.lastCheckStatus ? ` · health ${esc(a.lastCheckStatus)}` : ""}</p></div>
      <div class="head-actions">
        ${a.loading ? `<span class="muted small">${spinner} Fetching card…</span>` : `
          ${closed ? "" : pickButton(id, name)}
          <details class="about-agent"><summary>About</summary><div class="about-pop">${registryAbout(a)}</div></details>`}
      </div>
    </header>
    <div class="chat-scroll">
      ${thread ? "" : `<div class="chat-hero">${avatar(ag, "lg")}<h2>${esc(name)}</h2><p class="muted">${esc(a.description || "")}</p>
        <div class="reg-badges">${skills.slice(0, 6).map((s) => `<span class="pill">${esc(s.name || s.id)}</span>`).join("")}</div></div>`}
      <div class="chat">${thread}</div>
    </div>
    ${closed ? `<p class="hint closed-note">This agent doesn't take A2A messages: its card lists only other ways in.
        ${card.documentationUrl ? `See how to use it: ${out(card.documentationUrl)}` : ""}</p>` : `
    <form class="composer reg-chat-send" data-agent="${esc(id)}">
      <div class="composer-box">
        <textarea name="text" rows="1" required maxlength="4000" aria-label="Message to ${esc(name)}"
          placeholder="${esc(skills[0]?.examples?.[0] || `Message ${name}…`)}"></textarea>
        <div class="composer-row"><span class="pill">A2A</span>
          <button type="submit" class="send" aria-label="Send" ${a.loading ? "disabled" : ""}>${SEND}</button></div>
      </div>
    </form>`}`;
  $("reg-chat").querySelector(".chat").lastElementChild?.scrollIntoView({ block: "end" });
}

$("reg-chat").addEventListener("submit", (e) => {
  const form = e.target.closest("form.reg-chat-send");
  if (!form) return;
  e.preventDefault();
  const text = new FormData(form).get("text").trim();
  if (!text) return;
  const id = form.dataset.agent;
  chatSend(form, {
    threads: regThreads, text, shown: text,
    ag: { id, title: regName(regCards[id] || reg.agents.find((a) => regId(a) === id) || {}) },
    url: `/api/registry/agents/${encodeURIComponent(id)}/message`,
  });
});

// Registry agents picked to answer alongside our agents in the next run
function pickButton(id, name) {
  const on = picked.some((p) => p.id === id);
  const full = !on && picked.length >= REG.length;
  return `<button type="button" class="reg-pick ${on ? "ghost" : ""}" data-pick="${esc(id)}" data-name="${esc(name)}" ${full ? "disabled" : ""}>
    ${on ? "Remove from the next run" : full ? `Next run is full (${REG.length} registry agents)` : "Add to the next run"}</button>`;
}

function setPicked(next) {
  picked = next;
  $("picked").hidden = !picked.length;
  $("picked").innerHTML = picked.length ? `<span class="small muted">Registry agents in this run:</span>` + picked.map((p, i) =>
    `<button type="button" data-unpick="${esc(p.id)}" aria-label="Remove ${esc(p.name)} from this run" title="Remove from this run">
      <span class="badge badge-${REG[i]}">${REG[i].toUpperCase()}</span> ${esc(p.name)} ×</button>`).join("") : "";
  const btn = $("reg-chat").querySelector("button[data-pick]");
  if (btn) btn.outerHTML = pickButton(btn.dataset.pick, btn.dataset.name);
  lastSig = ""; // a live run re-renders on its next poll
  if (!shownId) renderAgents(null); else if (shownId !== liveId) showRun(shownId).catch(() => {});
}

$("reg-chat").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-pick]");
  if (!btn) return;
  const id = btn.dataset.pick;
  setPicked(picked.some((p) => p.id === id) ? picked.filter((p) => p.id !== id) : [...picked, { id, name: btn.dataset.name }]);
});
$("picked").addEventListener("click", (e) => {
  const btn = e.target.closest("button[data-unpick]");
  if (btn) setPicked(picked.filter((p) => p.id !== btn.dataset.unpick));
});
