// Agent Nexus - 3-Screen Multi-Agent Orchestration Engine
document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs
  const tabBtns = document.querySelectorAll(".nav-tab");
  const tabContents = document.querySelectorAll(".tab-content");

  // Header Telemetry
  const systemStatusEl = document.getElementById("system-status");
  const globalTokensEl = document.getElementById("global-tokens");
  const globalCostEl = document.getElementById("global-cost");
  const modeCheckbox = document.getElementById("mode-checkbox");
  const modeLabel = document.getElementById("mode-label");

  // Screen C Elements (Supervisor)
  const agentCState = document.getElementById("agent-c-state");
  const agentCDirectives = document.getElementById("agent-c-directives");
  const agentCTokens = document.getElementById("agent-c-tokens");
  const agentCCost = document.getElementById("agent-c-cost");
  const feedScreenC = document.getElementById("feed-screen-c");
  const supervisorTaskInput = document.getElementById("supervisor-task-input") || document.getElementById("input-chat-c");
  const thresholdSlider = document.getElementById("threshold-slider");
  const thresholdVal = document.getElementById("threshold-val");
  const selModelA = document.getElementById("sel-model-a");
  const selModelB = document.getElementById("sel-model-b");
  const btnRunWorkflow = document.getElementById("btn-run-workflow");
  const btnRunText = document.getElementById("btn-text");
  const currentRunPill = document.getElementById("current-run-pill");
  const btnSendC = document.getElementById("btn-send-c");
  const btnClearFeedC = document.getElementById("btn-clear-feed-c");

  // Screen A Elements (OpenAI)
  const agentAState = document.getElementById("agent-a-state");
  const agentATokens = document.getElementById("agent-a-tokens");
  const agentACost = document.getElementById("agent-a-cost");
  const screenAModelTag = document.getElementById("screen-a-model-tag");
  const feedScreenA = document.getElementById("feed-screen-a");
  const inputChatA = document.getElementById("input-chat-a");
  const btnSendA = document.getElementById("btn-send-a");
  const btnClearFeedA = document.getElementById("btn-clear-feed-a");
  const promptChipsA = document.querySelectorAll(".prompt-chip-a");

  // Screen B Elements (Claude)
  const agentBState = document.getElementById("agent-b-state");
  const agentBTokens = document.getElementById("agent-b-tokens");
  const agentBCost = document.getElementById("agent-b-cost");
  const screenBModelTag = document.getElementById("screen-b-model-tag");
  const feedScreenB = document.getElementById("feed-screen-b");
  const inputChatB = document.getElementById("input-chat-b");
  const btnSendB = document.getElementById("btn-send-b");
  const btnClearFeedB = document.getElementById("btn-clear-feed-b");
  const promptChipsB = document.querySelectorAll(".prompt-chip-b");

  // 3-Screen Split View Elements
  const splitRunId = document.getElementById("split-run-id");
  const splitStateC = document.getElementById("split-state-c");
  const splitStateA = document.getElementById("split-state-a");
  const splitStateB = document.getElementById("split-state-b");
  const splitFeedC = document.getElementById("split-feed-c");
  const splitFeedA = document.getElementById("split-feed-a");
  const splitFeedB = document.getElementById("split-feed-b");
  const inputSplitTask = document.getElementById("input-split-task");
  const btnSplitRun = document.getElementById("btn-split-run");

  // Scenario chips in Screen C
  const scenarioChips = document.querySelectorAll(".chip-btn");

  // Database Tab Elements
  const btnRefreshDb = document.getElementById("btn-refresh-db");
  const runsTbody = document.getElementById("runs-tbody");
  const agentsTbody = document.getElementById("agents-tbody");
  const dbSubtabs = document.querySelectorAll(".subtab-btn");
  const dbTabContents = document.querySelectorAll(".dbtab-content");

  // Modal Elements
  const runModal = document.getElementById("run-modal");
  const modalClose = document.getElementById("modal-close");
  const modalTitle = document.getElementById("modal-title");
  const modalContent = document.getElementById("modal-content");

  // State
  let globalTotalTokens = 0;
  let globalTotalCost = 0.0;
  let agentATotalTokens = 0;
  let agentATotalCost = 0.0;
  let agentBTotalTokens = 0;
  let agentBTotalCost = 0.0;
  let agentCTotalTokens = 0;
  let agentCTotalCost = 0.0;
  let supervisorDirectivesCount = 0;
  let activeEventSource = null;
  let isStandaloneMode = false;

  // Initialize
  checkSystemHealth();
  fetchDbAgents();

  // Tab Switching
  tabBtns.forEach(btn => {
    btn.addEventListener("click", () => {
      tabBtns.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const targetId = btn.getAttribute("data-tab");
      const targetContent = document.getElementById(targetId);
      if (targetContent) {
        targetContent.classList.add("active");
      }

      if (targetId === "tab-database") {
        fetchDbRuns();
        fetchDbAgents();
      }
    });
  });

  // DB Subtabs
  dbSubtabs.forEach(btn => {
    btn.addEventListener("click", () => {
      dbSubtabs.forEach(b => b.classList.remove("active"));
      dbTabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      const targetSub = document.getElementById(btn.getAttribute("data-dbtab"));
      if (targetSub) targetSub.classList.add("active");
    });
  });

  // Mode Toggle
  if (modeCheckbox) {
    modeCheckbox.addEventListener("change", (e) => {
      if (modeLabel) modeLabel.textContent = e.target.checked ? "Simulation Mode" : "Live API Mode";
    });
  }

  // Threshold Slider
  if (thresholdSlider && thresholdVal) {
    thresholdSlider.addEventListener("input", (e) => {
      thresholdVal.textContent = e.target.value;
    });
  }

  // Scenario Chips
  scenarioChips.forEach(chip => {
    chip.addEventListener("click", () => {
      const taskText = chip.getAttribute("data-task");
      if (supervisorTaskInput) {
        supervisorTaskInput.value = taskText;
        supervisorTaskInput.focus();
      }
      if (inputSplitTask) {
        inputSplitTask.value = taskText;
      }
    });
  });

  // Screen Clear Buttons
  if (btnClearFeedA) btnClearFeedA.addEventListener("click", () => { if (feedScreenA) feedScreenA.innerHTML = ""; });
  if (btnClearFeedB) btnClearFeedB.addEventListener("click", () => { if (feedScreenB) feedScreenB.innerHTML = ""; });
  if (btnClearFeedC) btnClearFeedC.addEventListener("click", () => { if (feedScreenC) feedScreenC.innerHTML = ""; });

  // ==========================================
  // SCREEN A: Direct Chat with Agent A (OpenAI)
  // ==========================================
  promptChipsA.forEach(chip => {
    chip.addEventListener("click", () => {
      if (inputChatA) {
        inputChatA.value = chip.getAttribute("data-prompt");
        inputChatA.focus();
      }
    });
  });

  if (inputChatA) {
    inputChatA.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendPromptToAgentA();
      }
    });
  }

  if (btnSendA) {
    btnSendA.addEventListener("click", () => {
      sendPromptToAgentA();
    });
  }

  async function sendPromptToAgentA() {
    if (!inputChatA) return;
    const message = inputChatA.value.trim();
    if (!message) {
      inputChatA.focus();
      return;
    }

    inputChatA.value = "";
    if (btnSendA) {
      btnSendA.disabled = true;
      btnSendA.innerHTML = '<span class="btn-icon">⏳</span><span>Generating...</span>';
    }
    if (agentAState) {
      agentAState.textContent = "GENERATING";
      agentAState.className = "agent-state-pill running";
    }
    if (splitStateA) {
      splitStateA.textContent = "GENERATING";
      splitStateA.className = "agent-state-pill running";
    }

    appendMessageCard(feedScreenA, "You", "You", message, null, "user");
    appendMessageCard(splitFeedA, "You", "You", message, null, "user");
    showLoader([feedScreenA, splitFeedA], "Laguna is writing…");

    try {
      if (isStandaloneMode) throw new Error("Standalone Netlify Mode");
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_target: "agent_a",
          message: message,
          simulation_mode: modeCheckbox ? modeCheckbox.checked : false
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to get response`);
      const data = await res.json();
      if (data.responses && data.responses.length) {
        const resp = data.responses[0];
        appendMessageCard(feedScreenA, resp.sender, "Reply", resp.reply, resp.tokens, "agent-a");
        appendMessageCard(splitFeedA, resp.sender, "Reply", resp.reply, resp.tokens, "agent-a");

        if (resp.tokens) {
          updateAgentATelemetry(resp.tokens);
        }
      }
    } catch (err) {
      if (!isStandaloneMode) {
        appendMessageCard(feedScreenA, "Agent A (OpenAI)", "Error", err.message, null, "agent-a");
        appendMessageCard(splitFeedA, "Agent A (OpenAI)", "Error", err.message, null, "agent-a");
      } else {
        const simResp = getSimulatedAgentAReply(message);
        appendMessageCard(feedScreenA, "Agent A (OpenAI)", "Deliverable (Autonomous)", simResp.reply, simResp.tokens, "agent-a");
        appendMessageCard(splitFeedA, "Agent A (OpenAI)", "Deliverable (Autonomous)", simResp.reply, simResp.tokens, "agent-a");
        if (simResp.tokens) updateAgentATelemetry(simResp.tokens);
      }
    } finally {
      hideLoader([feedScreenA, splitFeedA]);
      if (btnSendA) {
        btnSendA.disabled = false;
        btnSendA.innerHTML = '<span class="btn-icon">➤</span><span>Prompt Agent A</span>';
      }
      if (agentAState) {
        agentAState.textContent = "READY";
        agentAState.className = "agent-state-pill";
      }
      if (splitStateA) {
        splitStateA.textContent = "READY";
        splitStateA.className = "agent-state-pill";
      }
      if (inputChatA) inputChatA.focus();
    }
  }

  // ==========================================
  // SCREEN B: Direct Chat with Agent B (Claude)
  // ==========================================
  promptChipsB.forEach(chip => {
    chip.addEventListener("click", () => {
      if (inputChatB) {
        inputChatB.value = chip.getAttribute("data-prompt");
        inputChatB.focus();
      }
    });
  });

  if (inputChatB) {
    inputChatB.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendPromptToAgentB();
      }
    });
  }

  if (btnSendB) {
    btnSendB.addEventListener("click", () => {
      sendPromptToAgentB();
    });
  }

  async function sendPromptToAgentB() {
    if (!inputChatB) return;
    const message = inputChatB.value.trim();
    if (!message) {
      inputChatB.focus();
      return;
    }

    inputChatB.value = "";
    if (btnSendB) {
      btnSendB.disabled = true;
      btnSendB.innerHTML = '<span class="btn-icon">⏳</span><span>Auditing...</span>';
    }
    if (agentBState) {
      agentBState.textContent = "AUDITING";
      agentBState.className = "agent-state-pill running";
    }
    if (splitStateB) {
      splitStateB.textContent = "AUDITING";
      splitStateB.className = "agent-state-pill running";
    }

    appendMessageCard(feedScreenB, "You", "You", message, null, "user");
    appendMessageCard(splitFeedB, "You", "You", message, null, "user");
    showLoader([feedScreenB, splitFeedB], "Nemotron is writing…");

    try {
      if (isStandaloneMode) throw new Error("Standalone Netlify Mode");
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_target: "agent_b",
          message: message,
          simulation_mode: modeCheckbox ? modeCheckbox.checked : false
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to get response`);
      const data = await res.json();
      if (data.responses && data.responses.length) {
        const resp = data.responses[0];
        appendMessageCard(feedScreenB, resp.sender, "Reply", resp.reply, resp.tokens, "agent-b");
        appendMessageCard(splitFeedB, resp.sender, "Reply", resp.reply, resp.tokens, "agent-b");

        if (resp.tokens) {
          updateAgentBTelemetry(resp.tokens);
        }
      }
    } catch (err) {
      if (!isStandaloneMode) {
        appendMessageCard(feedScreenB, "Agent B (Claude)", "Error", err.message, null, "agent-b");
        appendMessageCard(splitFeedB, "Agent B (Claude)", "Error", err.message, null, "agent-b");
      } else {
        const simResp = getSimulatedAgentBReply(message);
        appendMessageCard(feedScreenB, "Agent B (Claude)", "Audit & Analysis (Autonomous)", simResp.reply, simResp.tokens, "agent-b");
        appendMessageCard(splitFeedB, "Agent B (Claude)", "Audit & Analysis (Autonomous)", simResp.reply, simResp.tokens, "agent-b");
        if (simResp.tokens) updateAgentBTelemetry(simResp.tokens);
      }
    } finally {
      hideLoader([feedScreenB, splitFeedB]);
      if (btnSendB) {
        btnSendB.disabled = false;
        btnSendB.innerHTML = '<span class="btn-icon">➤</span><span>Prompt Agent B</span>';
      }
      if (agentBState) {
        agentBState.textContent = "READY";
        agentBState.className = "agent-state-pill";
      }
      if (splitStateB) {
        splitStateB.textContent = "READY";
        splitStateB.className = "agent-state-pill";
      }
      if (inputChatB) inputChatB.focus();
    }
  }

  // =========================================================================
  // SCREEN C: Supervisor Multi-Agent Flow & Direct Chat
  // =========================================================================
  if (supervisorTaskInput) {
    supervisorTaskInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (e.ctrlKey || e.metaKey) {
          sendPromptToSupervisor();
        } else {
          startMultiAgentWorkflow();
        }
      }
    });
  }

  if (btnRunWorkflow) {
    btnRunWorkflow.addEventListener("click", () => {
      startMultiAgentWorkflow();
    });
  }

  if (btnSendC) {
    btnSendC.addEventListener("click", () => {
      sendPromptToSupervisor();
    });
  }

  // Split View Launcher
  if (btnSplitRun) {
    btnSplitRun.addEventListener("click", () => {
      const task = inputSplitTask ? inputSplitTask.value.trim() : "";
      startMultiAgentWorkflow(task);
    });
  }

  if (inputSplitTask) {
    inputSplitTask.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        startMultiAgentWorkflow(inputSplitTask.value.trim());
      }
    });
  }

  async function sendPromptToSupervisor(customMsg) {
    const message = customMsg || (supervisorTaskInput ? supervisorTaskInput.value.trim() : "");
    if (!message) {
      if (supervisorTaskInput) supervisorTaskInput.focus();
      return;
    }

    if (supervisorTaskInput) supervisorTaskInput.value = "";
    if (btnSendC) {
      btnSendC.disabled = true;
      btnSendC.innerHTML = '<span class="btn-icon">⏳</span><span>Thinking...</span>';
    }
    if (agentCState) {
      agentCState.textContent = "SUPERVISING";
      agentCState.className = "agent-state-pill running";
    }
    if (splitStateC) {
      splitStateC.textContent = "SUPERVISING";
      splitStateC.className = "agent-state-pill running";
    }

    appendMessageCard(feedScreenC, "You", "You", message, null, "user");
    appendMessageCard(splitFeedC, "You", "You", message, null, "user");
    showLoader([feedScreenC, splitFeedC], "Supervisor is writing…");

    try {
      if (isStandaloneMode) throw new Error("Standalone Netlify Mode");
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_target: "supervisor",
          message: message,
          simulation_mode: modeCheckbox ? modeCheckbox.checked : false
        })
      });

      if (!res.ok) throw new Error(`HTTP ${res.status}: Failed to get response`);
      const data = await res.json();
      if (data.responses && data.responses.length) {
        const resp = data.responses[0];
        appendMessageCard(feedScreenC, resp.sender, "Reply", resp.reply, resp.tokens, "agent-c");
        appendMessageCard(splitFeedC, resp.sender, "Reply", resp.reply, resp.tokens, "agent-c");

        if (resp.tokens) {
          updateAgentCTelemetry(resp.tokens);
        }
      }
    } catch (err) {
      if (!isStandaloneMode) {
        appendMessageCard(feedScreenC, "Agent C (Supervisor)", "Error", err.message, null, "agent-c");
        appendMessageCard(splitFeedC, "Agent C (Supervisor)", "Error", err.message, null, "agent-c");
      } else {
        const simResp = getSimulatedSupervisorReply(message);
        appendMessageCard(feedScreenC, "Agent C (Supervisor)", "Supervisor Directive (Autonomous)", simResp.reply, simResp.tokens, "agent-c");
        appendMessageCard(splitFeedC, "Agent C (Supervisor)", "Supervisor Directive (Autonomous)", simResp.reply, simResp.tokens, "agent-c");
        if (simResp.tokens) updateAgentCTelemetry(simResp.tokens);
      }
    } finally {
      hideLoader([feedScreenC, splitFeedC]);
      if (btnSendC) {
        btnSendC.disabled = false;
        btnSendC.innerHTML = '<span class="btn-icon">💬</span><span>Chat</span>';
      }
      if (agentCState) {
        agentCState.textContent = "STANDBY";
        agentCState.className = "agent-state-pill";
      }
      if (splitStateC) {
        splitStateC.textContent = "STANDBY";
        splitStateC.className = "agent-state-pill";
      }
      if (supervisorTaskInput) supervisorTaskInput.focus();
    }
  }

  async function startMultiAgentWorkflow(customTask) {
    let task = customTask || (supervisorTaskInput ? supervisorTaskInput.value.trim() : "");
    if (!task) {
      task = "Design a resilient, high-throughput financial transaction processing engine with audit logging and rate limiting.";
      if (supervisorTaskInput) supervisorTaskInput.value = task;
    }

    if (btnRunWorkflow) {
      btnRunWorkflow.disabled = true;
      btnRunWorkflow.innerHTML = '<span class="btn-icon">⏳</span><span>Orchestrating...</span>';
    }
    if (btnSplitRun) {
      btnSplitRun.disabled = true;
      btnSplitRun.innerHTML = '<span class="btn-icon">⏳</span><span>Running Flow...</span>';
    }

    if (agentCState) {
      agentCState.textContent = "DISCOVERY";
      agentCState.className = "agent-state-pill running";
    }
    if (splitStateC) {
      splitStateC.textContent = "DISCOVERY";
      splitStateC.className = "agent-state-pill running";
    }

    const simMode = modeCheckbox ? modeCheckbox.checked : false;
    const modelA = selModelA ? selModelA.value : "poolside/laguna-s-2.1:free";
    const modelB = selModelB ? selModelB.value : "nvidia/nemotron-3-ultra-550b-a55b:free";
    const threshold = thresholdSlider ? parseInt(thresholdSlider.value, 10) : 80;

    if (screenAModelTag) screenAModelTag.textContent = modelA;
    if (screenBModelTag) screenBModelTag.textContent = modelB;

    const runFeeds = [feedScreenC, splitFeedC, feedScreenA, splitFeedA, feedScreenB, splitFeedB];
    showLoader(runFeeds, "Starting Laguna and Nemotron…");
    try {
      if (isStandaloneMode) throw new Error("Standalone Netlify Mode");
      const res = await fetch("/api/orchestrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          task,
          simulation_mode: simMode,
          model_a: modelA,
          model_b: modelB,
          quality_threshold: threshold
        })
      });

      if (!res.ok) {
        let detail = "Failed to initialize orchestration run";
        try {
          const body = await res.json();
          detail = body.detail || detail;
        } catch (parseErr) { /* keep detail */ }
        throw new Error(detail);
      }
      const resData = await res.json();
      const runId = resData.run_id;

      if (currentRunPill) currentRunPill.textContent = runId;
      if (splitRunId) splitRunId.textContent = runId;

      connectOrchestrationStream(runId);
    } catch (err) {
      if (isStandaloneMode) {
        runClientSideSimulationWorkflow(task, modelA, modelB, threshold);
        return;
      }
      hideLoader(runFeeds);
      appendMessageCard(feedScreenC, "Agent C (Supervisor)", "Error", err.message, null, "agent-c");
      appendMessageCard(splitFeedC, "Agent C (Supervisor)", "Error", err.message, null, "agent-c");
      resetRunButtons();
    }
  }

  function resetRunButtons() {
    if (btnRunWorkflow) {
      btnRunWorkflow.disabled = false;
      btnRunWorkflow.innerHTML = '<span class="btn-icon">🚀</span><span id="btn-text">Run Multi-Agent Flow</span>';
    }
    if (btnSplitRun) {
      btnSplitRun.disabled = false;
      btnSplitRun.innerHTML = '<span class="btn-icon">⚡</span><span>Execute Across All 3</span>';
    }
  }

  function connectOrchestrationStream(runId) {
    if (activeEventSource) {
      activeEventSource.close();
    }

    activeEventSource = new EventSource(`/api/stream/${runId}`);

    activeEventSource.onmessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        handleOrchestrationEvent(payload);
      } catch (err) {
        console.error("Failed to parse SSE payload", err);
      }
    };

    activeEventSource.onerror = () => {
      activeEventSource.close();
      resetRunButtons();
      if (agentCState) {
        agentCState.textContent = "COMPLETED";
        agentCState.className = "agent-state-pill";
      }
      if (splitStateC) {
        splitStateC.textContent = "COMPLETED";
        splitStateC.className = "agent-state-pill";
      }
    };
  }

  function handleOrchestrationEvent(data) {
    const event = data.event;
    hideLoader([feedScreenC, splitFeedC, feedScreenA, splitFeedA, feedScreenB, splitFeedB]);

    // Update Global Telemetry Counters
    if (data.total_tokens !== undefined) {
      globalTotalTokens = data.total_tokens;
      globalTokensEl.textContent = globalTotalTokens.toLocaleString();
    }
    if (data.total_cost_usd !== undefined) {
      globalTotalCost = data.total_cost_usd;
      globalCostEl.textContent = `$${globalTotalCost.toFixed(6)}`;
    }

    switch (event) {
      // Step 1: Handshake & Discovery -> Appears on Screen C (Supervisor)
      case "agent_registered": {
        const agent = data.agent;
        const msg = `Discovered and registered capabilities for <strong>${agent.name}</strong> (${agent.provider} - ${agent.model}).\nCapabilities: ${agent.capabilities.join(", ")}.\nSaved to SQLite database.`;
        appendMessageCard(feedScreenC, "Agent C (Supervisor)", "Capability Discovery", msg, data.step?.token_usage, "agent-c");
        appendMessageCard(splitFeedC, "Agent C (Supervisor)", "Capability Discovery", msg, data.step?.token_usage, "agent-c");
        if (data.step?.token_usage) updateAgentCTelemetry(data.step.token_usage);
        showLoader([feedScreenA, splitFeedA], "Laguna is writing…");
        break;
      }

      // Step 2 & 5: Agent A generates initial draft or revision -> Appears on Screen A!
      case "draft_produced": {
        const rev = data.revision;
        const tokens = data.tokens;
        agentAState.textContent = rev === 1 ? "GENERATING (REV 1)" : `REVISING (REV ${rev})`;
        agentAState.className = "agent-state-pill running";
        splitStateA.textContent = rev === 1 ? "REV 1 DRAFT" : `REV ${rev} REFINEMENT`;
        splitStateA.className = "agent-state-pill running";

        const title = rev === 1 ? "Initial Draft Submission (Revision 1)" : `Refined Deliverable (Revision ${rev})`;
        appendMessageCard(feedScreenA, "Agent A (OpenAI)", title, data.draft, tokens, "agent-a");
        appendMessageCard(splitFeedA, "Agent A (OpenAI)", title, data.draft, tokens, "agent-a");

        if (tokens) updateAgentATelemetry(tokens);
        showLoader([feedScreenB, splitFeedB], "Nemotron is reviewing…");
        break;
      }

      // Step 3: Agent B performs audit & quality score -> Appears on Screen B!
      case "audit_completed": {
        const ev = data.evaluation;
        const rev = data.revision;
        agentBState.textContent = ev.passed ? "APPROVED" : "AUDITED (NEEDS REVISION)";
        agentBState.className = "agent-state-pill running";
        splitStateB.textContent = `AUDIT REV ${rev}: ${ev.score}/100`;
        splitStateB.className = "agent-state-pill running";

        let auditHtml = `<strong>Quality Audit Score: ${ev.score}/100 [${ev.passed ? 'PASSED' : 'REJECTED'}]</strong><br><br>`;
        if (ev.strengths && ev.strengths.length) {
          auditHtml += `<strong>Strengths:</strong><br>• ` + ev.strengths.join("<br>• ") + `<br><br>`;
        }
        if (ev.flaws && ev.flaws.length) {
          auditHtml += `<strong style="color: #f87171;">Flaws Detected:</strong><br><span style="color: #fca5a5;">• ` + ev.flaws.join("<br>• ") + `</span><br><br>`;
        }
        auditHtml += `<strong>Actionable Recommendation:</strong><br><em>"${escapeHtml(ev.actionable_feedback)}"</em>`;

        appendMessageCard(feedScreenB, "Agent B (Claude)", `Quality Audit Report (Revision ${rev})`, auditHtml, ev.token_usage, "agent-b", true);
        appendMessageCard(splitFeedB, "Agent B (Claude)", `Quality Audit Report (Revision ${rev})`, auditHtml, ev.token_usage, "agent-b", true);

        if (ev.token_usage) updateAgentBTelemetry(ev.token_usage);
        break;
      }

      // Step 4: Supervisor intervenes when Agent A didn't do a good job -> Appears on Screen C!
      case "supervisor_intervention": {
        supervisorDirectivesCount++;
        agentCDirectives.textContent = supervisorDirectivesCount;

        agentCState.textContent = "INTERVENING";
        agentCState.className = "agent-state-pill running";
        splitStateC.textContent = "INTERVENTION";
        splitStateC.className = "agent-state-pill running";

        const interventionMsg = `<strong>🚨 SUPERVISOR INTERVENTION TRIGGERED:</strong><br>` +
          `Agent A's work did not meet quality threshold (${data.score}/80).<br>` +
          `<strong>Action:</strong> Supervisor commanding Agent A to execute Revision ${data.revision + 1} addressing all Claude audit objections immediately.`;

        appendMessageCard(feedScreenC, "Agent C (Supervisor)", "Intervention Directive", interventionMsg, data.step?.token_usage, "agent-c", true);
        appendMessageCard(splitFeedC, "Agent C (Supervisor)", "Intervention Directive", interventionMsg, data.step?.token_usage, "agent-c", true);

        if (data.step?.token_usage) updateAgentCTelemetry(data.step.token_usage);
        break;
      }

      // Step 6: Workflow finalized and approved -> Appears on Screen C!
      case "workflow_completed": {
        agentCState.textContent = "APPROVED";
        agentCState.className = "agent-state-pill";
        splitStateC.textContent = "APPROVED";
        splitStateC.className = "agent-state-pill";

        agentAState.textContent = "READY";
        agentAState.className = "agent-state-pill";
        splitStateA.textContent = "READY";
        splitStateA.className = "agent-state-pill";

        agentBState.textContent = "READY";
        agentBState.className = "agent-state-pill";
        splitStateB.textContent = "READY";
        splitStateB.className = "agent-state-pill";

        const finalMsg = `<strong>🎉 DELIVERABLE APPROVED! Final Quality Score: ${data.final_score}/100</strong><br>` +
          `Completed across ${data.revisions} revisions. All tokens and USD expenditures recorded in SQLite (<code>orchestration.db</code>).`;

        appendMessageCard(feedScreenC, "Agent C (Supervisor)", "Sign-Off & Approval", finalMsg, data.step?.token_usage, "agent-c", true);
        appendMessageCard(splitFeedC, "Agent C (Supervisor)", "Sign-Off & Approval", finalMsg, data.step?.token_usage, "agent-c", true);

        if (data.step?.token_usage) updateAgentCTelemetry(data.step.token_usage);
        resetRunButtons();
        break;
      }
    }
  }

  // Telemetry Aggregation Functions
  function updateAgentATelemetry(tokens) {
    agentATotalTokens += tokens.total_tokens || 0;
    agentATotalCost += tokens.cost_usd || 0.0;
    agentATokens.textContent = agentATotalTokens.toLocaleString();
    agentACost.textContent = `$${agentATotalCost.toFixed(4)}`;
  }

  function updateAgentBTelemetry(tokens) {
    agentBTotalTokens += tokens.total_tokens || 0;
    agentBTotalCost += tokens.cost_usd || 0.0;
    agentBTokens.textContent = agentBTotalTokens.toLocaleString();
    agentBCost.textContent = `$${agentBTotalCost.toFixed(4)}`;
  }

  function updateAgentCTelemetry(tokens) {
    agentCTotalTokens += tokens.total_tokens || 0;
    agentCTotalCost += tokens.cost_usd || 0.0;
    agentCTokens.textContent = agentCTotalTokens.toLocaleString();
    agentCCost.textContent = `$${agentCTotalCost.toFixed(4)}`;
  }

  function showLoader(containers, label) {
    (containers || []).forEach((container) => {
      if (!container || container.querySelector("[data-loader]")) return;
      const card = document.createElement("div");
      card.className = "feed-card typing-card";
      card.dataset.loader = "1";
      card.innerHTML = `<div class="typing-row"><span class="typing-dots"><i></i><i></i><i></i></span><span>${escapeHtml(label)}</span></div>`;
      container.appendChild(card);
      container.scrollTop = container.scrollHeight;
    });
  }

  function hideLoader(containers) {
    (containers || []).forEach((container) => {
      if (!container) return;
      container.querySelectorAll("[data-loader]").forEach((node) => node.remove());
    });
  }

  // Message Card Renderer
  function appendMessageCard(container, sender, title, content, tokens, theme, isHtml = false) {
    if (!container) return;

    // Remove intro placeholder if present
    const intro = container.querySelector(".pane-intro");
    if (intro) intro.remove();

    let badgeClass = "badge-c";
    let cardThemeClass = "card-agent-c";
    if (theme === "agent-a") {
      badgeClass = "badge-a";
      cardThemeClass = "card-agent-a";
    } else if (theme === "agent-b") {
      badgeClass = "badge-b";
      cardThemeClass = "card-agent-b";
    } else if (theme === "user") {
      badgeClass = "badge-user";
      cardThemeClass = "card-user";
    }

    const card = document.createElement("div");
    card.className = `feed-card ${cardThemeClass}`;


    let tokensBadge = "";
    if (tokens) {
      tokensBadge = `<span class="chip-label" style="color: #34d399; font-family: var(--font-code);">${tokens.total_tokens || 0} tokens | $${(tokens.cost_usd || 0).toFixed(6)}</span>`;
    }

    const time = new Date().toLocaleTimeString();

    card.innerHTML = `
      <div class="feed-card-header">
        <div class="feed-card-title">
          <span class="${badgeClass}">${sender}</span>
          <span style="font-size: 0.85rem; color: #cbd5e1;">${escapeHtml(title)}</span>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          ${tokensBadge}
          <span class="bubble-time">${time}</span>
        </div>
      </div>
      <div class="feed-card-body">
        ${isHtml ? content : formatBody(content)}
      </div>
    `;

    container.appendChild(card);
    container.scrollTop = container.scrollHeight;
  }

  function formatBody(text) {
    if (!text) return "";
    let escaped = escapeHtml(text);
    escaped = escaped.replace(/```python([\s\S]*?)```/g, '<div class="feed-code-block"><code>$1</code></div>');
    escaped = escaped.replace(/```([\s\S]*?)```/g, '<div class="feed-code-block"><code>$1</code></div>');
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/\n### (.*?)\n/g, '<h4 style="margin: 8px 0; color: #38bdf8;">$1</h4>');
    escaped = escaped.replace(/\n#### (.*?)\n/g, '<h5 style="margin: 6px 0; color: #a5f3fc;">$1</h5>');
    escaped = escaped.replace(/\n• /g, '<br>• ');
    escaped = escaped.replace(/\n\n/g, '<br><br>');
    escaped = escaped.replace(/\n/g, '<br>');
    return escaped;
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

  // Database Tab Fetchers
  btnRefreshDb.addEventListener("click", () => {
    fetchDbRuns();
    fetchDbAgents();
  });

  async function fetchDbRuns() {
    try {
      runsTbody.innerHTML = `<tr><td colspan="8" class="text-center text-dim">Refreshing runs...</td></tr>`;
      let runs = [];
      if (!isStandaloneMode) {
        try {
          const res = await fetch("/api/runs");
          if (res.ok) runs = await res.json();
        } catch (e) {}
      }

      if (!runs || !runs.length) {
        const localRuns = JSON.parse(localStorage.getItem("nexus_runs") || "[]");
        if (localRuns.length) {
          runs = localRuns;
        } else {
          runs = [
            {
              run_id: "run_sample_fin01",
              task: "Design a resilient, high-throughput financial transaction processing engine with audit logging and rate limiting.",
              status: "COMPLETED (APPROVED)",
              revisions_count: 2,
              total_tokens: 1890,
              total_cost_usd: 0.016550,
              created_at: "2026-09-29 19:45:10"
            }
          ];
          localStorage.setItem("nexus_runs", JSON.stringify(runs));
        }
      }

      runsTbody.innerHTML = runs.map(r => `
        <tr>
          <td><code style="color: #38bdf8;">${r.run_id}</code></td>
          <td style="max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${escapeHtml(r.task)}</td>
          <td><span class="agent-badge ${r.status.includes('COMPLETED') ? 'badge-a' : 'badge-b'}">${r.status}</span></td>
          <td>${r.revisions_count}</td>
          <td>${(r.total_tokens || 0).toLocaleString()}</td>
          <td style="color: #34d399; font-weight: 600;">$${(r.total_cost_usd || 0).toFixed(6)}</td>
          <td style="color: #64748b; font-size: 0.75rem;">${r.created_at || ''}</td>
          <td><button class="btn-secondary view-run-btn" data-runid="${r.run_id}" style="padding: 4px 10px; font-size: 0.75rem;">Inspect</button></td>
        </tr>
      `).join("");

      document.querySelectorAll(".view-run-btn").forEach(b => {
        b.addEventListener("click", () => showRunDetails(b.getAttribute("data-runid")));
      });
    } catch (err) {
      runsTbody.innerHTML = `<tr><td colspan="8" class="text-center" style="color: #ef4444;">Failed to load runs: ${err.message}</td></tr>`;
    }
  }

  async function fetchDbAgents() {
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
            name: "Agent A (OpenAI)",
            provider: "OpenAI",
            model: "gpt-4o",
            role: "Creator / Implementation Specialist",
            capabilities: ["Code Generation", "Fast Drafting", "Architecture Design", "Self-Correction Refinement"],
            updated_at: "Active (Synced)"
          },
          {
            name: "Agent B (Claude)",
            provider: "Anthropic",
            model: "claude-3-5-sonnet-20241022",
            role: "Critical Auditor & Quality Gate",
            capabilities: ["Critical Audit", "Code Verification", "Security Analysis", "Quantitative Scoring (0-100)"],
            updated_at: "Active (Synced)"
          },
          {
            name: "Agent C (Supervisor)",
            provider: "Agent Nexus (Our System)",
            model: "supervisor-v2-meta",
            role: "Orchestrator & Directive Engine",
            capabilities: ["Capability Discovery", "Telemetry Tracking", "Token Cost Calculation", "Self-Correction Enforcement"],
            updated_at: "Active (Synced)"
          }
        ];
      }

      agentsTbody.innerHTML = agents.map(a => `
        <tr>
          <td><strong>${escapeHtml(a.name)}</strong></td>
          <td>${escapeHtml(a.provider)}</td>
          <td><code style="color: #38bdf8;">${escapeHtml(a.model)}</code></td>
          <td>${escapeHtml(a.role)}</td>
          <td>
            <div class="agent-capabilities">
              ${a.capabilities.map(c => `<span class="cap-tag">${escapeHtml(c)}</span>`).join("")}
            </div>
          </td>
          <td style="color: #64748b; font-size: 0.75rem;">${a.updated_at || ''}</td>
        </tr>
      `).join("");
    } catch (err) {
      agentsTbody.innerHTML = `<tr><td colspan="6" class="text-center" style="color: #ef4444;">Failed to load agents: ${err.message}</td></tr>`;
    }
  }

  async function showRunDetails(runId) {
    runModal.style.display = "flex";
    modalTitle.textContent = `Run Inspector: ${runId}`;
    modalContent.innerHTML = `<p class="text-dim">Fetching run records from SQLite / LocalStorage...</p>`;

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
        r = localRuns.find(item => item.run_id === runId) || {
          run_id: runId,
          task: "Autonomous Multi-Agent Task Execution",
          status: "COMPLETED (APPROVED)",
          total_tokens: 1890,
          total_cost_usd: 0.016550
        };
        steps = [
          { step_index: 1, sender: "Agent C (Supervisor)", receiver: "Agent A & B", action: "DISCOVERY", content: "Discovered and registered capabilities for OpenAI & Claude", cost_usd: 0.0011 },
          { step_index: 2, sender: "Agent A (OpenAI)", receiver: "Agent C (Supervisor)", action: "DRAFT_REV_1", content: "Initial code architecture submitted for review", cost_usd: 0.0038 },
          { step_index: 3, sender: "Agent B (Claude)", receiver: "Agent C (Supervisor)", action: "AUDIT_REV_1", content: "Quality score 65/100 (REJECTED). Missing idempotency and rate limiting.", cost_usd: 0.0041 },
          { step_index: 4, sender: "Agent C (Supervisor)", receiver: "Agent A (OpenAI)", action: "INTERVENTION", content: "Directing Agent A to execute Revision 2 addressing audit feedback.", cost_usd: 0.0000 },
          { step_index: 5, sender: "Agent A (OpenAI)", receiver: "Agent C (Supervisor)", action: "DRAFT_REV_2", content: "Refined deliverable with Redis locks and idempotency tokens.", cost_usd: 0.0046 },
          { step_index: 6, sender: "Agent B (Claude)", receiver: "Agent C (Supervisor)", action: "AUDIT_REV_2", content: "Quality score 94/100 (APPROVED). Ready for production.", cost_usd: 0.0039 }
        ];
        evals = [
          { revision: 1, score: 65, passed: false, actionable_feedback: "Implement Redis token-bucket rate limiting and atomic idempotency keys." },
          { revision: 2, score: 94, passed: true, actionable_feedback: "Fully compliant with enterprise resilience standards. Approved." }
        ];
      }

      modalContent.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 16px;">
          <div style="background: rgba(0,0,0,0.3); padding: 14px; border-radius: 8px;">
            <p><strong>Objective:</strong> ${escapeHtml(r.task)}</p>
            <p style="margin-top: 6px;"><strong>Status:</strong> ${r.status} | <strong>Total Tokens:</strong> ${(r.total_tokens || 0).toLocaleString()} | <strong>Cost:</strong> $${(r.total_cost_usd || 0).toFixed(6)}</p>
          </div>
          <h4>Recorded Steps (${steps.length}):</h4>
          <div style="max-height: 280px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px;">
            ${steps.map(s => `
              <div style="background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; font-size: 0.8rem; border-left: 3px solid #38bdf8;">
                <div style="display: flex; justify-content: space-between; font-weight: 600;">
                  <span>Step ${s.step_index}: ${s.sender} ➔ ${s.receiver} [${s.action}]</span>
                  <span style="color: #34d399;">$${(s.cost_usd || 0).toFixed(6)}</span>
                </div>
                <p style="color: #94a3b8; margin-top: 4px; max-height: 60px; overflow: hidden;">${escapeHtml(s.content)}</p>
              </div>
            `).join("")}
          </div>
          ${evals.length ? `
            <h4>Audit Evaluations (${evals.length}):</h4>
            ${evals.map(e => `
              <div style="background: rgba(255,255,255,0.03); padding: 10px; border-radius: 6px; font-size: 0.8rem;">
                <strong>Revision ${e.revision} Audit:</strong> Score ${e.score}/100 [${e.passed ? 'PASSED' : 'FAILED'}]
                <p style="color: #94a3b8; font-style: italic; margin-top: 4px;">"${escapeHtml(e.actionable_feedback)}"</p>
              </div>
            `).join("")}
          ` : ''}
        </div>
      `;
    } catch (err) {
      modalContent.innerHTML = `<p style="color: #ef4444;">Error fetching details: ${err.message}</p>`;
    }
  }

  modalClose.addEventListener("click", () => {
    runModal.style.display = "none";
  });

  async function checkSystemHealth() {
    try {
      const res = await fetch("/api/health");
      if (!res.ok) throw new Error("HTTP " + res.status);
      const health = await res.json();
      isStandaloneMode = false;
      if (systemStatusEl) {
        systemStatusEl.textContent = "ONLINE (SERVER)";
        systemStatusEl.className = "chip-value text-success";
      }
      if (modeLabel && modeCheckbox && !modeCheckbox.checked) {
        modeLabel.textContent = "Live API Mode";
      }
    } catch (err) {
      console.info("Backend server unreachable. Enabling autonomous client-side simulation mode (Netlify ready).", err);
      isStandaloneMode = true;
      if (systemStatusEl) {
        systemStatusEl.textContent = "NETLIFY CLOUD (ACTIVE)";
        systemStatusEl.className = "chip-value text-accent";
      }
      if (modeCheckbox) {
        modeCheckbox.checked = true;
        modeLabel.textContent = "Autonomous Mode";
      }
    }
  }

  // =========================================================================
  // NETLIFY / CLIENT-SIDE AUTONOMOUS SIMULATION ENGINE
  // (Enables instant execution on Netlify Drop without external Python server)
  // =========================================================================

  function getSimulatedAgentAReply(prompt) {
    const p = (prompt || "").toLowerCase();
    let reply = "";
    if (p.includes("financial") || p.includes("transaction") || p.includes("payment")) {
      reply = `### Financial Transaction Ledger Implementation (GPT-4o)\n\nHere is a resilient financial transaction processor with ledger recording and atomic transfers:\n\n\`\`\`python\nfrom dataclasses import dataclass\nfrom decimal import Decimal\nimport uuid\nimport datetime\n\n@dataclass\nclass Transaction:\n    tx_id: str\n    account_id: str\n    amount: Decimal\n    timestamp: datetime.datetime\n    status: str\n\nclass PaymentLedger:\n    def __init__(self):\n        self._balances = {}\n        self._journal = []\n\n    def execute_transfer(self, from_acc: str, to_acc: str, amount: Decimal) -> Transaction:\n        if self._balances.get(from_acc, Decimal('0.00')) < amount:\n            raise ValueError("Insufficient liquidity for transfer")\n        \n        self._balances[from_acc] -= amount\n        self._balances[to_acc] = self._balances.get(to_acc, Decimal('0.00')) + amount\n        \n        tx = Transaction(\n            tx_id=str(uuid.uuid4()),\n            account_id=from_acc,\n            amount=amount,\n            timestamp=datetime.datetime.utcnow(),\n            status="SETTLED"\n        )\n        self._journal.append(tx)\n        return tx\n\`\`\`\n• **Design Highlights:** In-memory ledger journal with isolated double-entry tracking.\n• **Latency Profile:** Sub-millisecond execution. Ready for Claude auditing.`;
    } else if (p.includes("summary") || p.includes("what do you do") || p.includes("capabilities")) {
      reply = `**OpenAI Agent A Profile:**\n• **Role:** Creator & Implementation Specialist (GPT-4o)\n• **Key Capabilities:** Architecture design, full-stack code implementation, API modeling, revision execution.\n• **Supervisor Integration:** Receives directives from Agent C, adapts drafts based on Agent B's audit feedback.`;
    } else {
      reply = `### Implementation Deliverable (OpenAI GPT-4o)\n\nAddressing your prompt: *"**${escapeHtml(prompt)}**"*\n\n\`\`\`python\nclass SystemWorker:\n    def __init__(self, name: str):\n        self.name = name\n        self.active = True\n\n    def process(self, payload: dict) -> dict:\n        return {\n            "status": "PROCESSED",\n            "worker": self.name,\n            "result": "Completed objective successfully"\n        }\n\`\`\`\n• Modular architecture designed for high availability.\n• Configured with standard error handling and telemetry metrics.`;
    }

    const tokens = {
      prompt_tokens: Math.floor(Math.random() * 50) + 120,
      completion_tokens: Math.floor(Math.random() * 80) + 280,
      total_tokens: 420,
      cost_usd: 0.00375
    };
    return { reply, tokens };
  }

  function getSimulatedAgentBReply(prompt) {
    const p = (prompt || "").toLowerCase();
    let reply = "";
    if (p.includes("financial") || p.includes("transaction") || p.includes("payment") || p.includes("code")) {
      reply = `### Claude 3.5 Sonnet Audit Report\n\n**Quantitative Quality Score:** 92 / 100 [PASSED]\n\n**1. Security & Edge Case Analysis:**\n• **Strengths:** Double-entry ledger logic is mathematically sound; accurate Decimal usage prevents IEEE 754 precision errors.\n• **Identified Risks:** Missing idempotency keys on REST payloads. Under network partition or client retry, duplicate debits could be triggered.\n• **Recommendation:** Wrap transfer execution inside a distributed Redis lock and record \`idempotency_key\` with an enforced 24-hour TTL window.\n\n**2. Audit Sign-Off:**\nArchitecture complies with core regulatory standards. Recommended for production deployment with telemetry hooks.`;
    } else if (p.includes("summary") || p.includes("what do you do") || p.includes("capabilities")) {
      reply = `**Claude Agent B Profile:**\n• **Role:** Critical Auditor & Logic Evaluator (Claude 3.5 Sonnet)\n• **Key Capabilities:** Vulnerability analysis, architectural stress testing, quantitative quality scoring (0-100), actionable revision feedback.\n• **Supervisor Integration:** Submits audits to Agent C; provides explicit reasons when rejecting drafts below quality thresholds.`;
    } else {
      reply = `### Claude 3.5 Sonnet Evaluation\n\n**Quality Score:** 88 / 100 [PASSED]\n\n• **Clarity & Completeness:** Logic is straightforward and meets requirements.\n• **Robustness:** Edge case handling could benefit from explicit exception hierarchies and timeout configurations.\n• **Verdict:** Approved with minor suggestions for production hardening.`;
    }

    const tokens = {
      prompt_tokens: Math.floor(Math.random() * 40) + 110,
      completion_tokens: Math.floor(Math.random() * 60) + 260,
      total_tokens: 390,
      cost_usd: 0.00405
    };
    return { reply, tokens };
  }

  function getSimulatedSupervisorReply(prompt) {
    const reply = `**Agent C (Supervisor Engine) Directive:**\n\nObjective received: *"**${escapeHtml(prompt)}**"*\n\n**Coordination Status:**\n• **Agent A (OpenAI):** Synced and ready for technical implementation.\n• **Agent B (Claude):** Initialized for quality auditing and policy compliance.\n• **Database Ledger:** Telemetry active. SQLite & LocalStorage session tracking enabled.\n\n*Click "Run Multi-Agent Flow" or the 3-Screen Split View tab to orchestrate the complete autonomous triad!*`;

    const tokens = {
      prompt_tokens: 85,
      completion_tokens: 115,
      total_tokens: 200,
      cost_usd: 0.00000
    };
    return { reply, tokens };
  }

  function runClientSideSimulationWorkflow(task, modelA, modelB, threshold) {
    const runId = "run_" + Math.random().toString(36).substring(2, 9);
    if (currentRunPill) currentRunPill.textContent = runId;
    if (splitRunId) splitRunId.textContent = runId;

    let accumulatedTokens = 0;
    let accumulatedCost = 0.0;

    // Step 1: Handshake
    handleOrchestrationEvent({
      event: "agent_registered",
      run_id: runId,
      agent: {
        id: "agent_a",
        name: "Agent A (OpenAI)",
        provider: "OpenAI",
        model: modelA,
        capabilities: ["Code Generation", "Fast Drafting", "Architecture", "Self-Correction"]
      },
      step: { token_usage: { prompt_tokens: 60, completion_tokens: 45, total_tokens: 105, cost_usd: 0.0005 } }
    });

    handleOrchestrationEvent({
      event: "agent_registered",
      run_id: runId,
      agent: {
        id: "agent_b",
        name: "Agent B (Claude)",
        provider: "Anthropic",
        model: modelB,
        capabilities: ["Critical Audit", "Code Verification", "Security Analysis", "Quantitative Scoring"]
      },
      step: { token_usage: { prompt_tokens: 55, completion_tokens: 40, total_tokens: 95, cost_usd: 0.0006 } }
    });

    // Step 2: Agent A Rev 1 Draft (1.2s delay)
    setTimeout(() => {
      accumulatedTokens += 430;
      accumulatedCost += 0.0038;
      handleOrchestrationEvent({
        event: "draft_produced",
        run_id: runId,
        revision: 1,
        draft: `### Initial Architecture Draft (Revision 1 - OpenAI GPT-4o)\n\nObjective: ${task}\n\n\`\`\`python\nclass CoreEngine:\n    def __init__(self):\n        self.queue = []\n\n    def process_item(self, item_id: str, data: dict):\n        # Fast in-memory processing\n        self.queue.append(data)\n        return {"status": "SUCCESS", "id": item_id}\n\`\`\`\n\n• High performance in-memory queue.\n• Fast synchronous response. Ready for Claude auditing.`,
        tokens: { prompt_tokens: 150, completion_tokens: 280, total_tokens: 430, cost_usd: 0.0038 },
        total_tokens: accumulatedTokens,
        total_cost_usd: accumulatedCost
      });

      // Step 3: Agent B Audits Rev 1 with Flaws (Score 65) (2.8s)
      setTimeout(() => {
        accumulatedTokens += 385;
        accumulatedCost += 0.0041;
        handleOrchestrationEvent({
          event: "audit_completed",
          run_id: runId,
          revision: 1,
          evaluation: {
            score: 65,
            passed: false,
            strengths: ["Clean syntax", "Minimal latency on in-memory queue"],
            flaws: ["Zero idempotency protection (duplicate operations possible)", "No persistent audit logging or rate-limiting"],
            actionable_feedback: "Implement Redis token-bucket rate limiting and atomic idempotency keys with rollback capability before production sign-off.",
            token_usage: { prompt_tokens: 140, completion_tokens: 245, total_tokens: 385, cost_usd: 0.0041 }
          },
          total_tokens: accumulatedTokens,
          total_cost_usd: accumulatedCost
        });

        // Step 4: Supervisor Intervenes (Score 65 < threshold) (4.2s)
        setTimeout(() => {
          accumulatedTokens += 95;
          handleOrchestrationEvent({
            event: "supervisor_intervention",
            run_id: runId,
            revision: 1,
            score: 65,
            step: { token_usage: { prompt_tokens: 50, completion_tokens: 45, total_tokens: 95, cost_usd: 0.0000 } },
            total_tokens: accumulatedTokens,
            total_cost_usd: accumulatedCost
          });

          // Step 5: Agent A Rev 2 Refinement (5.8s)
          setTimeout(() => {
            accumulatedTokens += 520;
            accumulatedCost += 0.0046;
            handleOrchestrationEvent({
              event: "draft_produced",
              run_id: runId,
              revision: 2,
              draft: `### Refined Deliverable (Revision 2 - OpenAI GPT-4o)\n\n*Incorporating Supervisor Directive & Claude 3.5 Sonnet Audit Feedback*\n\n\`\`\`python\nimport time\nimport redis\nfrom dataclasses import dataclass\n\n@dataclass\nclass ProcessedResult:\n    tx_id: str\n    status: str\n    cached: bool\n\nclass ResilientEngine:\n    def __init__(self, redis_client):\n        self.redis = redis_client\n        self.rate_limit_per_sec = 100\n\n    def process_with_idempotency(self, idempotency_key: str, payload: dict) -> ProcessedResult:\n        # 1. Idempotency Check (TTL 24 hours)\n        if self.redis.exists(f"idemp:{idempotency_key}"):\n            return ProcessedResult(idempotency_key, "ALREADY_PROCESSED", True)\n\n        # 2. Redis Token-Bucket Rate Limiter\n        current = self.redis.incr(f"ratelimit:{int(time.time())}")\n        if current > self.rate_limit_per_sec:\n            raise RuntimeError("Rate limit exceeded (HTTP 429)")\n\n        # 3. Atomic Execution & Ledger Journaling\n        with self.redis.pipeline() as pipe:\n            pipe.setex(f"idemp:{idempotency_key}", 86400, "SETTLED")\n            pipe.rpush("audit_log", str(payload))\n            pipe.execute()\n\n        return ProcessedResult(idempotency_key, "SETTLED", False)\n\`\`\`\n\n• **All Objections Resolved:** Idempotency keys enforced, distributed token-bucket rate limiting applied, atomic pipeline logging.`,
              tokens: { prompt_tokens: 180, completion_tokens: 340, total_tokens: 520, cost_usd: 0.0046 },
              total_tokens: accumulatedTokens,
              total_cost_usd: accumulatedCost
            });

            // Step 6: Agent B Approves Rev 2 (Score 94) (7.4s)
            setTimeout(() => {
              accumulatedTokens += 360;
              accumulatedCost += 0.0039;
              handleOrchestrationEvent({
                event: "audit_completed",
                run_id: runId,
                revision: 2,
                evaluation: {
                  score: 94,
                  passed: true,
                  strengths: ["Full idempotency protection with 24-hr TTL", "Token-bucket rate limiting correctly handles burst traffic", "Atomic pipeline guarantees zero log desync"],
                  flaws: [],
                  actionable_feedback: "Fully compliant with enterprise resilience standards. Approved for immediate deployment.",
                  token_usage: { prompt_tokens: 130, completion_tokens: 230, total_tokens: 360, cost_usd: 0.0039 }
                },
                total_tokens: accumulatedTokens,
                total_cost_usd: accumulatedCost
              });

              // Step 7: Supervisor Final Sign-Off & Workflow Complete (8.6s)
              setTimeout(() => {
                handleOrchestrationEvent({
                  event: "workflow_completed",
                  run_id: runId,
                  final_score: 94,
                  revisions: 2,
                  total_tokens: accumulatedTokens,
                  total_cost_usd: accumulatedCost,
                  step: { token_usage: { prompt_tokens: 40, completion_tokens: 30, total_tokens: 70, cost_usd: 0.0000 } }
                });

                // Persist Run into LocalStorage for Database Tab
                saveRunToLocalStorage({
                  run_id: runId,
                  task: task,
                  status: "COMPLETED (APPROVED)",
                  revisions_count: 2,
                  total_tokens: accumulatedTokens,
                  total_cost_usd: accumulatedCost,
                  created_at: new Date().toISOString().replace("T", " ").substring(0, 19)
                });

              }, 1200);
            }, 1600);
          }, 1600);
        }, 1400);
      }, 1600);
    }, 1200);
  }

  function saveRunToLocalStorage(runObj) {
    try {
      const runs = JSON.parse(localStorage.getItem("nexus_runs") || "[]");
      runs.unshift(runObj);
      localStorage.setItem("nexus_runs", JSON.stringify(runs.slice(0, 30)));
    } catch (e) {
      console.warn("Could not save to localStorage", e);
    }
  }
});
