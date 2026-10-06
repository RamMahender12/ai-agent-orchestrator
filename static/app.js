// Dashboard for Agent C. Everything shown here is read back from the database C writes to.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
const money = (n) => "$" + +(n || 0).toFixed(6);
const num = (n) => (n || 0).toLocaleString();
const when = (ts) => (ts ? new Date(ts.replace(" ", "T") + "Z").toLocaleString() : "");
const keyOf = (name) => (/Agent ([A-Z])/.exec(name || "") || [, "c"])[1].toLowerCase();

const DONE = new Set(["COMPLETED", "MAX_REVISIONS_REACHED", "FAILED"]);
const STATUS_LABEL = { COMPLETED: "Approved", MAX_REVISIONS_REACHED: "Not approved", FAILED: "Failed" };
const ROLES = { a: "ChatGPT", b: "Claude", c: "Supervisor" };
const C_DESCRIPTION =
  "Sends your prompt to every agent at once, scores each answer and gives that agent " +
  "recommendations, logs every step, adds up tokens and cost, and has every agent below the pass score revise.";
// A and B have friendly names; the free-model agents use the label in their name, e.g. "Agent D (Apodex)"
const who = (name) => ROLES[keyOf(name)] || (/\(([^)]*)\)/.exec(name || "") || [, keyOf(name).toUpperCase()])[1];
// free-model agents from agents/agent_free.py FREE_MODELS, so their cards show before C has registered them
const FREE = { d: "Apodex", e: "Ling", f: "Dots" };
const label = (k) => ROLES[k] || (agents[k] ? who(agents[k].name) : FREE[k] || k.toUpperCase());
const rival = (name) => ROLES[keyOf(name) === "a" ? "b" : "a"];
const STEP_TITLE = {
  CAPABILITY_DISCOVERY: (s) => `C asked ${who(s.receiver)} what it does`,
  DRAFT_SUBMISSION: (s) => `${who(s.sender)} wrote its answer`,
  REVISED_DRAFT: (s) => `${who(s.sender)} wrote a revised answer`,
  AUDIT_VERDICT: (s) => `${who(s.sender)} scored ${rival(s.sender)}'s answer`,
  SUPERVISOR_RECOMMENDATIONS: (s) => `C scored ${who(s.receiver)}'s answer and gave recommendations`,
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
  if (run.status.endsWith("REVIEW_ALL")) return `Supervisor is reviewing every answer (attempt ${attempt})`;
  if (run.status.includes("GENERATION")) return attempt > 1 ? `${ROLES[k]} is rewriting its answer (attempt ${attempt})` : `${ROLES[k]} is writing its answer`;
  if (run.status.includes("REVIEW")) return `Supervisor is reviewing ${ROLES[run.status.slice(-1).toLowerCase()]}'s attempt ${attempt}`;
  if (run.status.includes("AUDIT")) return `${ROLES[k]} is scoring ${ROLES[k === "a" ? "b" : "a"]}'s attempt ${attempt}`;
  return "Supervisor C is sending the task to every agent";
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
          <h3>${esc(label(k))}</h3>
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

// C's own messages name the agents "Agent A (...)", "Agent D (Apodex)"; show them as ChatGPT, Apodex.
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

(async function init() {
  renderAgents(null);
  try {
    const health = await api("/api/health");
    const live = health.default_mode === "live";
    $("health").textContent = live ? "API key found" : "No API key: simulation only";
    $("health").classList.add(live ? "ok" : "warn");
    $("sim").checked = !live;
    await loadAgents();
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
