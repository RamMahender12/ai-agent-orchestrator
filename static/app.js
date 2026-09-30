// ==========================================================================
// NEXUS ORCHESTRATOR - CLIENT CONTROLLER & TELEMETRY ENGINE
// Autonomous Multi-Agent Supervision, Quality Gates & Telemetry
// ==========================================================================

document.addEventListener("DOMContentLoaded", () => {
  // Global State
  let globalTokens = 0;
  let globalCost = 0.0;
  let supervisorDirectives = 0;
  let supervisorTokens = 0;
  let supervisorCost = 0.0;
  let creatorRevisions = 0;
  let creatorTokens = 0;
  let creatorCost = 0.0;
  let auditorTokens = 0;
  let auditorCost = 0.0;
  let lastAuditorScore = null;

  let activeEventSource = null;
  let isStandaloneMode = false;
  let currentChatTarget = "triad"; // "triad", "supervisor", "agent_a", "agent_b"

  // -------------------------------------------------------------------------
  // DOM Elements
  // -------------------------------------------------------------------------
  // Header Telemetry
  const systemStatusDot = document.getElementById("system-status-dot");
  const systemStatusText = document.getElementById("system-status-text");
  const globalTokensEl = document.getElementById("global-tokens");
  const globalCostEl = document.getElementById("global-cost");
  const modeCheckbox = document.getElementById("mode-checkbox");
  const modeText = document.getElementById("mode-text");

  // Navigation
  const navTabs = document.querySelectorAll(".nav-tab");
  const tabContents = document.querySelectorAll(".tab-content");

  // Mission Control & Launchpad
  const taskInput = document.getElementById("task-input");
  const btnLaunch = document.getElementById("btn-launch-workflow");
  const btnLaunchIcon = document.getElementById("btn-launch-icon");
  const btnLaunchLabel = document.getElementById("btn-launch-label");
  const gateSlider = document.getElementById("gate-slider");
  const gateDisplay = document.getElementById("gate-display");
  const selModelA = document.getElementById("sel-model-a");
  const selModelB = document.getElementById("sel-model-b");
  const activeRunIdEl = document.getElementById("active-run-id");
  const presetChips = document.querySelectorAll(".preset-chip");

  // Pipeline Stepper Nodes
  const stepNodes = [
    document.getElementById("step-node-1"),
    document.getElementById("step-node-2"),
    document.getElementById("step-node-3"),
    document.getElementById("step-node-4"),
    document.getElementById("step-node-5"),
    document.getElementById("step-node-6"),
  ];

  // Arena Columns & Telemetry
  const statePillC = document.getElementById("state-pill-c");
  const cDirectivesEl = document.getElementById("c-directives");
  const cTokensEl = document.getElementById("c-tokens");
  const cCostEl = document.getElementById("c-cost");
  const feedColC = document.getElementById("feed-col-c");
  const btnClearC = document.getElementById("btn-clear-c");

  const statePillA = document.getElementById("state-pill-a");
  const aRevisionsEl = document.getElementById("a-revisions");
  const aTokensEl = document.getElementById("a-tokens");
  const aCostEl = document.getElementById("a-cost");
  const feedColA = document.getElementById("feed-col-a");
  const btnClearA = document.getElementById("btn-clear-a");

  const statePillB = document.getElementById("state-pill-b");
  const bScoreEl = document.getElementById("b-score");
  const bTokensEl = document.getElementById("b-tokens");
  const bCostEl = document.getElementById("b-cost");
  const feedColB = document.getElementById("feed-col-b");
  const btnClearB = document.getElementById("btn-clear-b");

  // Chat Sandbox
  const dossierCards = document.querySelectorAll(".dossier-card");
  const chatHeaderAvatar = document.getElementById("chat-header-avatar");
  const chatHeaderTitle = document.getElementById("chat-header-title");
  const chatHeaderDesc = document.getElementById("chat-header-desc");
  const chatMessagesContainer = document.getElementById("chat-messages-container");
  const chatInput = document.getElementById("chat-input");
  const btnChatSend = document.getElementById("btn-chat-send");
  const btnClearChat = document.getElementById("btn-clear-chat");
  const chatSuggestBtns = document.querySelectorAll(".chat-suggest-btn");

  // Database Tab
  const dbtabRunsBtn = document.getElementById("dbtab-runs-btn");
  const dbtabAgentsBtn = document.getElementById("dbtab-agents-btn");
  const containerDbtabRuns = document.getElementById("container-dbtab-runs");
  const containerDbtabAgents = document.getElementById("container-dbtab-agents");
  const runsTbody = document.getElementById("runs-tbody");
  const agentsTbody = document.getElementById("agents-tbody");
  const btnRefreshDb = document.getElementById("btn-refresh-db");

  // Run Inspector Modal
  const runModal = document.getElementById("run-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const modalRunTitle = document.getElementById("modal-run-title");
  const modalRunBody = document.getElementById("modal-run-body");

  // -------------------------------------------------------------------------
  // Initialization
  // -------------------------------------------------------------------------
  checkBackendHealth();
  fetchRunsTable();
  fetchAgentsTable();

  // Tab Switching
  navTabs.forEach((btn) => {
    btn.addEventListener("click", () => {
      navTabs.forEach((b) => b.classList.remove("active"));
      tabContents.forEach((c) => c.classList.remove("active"));

      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetPanel = document.getElementById(targetId);
      if (targetPanel) targetPanel.classList.add("active");

      if (targetId === "tab-database") {
        fetchRunsTable();
        fetchAgentsTable();
      }
    });
  });

  // Quality Acceptance Gate Slider
  if (gateSlider && gateDisplay) {
    gateSlider.addEventListener("input", (e) => {
      gateDisplay.textContent = `${e.target.value} / 100`;
    });
  }

  // Preset Chips
  presetChips.forEach((chip) => {
    chip.addEventListener("click", () => {
      const taskText = chip.getAttribute("data-task");
      if (taskInput) {
        taskInput.value = taskText;
        taskInput.focus();
      }
    });
  });

  // Clear Screen Handlers
  if (btnClearC) btnClearC.addEventListener("click", () => clearFeed(feedColC));
  if (btnClearA) btnClearA.addEventListener("click", () => clearFeed(feedColA));
  if (btnClearB) btnClearB.addEventListener("click", () => clearFeed(feedColB));
  if (btnClearChat) btnClearChat.addEventListener("click", () => clearFeed(chatMessagesContainer));

  function clearFeed(container) {
    if (!container) return;
    container.innerHTML = `
      <div class="feed-placeholder">
        <span class="feed-placeholder-icon">🧹</span>
        <span class="feed-placeholder-text">Screen cleared. New events and messages will appear here.</span>
      </div>`;
  }

  // -------------------------------------------------------------------------
  // Multi-Agent Workflow Launchpad
  // -------------------------------------------------------------------------
  if (btnLaunch) {
    btnLaunch.addEventListener("click", () => executeWorkflow());
  }

  if (taskInput) {
    taskInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        executeWorkflow();
      }
    });
  }

  async function executeWorkflow() {
    let task = taskInput ? taskInput.value.trim() : "";
    if (!task) {
      task = "Design a resilient, high-throughput financial transaction processing engine with audit logging and rate limiting.";
      if (taskInput) taskInput.value = task;
    }

    const simMode = modeCheckbox ? modeCheckbox.checked : false;
    const modelA = selModelA ? selModelA.value : "poolside/laguna-s-2.1:free";
    const modelB = selModelB ? selModelB.value : "nvidia/nemotron-3-ultra-550b-a55b:free";
    const threshold = gateSlider ? parseInt(gateSlider.value, 10) : 80;

    // Set Launch Button State
    setLaunchLoading(true);
    resetLifecycleSteps();
    setLifecycleStep(1); // Step 1: Discovery

    // Update Agent Status Pills
    setAgentState(statePillC, "DISCOVERING", "running");
    setAgentState(statePillA, "STANDBY", "");
    setAgentState(statePillB, "STANDBY", "");

    showArenaLoader(feedColC, "Supervisor interrogating Agent A & B...");

    try {
      if (isStandaloneMode) throw new Error("Autonomous Simulation Mode");

      const res = await fetch("/api/orchestrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task,
          simulation_mode: simMode,
          model_a: modelA,
          model_b: modelB,
          quality_threshold: threshold,
        }),
      });

      if (!res.ok) {
        let errorDetail = "Failed to launch workflow";
        try {
          const body = await res.json();
          errorDetail = body.detail || errorDetail;
        } catch (e) {}
        throw new Error(errorDetail);
      }

      const resData = await res.json();
      const runId = resData.run_id;
      if (activeRunIdEl) activeRunIdEl.textContent = runId;

      connectOrchestrationStream(runId);
    } catch (err) {
      if (isStandaloneMode) {
        runClientAutonomousWorkflow(task, modelA, modelB, threshold);
        return;
      }

      hideArenaLoader(feedColC);
      appendSupervisorCard(
        feedColC,
        "System Error",
        `Execution failed: ${escapeHtml(err.message)}`,
        null,
        true,
        false
      );
      setLaunchLoading(false);
      setAgentState(statePillC, "FAILED", "");
    }
  }

  function setLaunchLoading(isLoading) {
    if (!btnLaunch) return;
    btnLaunch.disabled = isLoading;
    if (isLoading) {
      btnLaunchIcon.textContent = "⏳";
      btnLaunchLabel.textContent = "Orchestrating...";
    } else {
      btnLaunchIcon.textContent = "🚀";
      btnLaunchLabel.textContent = "Launch Workflow";
    }
  }

  function setAgentState(pillEl, text, statusClass) {
    if (!pillEl) return;
    pillEl.textContent = text;
    pillEl.className = "state-pill";
    if (statusClass) pillEl.classList.add(statusClass);
  }

  // -------------------------------------------------------------------------
  // Lifecycle Stepper Visual Progress
  // -------------------------------------------------------------------------
  function resetLifecycleSteps() {
    stepNodes.forEach((node) => {
      if (node) {
        node.classList.remove("active", "completed");
      }
    });
  }

  function setLifecycleStep(stepNumber) {
    stepNodes.forEach((node, idx) => {
      if (!node) return;
      const nodeNum = idx + 1;
      if (nodeNum < stepNumber) {
        node.classList.remove("active");
        node.classList.add("completed");
      } else if (nodeNum === stepNumber) {
        node.classList.remove("completed");
        node.classList.add("active");
      } else {
        node.classList.remove("active", "completed");
      }
    });
  }

  // -------------------------------------------------------------------------
  // Real-Time SSE Stream Listener
  // -------------------------------------------------------------------------
  function connectOrchestrationStream(runId) {
    if (activeEventSource) activeEventSource.close();

    activeEventSource = new EventSource(`/api/stream/${runId}`);

    activeEventSource.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        handleStreamPayload(payload);
      } catch (err) {
        console.error("Failed to parse SSE payload", err);
      }
    };

    activeEventSource.onerror = () => {
      activeEventSource.close();
      setLaunchLoading(false);
    };
  }

  function handleStreamPayload(data) {
    const event = data.event;
    hideAllLoaders();

    // Update Global Telemetry
    if (data.total_tokens !== undefined) {
      globalTokens = data.total_tokens;
      if (globalTokensEl) globalTokensEl.textContent = globalTokens.toLocaleString();
    }
    if (data.total_cost_usd !== undefined) {
      globalCost = data.total_cost_usd;
      if (globalCostEl) globalCostEl.textContent = `$${globalCost.toFixed(4)}`;
    }

    switch (event) {
      // Step 1: Agent Registration
      case "agent_registered": {
        setLifecycleStep(1);
        const agent = data.agent;
        supervisorDirectives++;
        if (cDirectivesEl) cDirectivesEl.textContent = supervisorDirectives;

        const body = `Discovered <strong>${escapeHtml(agent.name)}</strong> (${escapeHtml(agent.provider)} · <code>${escapeHtml(agent.model)}</code>).<br>Role: <em>${escapeHtml(agent.role)}</em>.<br>Capabilities: ${agent.capabilities.map((c) => `<span class="dossier-tag">${escapeHtml(c)}</span>`).join(" ")}`;
        appendSupervisorCard(feedColC, "Capability Discovered", body, data.step?.token_usage);

        if (data.step?.token_usage) tallySupervisorUsage(data.step.token_usage);

        // Prep Agent A
        setLifecycleStep(2);
        setAgentState(statePillA, "DRAFTING (REV 1)", "running");
        showArenaLoader(feedColA, "Agent A (OpenAI) drafting technical solution...");
        break;
      }

      // Step 2 & 5: Draft Produced by Agent A
      case "draft_produced": {
        const rev = data.revision;
        const tokens = data.tokens;
        creatorRevisions = rev;
        if (aRevisionsEl) aRevisionsEl.textContent = rev;

        setAgentState(statePillA, rev === 1 ? "DRAFT REV 1" : `REVISION ${rev}`, "running");
        setLifecycleStep(rev === 1 ? 2 : 5);

        appendCreatorCard(
          feedColA,
          rev === 1 ? "Initial Technical Deliverable (Revision 1)" : `Refined Deliverable (Revision ${rev})`,
          data.draft,
          tokens,
          rev
        );

        if (tokens) tallyCreatorUsage(tokens);

        // Shift to Agent B
        setLifecycleStep(3);
        setAgentState(statePillB, `AUDITING (REV ${rev})`, "running");
        showArenaLoader(feedColB, `Agent B (Claude) auditing Revision ${rev}...`);
        break;
      }

      // Step 3: Audit Completed by Agent B
      case "audit_completed": {
        setLifecycleStep(3);
        const ev = data.evaluation;
        const rev = data.revision;
        lastAuditorScore = ev.score;

        if (bScoreEl) {
          bScoreEl.textContent = `${ev.score}/100`;
          bScoreEl.style.color = ev.passed ? "var(--a-light)" : "var(--accent-danger)";
        }

        setAgentState(statePillB, ev.passed ? "APPROVED" : "REJECTED (FLAWS DETECTED)", ev.passed ? "approved" : "intervening");

        appendAuditorCard(feedColB, ev, rev);
        if (ev.token_usage) tallyAuditorUsage(ev.token_usage);
        break;
      }

      // Step 4: Supervisor Intervention (Score < Threshold)
      case "supervisor_intervention": {
        setLifecycleStep(4);
        supervisorDirectives++;
        if (cDirectivesEl) cDirectivesEl.textContent = supervisorDirectives;

        setAgentState(statePillC, "INTERVENING", "intervening");

        const msg = `Quality score <strong>${data.score}/100</strong> fell below user Acceptance Gate (${gateSlider ? gateSlider.value : 80}).<br>` +
          `<strong>Corrective Action:</strong> Directive issued to Agent A commanding Revision ${data.revision + 1} with immediate mitigation of all Claude audit defects.`;

        appendSupervisorCard(feedColC, "Quality Gate Breached · Intervention", msg, data.step?.token_usage, true, false);

        if (data.step?.token_usage) tallySupervisorUsage(data.step.token_usage);

        // Tell Agent A to Revise
        setLifecycleStep(5);
        setAgentState(statePillA, `REVISING (REV ${data.revision + 1})`, "running");
        showArenaLoader(feedColA, `Agent A implementing Revision ${data.revision + 1} with Claude fixes...`);
        break;
      }

      // Step 6: Final Approval & Sign-off
      case "workflow_completed": {
        setLifecycleStep(6);
        setAgentState(statePillC, "APPROVED", "approved");
        setAgentState(statePillA, "READY", "approved");
        setAgentState(statePillB, "READY", "approved");

        const signOffMsg = `<strong>🎉 DELIVERABLE APPROVED & VERIFIED!</strong><br>` +
          `Final Quality Score: <strong>${data.final_score}/100</strong>.<br>` +
          `Multi-agent loop resolved across <strong>${data.revisions} revisions</strong>.<br>` +
          `Audit trail sealed and recorded in SQLite (<code>orchestration.db</code>).`;

        appendSupervisorCard(feedColC, "Final Sign-Off & SQLite Seal", signOffMsg, data.step?.token_usage, false, true);

        if (data.step?.token_usage) tallySupervisorUsage(data.step.token_usage);
        setLaunchLoading(false);
        break;
      }
    }
  }

  // -------------------------------------------------------------------------
  // Telemetry Aggregators
  // -------------------------------------------------------------------------
  function tallySupervisorUsage(usage) {
    if (!usage) return;
    supervisorTokens += usage.total_tokens || 0;
    supervisorCost += usage.cost_usd || 0;
    if (cTokensEl) cTokensEl.textContent = supervisorTokens.toLocaleString();
    if (cCostEl) cCostEl.textContent = `$${supervisorCost.toFixed(4)}`;
  }

  function tallyCreatorUsage(usage) {
    if (!usage) return;
    creatorTokens += usage.total_tokens || 0;
    creatorCost += usage.cost_usd || 0;
    if (aTokensEl) aTokensEl.textContent = creatorTokens.toLocaleString();
    if (aCostEl) aCostEl.textContent = `$${creatorCost.toFixed(4)}`;
  }

  function tallyAuditorUsage(usage) {
    if (!usage) return;
    auditorTokens += usage.total_tokens || 0;
    auditorCost += usage.cost_usd || 0;
    if (bTokensEl) bTokensEl.textContent = auditorTokens.toLocaleString();
    if (bCostEl) bCostEl.textContent = `$${auditorCost.toFixed(4)}`;
  }

  // -------------------------------------------------------------------------
  // Message & Feed Card Renderers
  // -------------------------------------------------------------------------
  function appendSupervisorCard(container, title, content, usage, isIntervention = false, isApproval = false) {
    if (!container) return;
    removePlaceholder(container);

    const card = document.createElement("div");
    card.className = "arena-card";
    if (isIntervention) card.classList.add("card-intervention");

    const time = new Date().toLocaleTimeString();
    const tokenBadge = usage
      ? `<span style="color: var(--c-light); font-family: var(--font-mono);">${usage.total_tokens || 0} tok | $${(usage.cost_usd || 0).toFixed(4)}</span>`
      : "";

    let interventionBanner = "";
    if (isIntervention) {
      interventionBanner = `
        <div class="intervention-banner">
          <span>🚨</span>
          <span>SUPERVISOR INTERVENTION ENFORCED</span>
        </div>`;
    }

    card.innerHTML = `
      ${interventionBanner}
      <div class="arena-card-header">
        <div class="card-title-group">
          <span class="card-step-tag ${isIntervention ? 'tag-intervene' : 'tag-c'}">${escapeHtml(title)}</span>
        </div>
        <div class="card-meta-right">
          ${tokenBadge}
          <span style="color: var(--text-dim);">${time}</span>
        </div>
      </div>
      <div class="arena-card-body">
        ${content}
      </div>
    `;

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  function appendCreatorCard(container, title, content, usage, revision) {
    if (!container) return;
    removePlaceholder(container);

    const card = document.createElement("div");
    card.className = "arena-card";

    const time = new Date().toLocaleTimeString();
    const tokenBadge = usage
      ? `<span style="color: var(--a-light); font-family: var(--font-mono);">${usage.total_tokens || 0} tok | $${(usage.cost_usd || 0).toFixed(4)}</span>`
      : "";

    // Parse and syntax-box any code blocks
    const formattedBody = formatCodeAndMarkdown(content);

    card.innerHTML = `
      <div class="arena-card-header">
        <div class="card-title-group">
          <span class="card-step-tag tag-a">REV ${revision}</span>
          <strong style="color: var(--a-light); font-size: 0.82rem;">${escapeHtml(title)}</strong>
        </div>
        <div class="card-meta-right">
          ${tokenBadge}
          <span style="color: var(--text-dim);">${time}</span>
        </div>
      </div>
      <div class="arena-card-body">
        ${formattedBody}
      </div>
    `;

    // Attach copy button handlers within this card
    card.querySelectorAll(".btn-copy-code").forEach((btn) => {
      btn.addEventListener("click", () => {
        const codeText = btn.getAttribute("data-code");
        if (codeText) {
          navigator.clipboard.writeText(codeText);
          const origText = btn.innerHTML;
          btn.innerHTML = "<span>✓ Copied!</span>";
          setTimeout(() => (btn.innerHTML = origText), 1800);
        }
      });
    });

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  function appendAuditorCard(container, ev, revision) {
    if (!container) return;
    removePlaceholder(container);

    const card = document.createElement("div");
    card.className = "arena-card";

    const time = new Date().toLocaleTimeString();
    const tokenBadge = ev.token_usage
      ? `<span style="color: var(--b-light); font-family: var(--font-mono);">${ev.token_usage.total_tokens || 0} tok | $${(ev.token_usage.cost_usd || 0).toFixed(4)}</span>`
      : "";

    let flawsHtml = "";
    if (ev.flaws && ev.flaws.length) {
      flawsHtml = `
        <div class="audit-section">
          <div class="audit-section-title audit-flaws-title">Identified Vulnerabilities & Flaws:</div>
          <ul class="audit-list" style="color: #fca5a5;">
            ${ev.flaws.map((f) => `<li>• ${escapeHtml(f)}</li>`).join("")}
          </ul>
        </div>`;
    }

    let strengthsHtml = "";
    if (ev.strengths && ev.strengths.length) {
      strengthsHtml = `
        <div class="audit-section">
          <div class="audit-section-title audit-strengths-title">Verified Strengths & Compliance:</div>
          <ul class="audit-list" style="color: #86efac;">
            ${ev.strengths.map((s) => `<li>• ${escapeHtml(s)}</li>`).join("")}
          </ul>
        </div>`;
    }

    let feedbackHtml = "";
    if (ev.actionable_feedback) {
      feedbackHtml = `
        <div class="audit-section">
          <div class="audit-section-title audit-feedback-title">Actionable Recommendation for Agent A:</div>
          <div class="audit-quote">"${escapeHtml(ev.actionable_feedback)}"</div>
        </div>`;
    }

    card.innerHTML = `
      <div class="arena-card-header">
        <div class="card-title-group">
          <span class="card-step-tag tag-b">AUDIT REV ${revision}</span>
          <strong style="color: var(--b-light); font-size: 0.82rem;">Quality Evaluation Report</strong>
        </div>
        <div class="card-meta-right">
          ${tokenBadge}
          <span style="color: var(--text-dim);">${time}</span>
        </div>
      </div>
      <div class="arena-card-body">
        <div class="scorecard-banner">
          <div class="scorecard-gauge">
            <span class="score-num ${ev.passed ? 'score-passed' : 'score-rejected'}">${ev.score}</span>
            <span class="score-denom">/ 100</span>
          </div>
          <span class="verdict-tag ${ev.passed ? 'verdict-passed' : 'verdict-rejected'}">
            ${ev.passed ? '✓ PASSED GATE' : '✗ GATE REJECTED'}
          </span>
        </div>
        ${flawsHtml}
        ${strengthsHtml}
        ${feedbackHtml}
      </div>
    `;

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  function formatCodeAndMarkdown(rawText) {
    if (!rawText) return "";
    let formatted = escapeHtml(rawText);

    // Extract code blocks
    formatted = formatted.replace(/```(?:python)?([\s\S]*?)```/g, (match, code) => {
      const cleanCode = code.trim();
      return `
        <div class="code-deliverable-box">
          <div class="code-header-strip">
            <span>PYTHON ARCHITECTURE</span>
            <button class="btn-copy-code" data-code="${escapeHtml(cleanCode)}">
              <span>📋 Copy Code</span>
            </button>
          </div>
          <pre><code>${cleanCode}</code></pre>
        </div>`;
    });

    formatted = formatted.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    formatted = formatted.replace(/\*(.*?)\*/g, "<em>$1</em>");
    formatted = formatted.replace(/\n### (.*?)\n/g, '<h4 style="color: var(--c-light); margin: 8px 0 4px;">$1</h4>');
    formatted = formatted.replace(/\n#### (.*?)\n/g, '<h5 style="color: var(--a-light); margin: 6px 0 2px;">$1</h5>');
    formatted = formatted.replace(/\n• /g, "<br>• ");
    formatted = formatted.replace(/\n\n/g, "<br><br>");
    formatted = formatted.replace(/\n/g, "<br>");
    return formatted;
  }

  function escapeHtml(text) {
    if (!text) return "";
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function removePlaceholder(container) {
    if (!container) return;
    const ph = container.querySelector(".feed-placeholder");
    if (ph) ph.remove();
  }

  function showArenaLoader(container, label) {
    if (!container || container.querySelector("[data-arena-loader]")) return;
    removePlaceholder(container);
    const card = document.createElement("div");
    card.className = "typing-card";
    card.setAttribute("data-arena-loader", "1");
    card.innerHTML = `
      <div class="typing-dots">
        <i></i><i></i><i></i>
      </div>
      <span class="typing-label">${escapeHtml(label)}</span>
    `;
    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  function hideArenaLoader(container) {
    if (!container) return;
    container.querySelectorAll("[data-arena-loader]").forEach((el) => el.remove());
  }

  function hideAllLoaders() {
    hideArenaLoader(feedColC);
    hideArenaLoader(feedColA);
    hideArenaLoader(feedColB);
    hideArenaLoader(chatMessagesContainer);
  }

  // -------------------------------------------------------------------------
  // VIEW 2: Direct Agent Sandbox / Chat Room Logic
  // -------------------------------------------------------------------------
  dossierCards.forEach((card) => {
    card.addEventListener("click", () => {
      dossierCards.forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      currentChatTarget = card.getAttribute("data-target") || "triad";
      updateChatHeader(currentChatTarget);
    });
  });

  function updateChatHeader(target) {
    if (target === "triad") {
      chatHeaderAvatar.textContent = "🌐";
      chatHeaderAvatar.className = "agent-avatar avatar-c";
      chatHeaderTitle.textContent = "Triad Council (Collaborative Chat)";
      chatHeaderDesc.textContent = "Supervisor coordinates, Creator drafts solutions, Auditor evaluates.";
    } else if (target === "supervisor") {
      chatHeaderAvatar.textContent = "🧭";
      chatHeaderAvatar.className = "agent-avatar avatar-c";
      chatHeaderTitle.textContent = "Agent C · Supervisor Engine";
      chatHeaderDesc.textContent = "Directive control, agent discovery, quality gatekeeping.";
    } else if (target === "agent_a") {
      chatHeaderAvatar.textContent = "⚡";
      chatHeaderAvatar.className = "agent-avatar avatar-a";
      chatHeaderTitle.textContent = "Agent A · Creator (OpenAI)";
      chatHeaderDesc.textContent = "Technical proposals, Python architecture, implementation code.";
    } else if (target === "agent_b") {
      chatHeaderAvatar.textContent = "🛡️";
      chatHeaderAvatar.className = "agent-avatar avatar-b";
      chatHeaderTitle.textContent = "Agent B · Quality Auditor (Claude)";
      chatHeaderDesc.textContent = "Vulnerability discovery, quantitative scoring, policy compliance.";
    }
  }

  chatSuggestBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      const prompt = btn.getAttribute("data-chat-prompt");
      if (chatInput) {
        chatInput.value = prompt;
        sendChatMessage();
      }
    });
  });

  if (btnChatSend) btnChatSend.addEventListener("click", sendChatMessage);
  if (chatInput) {
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendChatMessage();
      }
    });
  }

  async function sendChatMessage() {
    const message = chatInput ? chatInput.value.trim() : "";
    if (!message) return;
    if (chatInput) chatInput.value = "";

    // Append User Card
    appendChatUserCard(message);
    showArenaLoader(chatMessagesContainer, `${chatHeaderTitle.textContent} is formulating reply...`);

    try {
      if (isStandaloneMode) throw new Error("Autonomous Simulation Mode");

      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_target: currentChatTarget,
          message: message,
          simulation_mode: modeCheckbox ? modeCheckbox.checked : false,
        }),
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to get reply`);
      const data = await res.json();

      hideArenaLoader(chatMessagesContainer);

      if (data.responses && data.responses.length) {
        data.responses.forEach((resp) => {
          appendChatAgentCard(resp.sender, resp.role, resp.reply, resp.tokens);
        });
      }
    } catch (err) {
      hideArenaLoader(chatMessagesContainer);
      if (isStandaloneMode) {
        const simReplies = getSimulatedChatReplies(currentChatTarget, message);
        simReplies.forEach((r) => appendChatAgentCard(r.sender, r.role, r.reply, r.tokens));
      } else {
        appendChatAgentCard("System", "Error", err.message, null);
      }
    }
  }

  function appendChatUserCard(message) {
    removePlaceholder(chatMessagesContainer);
    const card = document.createElement("div");
    card.className = "arena-card card-user";
    card.innerHTML = `
      <div class="arena-card-header">
        <span class="badge-user">OPERATOR</span>
        <span class="bubble-time">${new Date().toLocaleTimeString()}</span>
      </div>
      <div class="arena-card-body">
        ${escapeHtml(message)}
      </div>
    `;
    chatMessagesContainer.appendChild(card);
    setTimeout(() => {
      chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }, 20);
  }

  function getAgentTagClass(sender) {
    const s = (sender || "").toLowerCase();
    if (s.includes("supervisor") || s.includes("agent c") || s.includes("council")) return "tag-c";
    if (s.includes("auditor") || s.includes("agent b") || s.includes("claude") || s.includes("nemotron")) return "tag-b";
    if (s.includes("creator") || s.includes("agent a") || s.includes("openai") || s.includes("laguna")) return "tag-a";
    if (s.includes("error") || s.includes("system")) return "tag-intervene";
    return "tag-c";
  }

  function appendChatAgentCard(sender, role, reply, tokens) {
    removePlaceholder(chatMessagesContainer);
    const card = document.createElement("div");
    card.className = "arena-card";

    const tagClass = getAgentTagClass(sender);
    const tokenBadge = tokens
      ? `<span style="font-family: var(--font-mono); color: var(--text-dim);">${tokens.total_tokens || 0} tokens</span>`
      : "";

    const safeReply = (reply && String(reply).trim()) 
      ? reply 
      : "*(Agent returned an empty reply or is warming up)*";

    card.innerHTML = `
      <div class="arena-card-header">
        <div class="card-title-group">
          <span class="card-step-tag ${tagClass}">${escapeHtml(sender)}</span>
          <span style="font-size: 0.75rem; color: var(--text-muted);">${escapeHtml(role || '')}</span>
        </div>
        <div class="card-meta-right">
          ${tokenBadge}
          <span class="bubble-time">${new Date().toLocaleTimeString()}</span>
        </div>
      </div>
      <div class="arena-card-body">
        ${formatCodeAndMarkdown(safeReply)}
      </div>
    `;

    // Attach copy button handlers if code snippets are returned in chat
    card.querySelectorAll(".btn-copy-code").forEach((btn) => {
      btn.addEventListener("click", () => {
        const codeText = btn.getAttribute("data-code");
        if (codeText) {
          navigator.clipboard.writeText(codeText);
          const origText = btn.innerHTML;
          btn.innerHTML = "<span>✓ Copied!</span>";
          setTimeout(() => (btn.innerHTML = origText), 1800);
        }
      });
    });

    chatMessagesContainer.appendChild(card);
    setTimeout(() => {
      chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
    }, 20);
  }

  // -------------------------------------------------------------------------
  // VIEW 3: SQLite Database Explorer
  // -------------------------------------------------------------------------
  if (dbtabRunsBtn && dbtabAgentsBtn) {
    dbtabRunsBtn.addEventListener("click", () => {
      dbtabRunsBtn.classList.add("active");
      dbtabAgentsBtn.classList.remove("active");
      containerDbtabRuns.style.display = "block";
      containerDbtabAgents.style.display = "none";
    });

    dbtabAgentsBtn.addEventListener("click", () => {
      dbtabAgentsBtn.classList.add("active");
      dbtabRunsBtn.classList.remove("active");
      containerDbtabRuns.style.display = "none";
      containerDbtabAgents.style.display = "block";
    });
  }

  if (btnRefreshDb) {
    btnRefreshDb.addEventListener("click", () => {
      fetchRunsTable();
      fetchAgentsTable();
    });
  }

  async function fetchRunsTable() {
    if (!runsTbody) return;
    try {
      let runs = [];
      if (!isStandaloneMode) {
        try {
          const res = await fetch("/api/runs");
          if (res.ok) runs = await res.json();
        } catch (e) {}
      }

      if (!runs || !runs.length) {
        runs = JSON.parse(localStorage.getItem("nexus_runs") || "[]");
        if (!runs.length) {
          runs = [
            {
              run_id: "run_fin_arch_01",
              task: "Design a resilient, high-throughput financial transaction processing engine with audit logging and rate limiting.",
              status: "COMPLETED (APPROVED)",
              revisions_count: 2,
              total_tokens: 1940,
              total_cost_usd: 0.01684,
              created_at: "2026-09-30 20:05:14",
            },
            {
              run_id: "run_cache_ttl_02",
              task: "Implement an asynchronous in-memory caching utility in Python with TTL expiration and LRU eviction policy.",
              status: "COMPLETED (APPROVED)",
              revisions_count: 1,
              total_tokens: 1250,
              total_cost_usd: 0.00985,
              created_at: "2026-09-30 19:42:30",
            },
          ];
          localStorage.setItem("nexus_runs", JSON.stringify(runs));
        }
      }

      runsTbody.innerHTML = runs.map((r) => `
        <tr>
          <td><code style="color: var(--c-light); font-weight: 700;">${r.run_id}</code></td>
          <td style="max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(r.task)}</td>
          <td>
            <span class="badge-status ${r.status.includes('COMPLETED') ? 'status-completed' : 'status-failed'}">
              ${r.status}
            </span>
          </td>
          <td><strong style="color: var(--text-main);">${r.revisions_count || 1}</strong></td>
          <td><span style="font-family: var(--font-mono);">${(r.total_tokens || 0).toLocaleString()}</span></td>
          <td style="color: var(--a-light); font-weight: 600; font-family: var(--font-mono);">$${(r.total_cost_usd || 0).toFixed(4)}</td>
          <td style="color: var(--text-dim); font-size: 0.75rem;">${r.created_at || 'Recently'}</td>
          <td>
            <button class="btn-inspect-run" data-run-id="${r.run_id}">Inspect Run</button>
          </td>
        </tr>
      `).join("");

      document.querySelectorAll(".btn-inspect-run").forEach((b) => {
        b.addEventListener("click", () => openRunInspector(b.getAttribute("data-run-id")));
      });
    } catch (err) {
      runsTbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color: var(--accent-danger);">Failed to load runs: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  async function fetchAgentsTable() {
    if (!agentsTbody) return;
    try {
      let agents = [];
      if (!isStandaloneMode) {
        try {
          const res = await fetch("/api/agents");
          if (res.ok) agents = await res.json();
        } catch (e) {}
      }

      if (!agents || !agents.length) {
        agents = [
          {
            name: "Agent C (Supervisor)",
            provider: "Nexus Core",
            model: "supervisor-meta-engine",
            role: "Directive Engine & Orchestrator",
            capabilities: ["Capability Discovery", "Task Dispatch", "Token Cost Accounting", "Self-Correction Loop Enforcement"],
            updated_at: "Active (Synced)",
          },
          {
            name: "Agent A (Creator)",
            provider: "OpenAI",
            model: "gpt-4o",
            role: "Primary Implementation Specialist",
            capabilities: ["Technical Drafting", "Python Code Architecture", "API Modeling", "Self-Correction Refinement"],
            updated_at: "Active (Synced)",
          },
          {
            name: "Agent B (Quality Auditor)",
            provider: "Anthropic",
            model: "claude-3-5-sonnet",
            role: "Adversarial Reviewer & Logic Inspector",
            capabilities: ["Critical Logic Audit", "Vulnerability Discovery", "Quantitative Scoring (0-100)", "Actionable Defect Formulation"],
            updated_at: "Active (Synced)",
          },
        ];
      }

      agentsTbody.innerHTML = agents.map((a) => `
        <tr>
          <td><strong style="color: var(--text-main);">${escapeHtml(a.name)}</strong></td>
          <td>${escapeHtml(a.provider)}</td>
          <td><code style="color: var(--c-light);">${escapeHtml(a.model)}</code></td>
          <td>${escapeHtml(a.role)}</td>
          <td>
            <div style="display: flex; flex-wrap: wrap; gap: 4px;">
              ${(a.capabilities || []).map((c) => `<span class="dossier-tag">${escapeHtml(c)}</span>`).join("")}
            </div>
          </td>
          <td style="color: var(--a-light); font-size: 0.75rem;">${a.updated_at || 'Active'}</td>
        </tr>
      `).join("");
    } catch (err) {
      agentsTbody.innerHTML = `<tr><td colspan="6" class="text-center" style="color: var(--accent-danger);">Failed to load registry: ${escapeHtml(err.message)}</td></tr>`;
    }
  }

  async function openRunInspector(runId) {
    if (!runModal) return;
    runModal.style.display = "flex";
    modalRunTitle.textContent = `Run Telemetry Inspector: ${runId}`;
    modalRunBody.innerHTML = `<p class="text-dim">Retrieving execution audit log from SQLite...</p>`;

    try {
      let r = null;
      let steps = [];
      let evals = [];

      if (!isStandaloneMode) {
        try {
          const res = await fetch(`/api/runs/${runId}`);
          if (res.ok) {
            const data = await res.json();
            r = data.run;
            steps = data.steps || [];
            evals = data.evaluations || [];
          }
        } catch (e) {}
      }

      if (!r) {
        const localRuns = JSON.parse(localStorage.getItem("nexus_runs") || "[]");
        r = localRuns.find((item) => item.run_id === runId) || {
          run_id: runId,
          task: "Autonomous Multi-Agent Task Execution",
          status: "COMPLETED (APPROVED)",
          total_tokens: 1940,
          total_cost_usd: 0.01684,
        };
        steps = [
          { step_index: 1, sender: "Agent C (Supervisor)", receiver: "Agent A & B", action: "CAPABILITY_DISCOVERY", content: "Discovered and registered OpenAI & Claude capabilities", cost_usd: 0.0011 },
          { step_index: 2, sender: "Agent A (Creator)", receiver: "Agent C (Supervisor)", action: "DRAFT_REV_1", content: "Initial code architecture submitted for evaluation", cost_usd: 0.0038 },
          { step_index: 3, sender: "Agent B (Auditor)", receiver: "Agent C (Supervisor)", action: "AUDIT_REV_1", content: "Quality score 65/100 (REJECTED). Missing idempotency protection.", cost_usd: 0.0041 },
          { step_index: 4, sender: "Agent C (Supervisor)", receiver: "Agent A (Creator)", action: "INTERVENTION", content: "Supervisory directive: Execute Revision 2 addressing audit feedback.", cost_usd: 0.0000 },
          { step_index: 5, sender: "Agent A (Creator)", receiver: "Agent C (Supervisor)", action: "DRAFT_REV_2", content: "Refined deliverable incorporating Redis token locks and idempotency keys.", cost_usd: 0.0046 },
          { step_index: 6, sender: "Agent B (Auditor)", receiver: "Agent C (Supervisor)", action: "AUDIT_REV_2", content: "Quality score 94/100 (APPROVED). Production ready.", cost_usd: 0.0039 },
        ];
        evals = [
          { revision: 1, score: 65, passed: false, actionable_feedback: "Implement Redis token-bucket rate limiting and atomic idempotency keys with rollback capability." },
          { revision: 2, score: 94, passed: true, actionable_feedback: "Fully compliant with enterprise resilience standards. Approved for immediate deployment." },
        ];
      }

      modalRunBody.innerHTML = `
        <div style="background: rgba(0,0,0,0.4); padding: 16px; border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);">
          <div style="font-size: 0.88rem; font-weight: 700; color: var(--text-main); margin-bottom: 6px;">Objective:</div>
          <div style="color: #cbd5e1; font-size: 0.85rem; line-height: 1.5;">${escapeHtml(r.task)}</div>
          <div style="display: flex; gap: 16px; margin-top: 12px; font-size: 0.78rem;">
            <span>Status: <strong style="color: var(--a-light);">${r.status}</strong></span>
            <span>Tokens: <strong style="font-family: var(--font-mono); color: var(--c-light);">${(r.total_tokens || 0).toLocaleString()}</strong></span>
            <span>Cost: <strong style="font-family: var(--font-mono); color: var(--a-light);">$${(r.total_cost_usd || 0).toFixed(4)}</strong></span>
          </div>
        </div>

        <div>
          <h4 style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px;">Execution Steps (${steps.length}):</h4>
          <div style="display: flex; flex-direction: column; gap: 8px; max-height: 240px; overflow-y: auto;">
            ${steps.map((s) => `
              <div style="background: rgba(255,255,255,0.02); padding: 10px 14px; border-radius: var(--radius-xs); border-left: 3px solid var(--c-pri); font-size: 0.78rem;">
                <div style="display: flex; justify-content: space-between; font-weight: 700; margin-bottom: 4px;">
                  <span>Step ${s.step_index}: ${escapeHtml(s.sender)} ➔ ${escapeHtml(s.receiver)} [${escapeHtml(s.action)}]</span>
                  <span style="color: var(--a-light); font-family: var(--font-mono);">$${(s.cost_usd || 0).toFixed(4)}</span>
                </div>
                <div style="color: var(--text-muted);">${escapeHtml(s.content)}</div>
              </div>
            `).join("")}
          </div>
        </div>

        ${evals.length ? `
          <div>
            <h4 style="font-size: 0.85rem; font-weight: 700; text-transform: uppercase; color: var(--text-dim); margin-bottom: 8px;">Quality Audits (${evals.length}):</h4>
            <div style="display: flex; flex-direction: column; gap: 8px;">
              ${evals.map((e) => `
                <div style="background: rgba(255,255,255,0.02); padding: 10px 14px; border-radius: var(--radius-xs); border-left: 3px solid ${e.passed ? 'var(--a-pri)' : 'var(--accent-danger)'}; font-size: 0.78rem;">
                  <strong>Revision ${e.revision} Evaluation:</strong>
                  Score <span style="font-weight: 800; color: ${e.passed ? 'var(--a-light)' : 'var(--accent-danger)'};">${e.score}/100</span> [${e.passed ? 'PASSED' : 'FAILED'}]
                  <div style="font-style: italic; color: #cbd5e1; margin-top: 4px;">"${escapeHtml(e.actionable_feedback)}"</div>
                </div>
              `).join("")}
            </div>
          </div>
        ` : ''}
      `;
    } catch (err) {
      modalRunBody.innerHTML = `<p style="color: var(--accent-danger);">Error: ${escapeHtml(err.message)}</p>`;
    }
  }

  if (modalCloseBtn) {
    modalCloseBtn.addEventListener("click", () => {
      runModal.style.display = "none";
    });
  }

  // -------------------------------------------------------------------------
  // Backend Health & Standalone Fallback Engine
  // -------------------------------------------------------------------------
  async function checkBackendHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const data = await res.json();
      isStandaloneMode = false;
      if (systemStatusDot) systemStatusDot.style.background = "var(--accent-success)";
      if (systemStatusText) systemStatusText.textContent = "ONLINE (SERVER)";
      if (modeText) modeText.textContent = data.has_openai_key ? "Live API Mode" : "Simulation Mode";
    } catch (err) {
      isStandaloneMode = true;
      if (systemStatusDot) systemStatusDot.style.background = "var(--c-light)";
      if (systemStatusText) systemStatusText.textContent = "AUTONOMOUS (READY)";
      if (modeCheckbox) modeCheckbox.checked = true;
      if (modeText) modeText.textContent = "Autonomous Simulation";
    }
  }

  // Autonomous Client-Side Simulation for Offline / Standalone
  function runClientAutonomousWorkflow(task, modelA, modelB, threshold) {
    const runId = "run_" + Math.random().toString(36).substring(2, 9);
    if (activeRunIdEl) activeRunIdEl.textContent = runId;

    let totalSimTokens = 0;
    let totalSimCost = 0.0;

    // Step 1: Handshake (0.5s)
    setTimeout(() => {
      handleStreamPayload({
        event: "agent_registered",
        run_id: runId,
        agent: {
          name: "Agent A (Creator)",
          provider: "OpenAI",
          model: modelA,
          role: "Technical Implementer & Builder",
          capabilities: ["Code Generation", "System Architecture", "Self-Correction Refinement"],
        },
        step: { token_usage: { prompt_tokens: 45, completion_tokens: 40, total_tokens: 85, cost_usd: 0.0006 } },
      });

      handleStreamPayload({
        event: "agent_registered",
        run_id: runId,
        agent: {
          name: "Agent B (Quality Auditor)",
          provider: "Anthropic",
          model: modelB,
          role: "Adversarial Inspector & Quality Gate",
          capabilities: ["Critical Audit", "Vulnerability Stress-testing", "Quantitative Scoring (0-100)"],
        },
        step: { token_usage: { prompt_tokens: 40, completion_tokens: 35, total_tokens: 75, cost_usd: 0.0005 } },
      });

      // Step 2: Agent A Rev 1 Draft (1.8s)
      setTimeout(() => {
        totalSimTokens += 430;
        totalSimCost += 0.0038;
        handleStreamPayload({
          event: "draft_produced",
          run_id: runId,
          revision: 1,
          draft: `### Initial Technical Architecture (Revision 1 - OpenAI GPT-4o)\n\nObjective: ${task}\n\n\`\`\`python\nclass CoreEngine:\n    def __init__(self):\n        self.transaction_queue = []\n\n    def process_transaction(self, tx_id: str, payload: dict):\n        # In-memory execution\n        self.transaction_queue.append(payload)\n        return {"status": "SUCCESS", "tx_id": tx_id}\n\`\`\`\n\n• High performance in-memory queue.\n• Fast synchronous response. Ready for Claude auditing.`,
          tokens: { prompt_tokens: 150, completion_tokens: 280, total_tokens: 430, cost_usd: 0.0038 },
          total_tokens: totalSimTokens,
          total_cost_usd: totalSimCost,
        });

        // Step 3: Agent B Audits Rev 1 with Flaws (Score 65 < threshold) (3.6s)
        setTimeout(() => {
          totalSimTokens += 385;
          totalSimCost += 0.0041;
          handleStreamPayload({
            event: "audit_completed",
            run_id: runId,
            revision: 1,
            evaluation: {
              score: 65,
              passed: false,
              strengths: ["Clean syntax and minimal overhead", "Sub-millisecond processing on local queue"],
              flaws: [
                "Zero idempotency validation: duplicate requests cause double-spend.",
                "Missing token-bucket rate limiter: vulnerable to traffic spikes.",
                "In-memory state without persistent write-ahead logging.",
              ],
              actionable_feedback: "Wrap processing inside atomic Redis idempotency keys (24-hr TTL) and implement distributed token-bucket rate limiting before production deployment.",
              token_usage: { prompt_tokens: 140, completion_tokens: 245, total_tokens: 385, cost_usd: 0.0041 },
            },
            total_tokens: totalSimTokens,
            total_cost_usd: totalSimCost,
          });

          // Step 4: Supervisor Intervenes (5.0s)
          setTimeout(() => {
            totalSimTokens += 80;
            handleStreamPayload({
              event: "supervisor_intervention",
              run_id: runId,
              revision: 1,
              score: 65,
              step: { token_usage: { prompt_tokens: 45, completion_tokens: 35, total_tokens: 80, cost_usd: 0.0000 } },
              total_tokens: totalSimTokens,
              total_cost_usd: totalSimCost,
            });

            // Step 5: Agent A Refines Rev 2 with Fixes (6.8s)
            setTimeout(() => {
              totalSimTokens += 520;
              totalSimCost += 0.0046;
              handleStreamPayload({
                event: "draft_produced",
                run_id: runId,
                revision: 2,
                draft: `### Production Deliverable (Revision 2 - OpenAI GPT-4o)\n\n*Incorporating Supervisor Directive & Claude 3.5 Sonnet Audit Feedback*\n\n\`\`\`python\nimport time\nimport redis\nfrom dataclasses import dataclass\n\n@dataclass\nclass ProcessedResult:\n    tx_id: str\n    status: str\n    cached: bool\n\nclass ResilientEngine:\n    def __init__(self, redis_client):\n        self.redis = redis_client\n        self.rate_limit_per_sec = 100\n\n    def process_with_idempotency(self, idempotency_key: str, payload: dict) -> ProcessedResult:\n        # 1. Idempotency Check (TTL 24 hours)\n        if self.redis.exists(f"idemp:{idempotency_key}"):\n            return ProcessedResult(idempotency_key, "ALREADY_PROCESSED", True)\n\n        # 2. Redis Token-Bucket Rate Limiter\n        current = self.redis.incr(f"ratelimit:{int(time.time())}")\n        if current > self.rate_limit_per_sec:\n            raise RuntimeError("Rate limit exceeded (HTTP 429)")\n\n        # 3. Atomic Execution & Ledger Journaling\n        with self.redis.pipeline() as pipe:\n            pipe.setex(f"idemp:{idempotency_key}", 86400, "SETTLED")\n            pipe.rpush("audit_log", str(payload))\n            pipe.execute()\n\n        return ProcessedResult(idempotency_key, "SETTLED", False)\n\`\`\`\n\n• **All Objections Resolved:** Idempotency keys enforced, distributed token-bucket rate limiting applied, atomic pipeline logging.`,
                tokens: { prompt_tokens: 180, completion_tokens: 340, total_tokens: 520, cost_usd: 0.0046 },
                total_tokens: totalSimTokens,
                total_cost_usd: totalSimCost,
              });

              // Step 6: Agent B Approves Rev 2 (Score 94) (8.6s)
              setTimeout(() => {
                totalSimTokens += 360;
                totalSimCost += 0.0039;
                handleStreamPayload({
                  event: "audit_completed",
                  run_id: runId,
                  revision: 2,
                  evaluation: {
                    score: 94,
                    passed: true,
                    strengths: [
                      "Full idempotency protection with 24-hr TTL prevents duplicate execution.",
                      "Token-bucket rate limiting correctly protects downstream workers.",
                      "Atomic pipeline guarantees zero log desync.",
                    ],
                    flaws: [],
                    actionable_feedback: "Fully compliant with enterprise resilience standards. Approved for immediate deployment.",
                    token_usage: { prompt_tokens: 130, completion_tokens: 230, total_tokens: 360, cost_usd: 0.0039 },
                  },
                  total_tokens: totalSimTokens,
                  total_cost_usd: totalSimCost,
                });

                // Step 7: Supervisor Final Approval & SQLite Seal (9.8s)
                setTimeout(() => {
                  handleStreamPayload({
                    event: "workflow_completed",
                    run_id: runId,
                    final_score: 94,
                    revisions: 2,
                    total_tokens: totalSimTokens,
                    total_cost_usd: totalSimCost,
                    step: { token_usage: { prompt_tokens: 40, completion_tokens: 30, total_tokens: 70, cost_usd: 0.0000 } },
                  });

                  // Save into LocalStorage for Database View
                  saveLocalRunRecord({
                    run_id: runId,
                    task: task,
                    status: "COMPLETED (APPROVED)",
                    revisions_count: 2,
                    total_tokens: totalSimTokens,
                    total_cost_usd: totalSimCost,
                    created_at: new Date().toISOString().replace("T", " ").substring(0, 19),
                  });
                }, 1200);
              }, 1800);
            }, 1800);
          }, 1400);
        }, 1800);
      }, 1800);
    }, 600);
  }

  function saveLocalRunRecord(runObj) {
    try {
      const runs = JSON.parse(localStorage.getItem("nexus_runs") || "[]");
      runs.unshift(runObj);
      localStorage.setItem("nexus_runs", JSON.stringify(runs.slice(0, 30)));
    } catch (e) {}
  }

  function getSimulatedChatReplies(target, message) {
    const p = message.toLowerCase();
    if (target === "agent_a") {
      return [
        {
          sender: "Agent A (Creator)",
          role: "OpenAI Implementer",
          reply: `Here is a technical draft addressing: "${message}"\n\n\`\`\`python\nclass SolutionWorker:\n    def __init__(self):\n        self.initialized = True\n\n    def execute(self, payload: dict):\n        return {"status": "SUCCESS", "data": payload}\n\`\`\`\n• Modular architecture designed for high availability and low latency.`,
          tokens: { total_tokens: 380, cost_usd: 0.0034 },
        },
      ];
    } else if (target === "agent_b") {
      return [
        {
          sender: "Agent B (Quality Auditor)",
          role: "Claude Logic Inspector",
          reply: `### Claude Quality Evaluation\n\n**Quality Score: 91 / 100 [PASSED]**\n\n• **Logic Review:** Requirements are satisfied with appropriate boundary checks.\n• **Risk Assessment:** Recommended to verify concurrency limits and network retry jitter.`,
          tokens: { total_tokens: 340, cost_usd: 0.0037 },
        },
      ];
    } else if (target === "supervisor") {
      return [
        {
          sender: "Agent C (Supervisor)",
          role: "Meta-Orchestrator",
          reply: `Objective received: "${message}". Both Agent A (Creator) and Agent B (Auditor) are synchronized. You can click "Launch Workflow" on the Multi-Agent Studio tab to execute the full discovery, drafting, and audit loop!`,
          tokens: { total_tokens: 160, cost_usd: 0.0000 },
        },
      ];
    } else {
      // Triad
      return [
        {
          sender: "Agent C (Supervisor)",
          role: "Meta-Orchestrator",
          reply: `Triad inquiry received: "${message}". Assigning initial technical formulation to Agent A.`,
          tokens: { total_tokens: 90, cost_usd: 0.0000 },
        },
        {
          sender: "Agent A (Creator)",
          role: "OpenAI Implementer",
          reply: `I have architected the solution with an asynchronous queue and atomic locks.`,
          tokens: { total_tokens: 280, cost_usd: 0.0026 },
        },
        {
          sender: "Agent B (Quality Auditor)",
          role: "Claude Logic Inspector",
          reply: `Audit score 92/100. Concurrency safeguards and latency SLA benchmarks verified.`,
          tokens: { total_tokens: 240, cost_usd: 0.0028 },
        },
      ];
    }
  }
});
