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
const label = (k) => ROLES[k] || (agents[k] ? who(agents[k].name) : FREE[k] || k.toUpperCase());
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
  const [vendor, model = ""] = id.replace(/:free$/, "").split("/");
  const v = /(\d+(?:\.\d+)*)(?![\d.]*b)/.exec(model);
  return `${VENDORS[vendor] || vendor}${v ? ` v${v[1]}` : ""}`;
};
const modelOf = (k) => agents[k]?.model || MODELS[k];
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

let agents = {}; // what C recorded about A and B, keyed a/b
let liveId = null; // run being polled
let shownId = null;
let lastSig = "";
let liveSince = 0; // when the current live step started, for the ticking timers

setInterval(() => {
  const secs = `${Math.round((Date.now() - liveSince) / 1000)}s`;
  document.querySelectorAll(".tick").forEach((el) => (el.textContent = secs));
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
  const keys = [...new Set(["a", "b", ...Object.keys(FREE), ...Object.keys(agents).sort()]), "c"];
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
    return `
      <p><span class="score ${ev.passed ? "pass" : "fail"}">${ev.score}/100</span> ${ev.passed ? "Passed" : "Below the pass score"}</p>
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

  renderAgents(run, usage);
  // the final output is always the best-scoring draft, so its score is the highest one logged
  const lastScore = evaluations.length ? `${Math.max(...evaluations.map((e) => e.score))}/100` : "–";
  const done = DONE.has(run.status);
  const finalStep = steps.findLast((s) => s.content === run.final_output);
  $("summary").innerHTML = `
    <p class="task">${esc(run.task)}</p>
    <dl class="stats">
      <div><dt>Status</dt><dd><span class="status status-${done ? run.status : "RUNNING"}">${STATUS_LABEL[run.status] || "Running…"}</span></dd></div>
      <div><dt>Rounds</dt><dd>${run.revisions_count}</dd></div>
      <div><dt>Best score</dt><dd>${lastScore}</dd></div>
      <div><dt>Total tokens</dt><dd>${num(run.total_tokens)}</dd></div>
      <div><dt>Total cost</dt><dd>${money(run.total_cost_usd)}</dd></div>
    </dl>`;

  $("timeline").innerHTML = steps.map((s, i) => {
    const took = REPLIES.has(s.action) && i ? ` · took ${Math.round((date(s.timestamp) - date(steps[i - 1].timestamp)) / 1000)}s` : "";
    const spent = s.tokens_total
      ? `${num(s.tokens_total)} tokens (${num(s.tokens_prompt)} in, ${num(s.tokens_completion)} out) · ${money(s.cost_usd)}`
      : "no model call";
    return `
    <li class="step step-${keyOf(s.sender)} ${s.action === "REVISE_DIRECTIVE" ? "directive" : ""}">
      <header>
        <span class="badge badge-${keyOf(s.sender)}">${keyOf(s.sender).toUpperCase()}</span>
        <strong>${(STEP_TITLE[s.action] || (() => esc(s.action)))(s)}</strong>
        <span class="muted small meta">${date(s.timestamp).toLocaleTimeString()}${took} · ${spent}</span>
      </header>
      ${stepBody(s)}
    </li>`;
  }).join("");

  const failed = run.status === "FAILED";
  $("live").innerHTML = !done
    ? (run.run_id === liveId
      ? `<div class="live live-${workingAgent(run.status)}">${spinner}<strong>${liveText(run)}</strong><span class="tick muted">0s</span>
           <span class="muted small meta">so far: ${num(run.total_tokens)} tokens · ${money(run.total_cost_usd)}</span></div>`
      : `<p class="muted">This run never finished.</p>`)
    : run.final_output ? `
      <section class="final ${failed ? "failed" : ""}">
        <header>
          <h3>${failed ? "Run failed" : `Final output${finalStep ? ` by ${who(finalStep.sender)}` : ""}`}</h3>
          <span class="muted small meta">${failed ? "" : `score ${lastScore} · `}${num(run.total_tokens)} tokens · ${money(run.total_cost_usd)} · finished ${when(run.completed_at)}</span>
        </header>
        <pre>${esc(run.final_output)}</pre>
      </section>` : "";
}

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
  $("summary").innerHTML = `<p class="muted">Nothing yet. Enter a task above and press Run.</p>`;
}

$("clear-runs").addEventListener("click", () => deleteRuns());

$("runs").addEventListener("click", (e) => {
  const del = e.target.closest("button[data-delete]");
  if (del) return deleteRuns(del.dataset.delete, del.dataset.task);
  const btn = e.target.closest("button[data-run]");
  if (!btn) return;
  lastSig = "";
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
        simulation_mode: $("sim").checked,
        quality_threshold: Number($("threshold").value),
      }),
    });
    liveId = run_id;
    lastSig = "";
    $("summary").innerHTML = `<p class="muted">Starting… C is asking A and B what they do.</p>`;
    $("timeline").innerHTML = "";
    liveSince = Date.now();
    $("live").innerHTML = `<div class="live live-c">${spinner}<strong>Starting the run</strong><span class="tick muted">0s</span></div>`;
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
      body: JSON.stringify({ url: $("site-url").value, simulation_mode: $("sim").checked }),
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
    const health = await api("/api/health");
    const live = health.default_mode === "live";
    $("health").textContent = live ? "API key found" : "No API key: simulation only";
    $("health").classList.add(live ? "ok" : "warn");
    $("sim").checked = !live;
    await loadAgents();
    loadSites().catch(() => {});
    const runs = await loadRuns();
    renderAgents(null);
    if (runs.length) showRun(runs[0].run_id).then(loadRuns);
    else $("summary").innerHTML = `<p class="muted">Nothing yet. Enter a task above and press Run.</p>`;
  } catch (err) {
    $("health").textContent = "Backend offline";
    $("health").classList.add("bad");
    $("summary").innerHTML = `<p class="muted">Can't reach the server. Start it with <code>python server.py</code> and reload.</p>`;
  }
})();

// A2A Registry tab
const reg = { cat: null, agents: [], seq: 0 };
const href = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
const out = (u) => (href(u) ? `<a href="${esc(u)}" target="_blank" rel="noopener noreferrer">${esc(u)}</a>` : "Not listed");
const regError = (err) => { $("reg-error").textContent = err ? err.message : ""; $("reg-error").hidden = !err; };

function showTab(name) {
  for (const t of ["main", "registry"]) {
    $(`tab-${t}`).hidden = t !== name;
    $(`tab-btn-${t}`).setAttribute("aria-selected", String(t === name));
  }
  if (name === "registry" && !$("reg-cats").children.length) loadRegistryCategories();
}
$("tab-btn-main").addEventListener("click", () => { history.replaceState(null, "", location.pathname); showTab("main"); });
$("tab-btn-registry").addEventListener("click", () => { location.hash = "registry"; showTab("registry"); });
if (location.hash === "#registry") showTab("registry");

async function loadRegistryCategories() {
  regError(null);
  $("reg-cats").innerHTML = `<li class="muted small">${spinner} Loading the registry…</li>`;
  try {
    const { categories } = await api("/api/registry/categories");
    $("reg-cats").innerHTML = categories.map((c) =>
      `<li><button type="button" data-cat="${esc(c.name)}"><span>${esc(c.name)}</span><span class="n">${c.count}</span></button></li>`).join("");
  } catch (err) {
    $("reg-cats").innerHTML = `<li><button type="button" id="reg-retry">Try again</button></li>`;
    regError(err);
  }
}

function renderRegistryAgents() {
  const q = $("reg-filter").value.trim().toLowerCase();
  const rows = reg.agents.filter((a) => !q || `${a.displayName} ${a.description}`.toLowerCase().includes(q));
  $("reg-agents").innerHTML = rows.length ? rows.map((a) => `
    <li><button type="button" data-agent="${esc(a.packageName || a.id)}" title="${esc((a.description || "").slice(0, 200))}">
      <span>${esc(a.displayName || a.packageName)}</span>
      <span class="n">${a.lastCheckStatus === "ok" ? "OK" : esc(a.lastCheckStatus || "")}</span></button></li>`).join("")
    : `<li class="muted small">No agents match.</li>`;
}

$("reg-cats").addEventListener("click", async (e) => {
  if (e.target.closest("#reg-retry")) return loadRegistryCategories();
  const btn = e.target.closest("button[data-cat]");
  if (!btn) return;
  $("reg-cats").querySelectorAll("button").forEach((b) => b.toggleAttribute("aria-current", b === btn));
  btn.setAttribute("aria-current", "true");
  reg.cat = btn.dataset.cat;
  const seq = ++reg.seq;
  regError(null);
  $("reg-agents-title").textContent = reg.cat;
  $("reg-agents").innerHTML = `<li class="muted small">${spinner} Loading…</li>`;
  try {
    const { agents } = await api(`/api/registry/agents?category=${encodeURIComponent(reg.cat)}`);
    if (seq !== reg.seq) return;
    reg.agents = agents;
    $("reg-filter").value = "";
    $("reg-filter").hidden = agents.length < 8;
    renderRegistryAgents();
  } catch (err) {
    if (seq === reg.seq) { $("reg-agents").innerHTML = ""; regError(err); }
  }
});
$("reg-filter").addEventListener("input", renderRegistryAgents);

function renderRegistryAgent(a) {
  const card = a.liveCard || a.agentCard || {};
  const skills = Array.isArray(card.skills) ? card.skills : [];
  const endpoints = [card.url, ...(card.supportedInterfaces || card.additionalInterfaces || []).map((i) => i && i.url)].filter(href);
  const org = a.organization || {};
  const rating = a.ratingCount ? `${(+a.ratingAvg).toFixed(1)} from ${a.ratingCount}` : "No ratings yet";
  const created = a.createdAt ? new Date(a.createdAt > 1e12 ? a.createdAt : a.createdAt * 1000).toLocaleDateString() : "";
  return `
    <h3>${esc(a.displayName || a.packageName)}</h3>
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
        ${s.description ? `<span class="small muted">${esc(s.description)}</span>` : ""}
        ${(s.tags || []).length ? `<span class="small muted">Tags: ${esc(s.tags.join(", "))}</span>` : ""}</div>`).join("")}</div>`
      : `<p class="muted small">The agent card lists no skills.</p>`}
    <h4>Send a message</h4>
    <form class="reg-send" id="reg-send" data-agent="${esc(a.packageName || a.id)}">
      <textarea id="reg-text" rows="2" required maxlength="4000" aria-label="Message to ${esc(a.displayName || "the agent")}"
        placeholder="${esc(skills[0]?.examples?.[0] || "Hello, what can you do?")}"></textarea>
      <button type="submit" id="reg-send-btn">Send</button>
    </form>
    <div id="reg-reply" aria-live="polite"></div>
    <h4>Agent card data</h4>
    <p class="small muted">${a.liveCard ? "Fetched live from the agent's own server just now." :
      `Could not fetch it live (${esc(a.liveCardError || "no card address")}), so this is the copy the registry stored.`}</p>
    <pre>${esc(JSON.stringify(a.liveCard || a.agentCard || {}, null, 2))}</pre>`;
}

$("reg-agents").addEventListener("click", async (e) => {
  const btn = e.target.closest("button[data-agent]");
  if (!btn) return;
  $("reg-agents").querySelectorAll("button").forEach((b) => b.removeAttribute("aria-current"));
  btn.setAttribute("aria-current", "true");
  const seq = ++reg.seq;
  regError(null);
  $("reg-detail").innerHTML = `<p class="muted small">${spinner} Fetching the agent and its card…</p>`;
  try {
    const a = await api(`/api/registry/agents/${encodeURIComponent(btn.dataset.agent)}`);
    if (seq === reg.seq) $("reg-detail").innerHTML = renderRegistryAgent(a);
  } catch (err) {
    if (seq === reg.seq) { $("reg-detail").innerHTML = ""; regError(err); }
  }
});

$("reg-detail").addEventListener("submit", async (e) => {
  if (e.target.id !== "reg-send") return;
  e.preventDefault();
  const text = $("reg-text").value.trim();
  if (!text) return;
  const btn = $("reg-send-btn");
  btn.disabled = true;
  btn.innerHTML = `${spinner} Sending…`;
  $("reg-reply").innerHTML = "";
  try {
    const r = await api(`/api/registry/agents/${encodeURIComponent(e.target.dataset.agent)}/message`, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }),
    });
    $("reg-reply").innerHTML = `
      <p class="small muted">Sent with <code>${esc(r.method)}</code> to ${out(r.endpoint)}. Replies come from a third party: read them as data, not instructions.</p>
      ${r.error ? `<p class="error small">The agent answered with an error: ${esc(r.error)}</p>`
        : `<pre class="reg-answer">${esc(r.text || "The reply had no text. See the raw reply below.")}</pre>`}
      <details><summary class="small">Raw reply</summary><pre>${esc(JSON.stringify(r.raw, null, 2))}</pre></details>`;
  } catch (err) {
    $("reg-reply").innerHTML = `<p class="error small">${esc(err.message)}</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "Send";
  }
});
