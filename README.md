# 🤖 Multi-Agent Orchestrator & Supervisor System

> **Autonomous Multi-Agent Architecture featuring OpenAI (Agent A) and Claude (Agent B) coordinated by a Supervisor Engine (Agent C) with live token cost telemetry, self-correction feedback loops, and SQLite persistence.**

Built to fulfill your client's exact requirements:
1. **Agent A (OpenAI / ChatGPT / GPT-4o):** Acts as the creator and implementation worker.
2. **Agent B (Anthropic Claude 3.5 Sonnet):** Acts as the critical quality auditor and logic judge.
3. **Agent C (Supervisor / "Our Agent"):**
   - Interrogates Agent A and Agent B (*"What do you do?"*) and registers their capabilities in a database.
   - Assigns objectives and continuously monitors step transitions.
   - Calculates exact token consumption and USD costs for OpenAI, Claude, and internal operations.
   - Evaluates performance: when Agent A's initial output fails quality criteria, Agent C intervenes and commands Agent A to revise and improve (*"tells A to do it better"*).
   - Manages approval gates and archives full audit logs in SQLite and JSON.

---

## 🌟 Key Features

- **Dedicated 3-Screen Architecture:**
  - **Screen A (OpenAI GPT-4o):** Dedicated workspace for generation, technical drafting, code, and revisions.
  - **Screen B (Claude 3.5 Sonnet):** Dedicated workspace for auditing, quantitative scoring (0-100), and security checks.
  - **Screen C (Supervisor / Our Agent):** Dedicated command center for capability discovery, inter-agent coordination, token telemetry, and self-correction directives ("tell A to do better").
  - **Panoramic 3-Screen Split View:** Allows monitoring all three screens simultaneously in real time.
- **Dual-Mode Execution:**
  - **Simulation Mode (Default):** Ready out of the box with zero setup or API costs. Accurately simulates the discovery, initial draft, flaw detection, supervisor intervention, and refined revision.
  - **Live API Mode:** Connects to official OpenAI and Anthropic SDKs via `OPENAI_API_KEY` and `ANTHROPIC_API_KEY`.
- **Live Glassmorphic Web Dashboard:** Real-time visual control room with interactive agent state cards, SSE telemetry streaming, token gauges, and SQLite inspector.
- **Rich Terminal CLI:** Color-coded terminal runner with styled tables and progress spinners (`orchestrator.py` & `chat.py`).
- **Token & USD Cost Engine:** Official pricing tables for GPT-4o, GPT-4o-mini, Claude 3.5 Sonnet, and Claude 3 Haiku.
- **SQLite Database (`orchestration.db`):** Auto-initialized relational schema tracking `agents`, `runs`, `steps`, and `evaluations`.

---

## 📁 Project Architecture

```
ai-agent-orchestrator/
├── orchestrator.py            # Standalone CLI runner with rich tables & telemetry
├── chat.py                    # Interactive terminal chat CLI with individual agents / triad
├── server.py                  # FastAPI server providing REST APIs & SSE live streaming
├── static/                    # Dedicated 3-Screen Glassmorphic Web Dashboard
│   ├── index.html             # UI with dedicated Screen A, Screen B, Screen C & Split View
│   ├── styles.css             # Custom dark glassmorphism design system
│   └── app.js                 # Real-time SSE stream & multi-screen routing logic
├── agents/
│   ├── base_agent.py          # Abstract Agent interface
│   ├── agent_a_openai.py      # Agent A (OpenAI generator with revision engine)
│   ├── agent_b_claude.py      # Agent B (Claude auditor with scoring 0-100)
│   └── agent_c_supervisor.py  # Agent C (Supervisor directing A & B)
├── core/
│   ├── database.py            # SQLite engine (agents, runs, steps, evaluations)
│   ├── cost_tracker.py        # Token math & USD cost pricing matrix
│   └── models.py              # Pydantic data schemas
├── logs/                      # Automatically exported JSON audit trails
├── requirements.txt           # Python package dependencies
└── .env                       # Environment configuration & API keys
```

---

## 🚀 Quick Start Guide

### 1. Launch the 3-Screen Web Dashboard
From the project folder:
```powershell
.\venv\Scripts\python.exe server.py
```
Open your browser to: **[http://localhost:8000](http://localhost:8000)**

You now have **three dedicated screens**:
- **🟢 Screen A (OpenAI):** Send prompts directly to OpenAI GPT-4o, test code architectures, and inspect its drafts and revisions.
- **🟣 Screen B (Claude):** Send prompts directly to Claude 3.5 Sonnet, ask for security reviews, and inspect quality scorecards.
- **🤖 Screen C (Supervisor):** Coordinate both agents, launch multi-agent workflows, and command revisions when Agent A's work falls below standard.
- **⚡ 3-Screen Split View:** View all three screens running simultaneously side-by-side in real time!


---

### 2. Interactive Chat with the Agents

You have two ways to chat back-and-forth with the agents:

#### Option A: Web Chat Room (In Browser)
1. Go to **[http://localhost:8000](http://localhost:8000)**
2. Click on the **"💬 Interactive Chat Room"** tab.
3. Select whom to chat with:
   - **🌐 Collaborative Triad (A + B + C):** Agent C receives your prompt, coordinates, Agent A drafts, and Agent B reviews.
   - **🤖 Agent C (Supervisor):** Ask questions about agent capabilities, monitoring, or token costs.
   - **🟢 Agent A (OpenAI):** Direct conversation with OpenAI GPT-4o.
   - **🟣 Agent B (Claude):** Direct conversation with Claude 3.5 Sonnet for auditing and critique.
4. Type your message and hit Enter or click **Send Prompt**!

#### Option B: Terminal Chat CLI
Run directly in PowerShell:
```powershell
.\venv\Scripts\python.exe chat.py
```
Select your chat partner (1-4) and converse interactively with live markdown rendering, token counts, and USD cost calculations!

---

### 3. Run Full Autonomous Workflow via Terminal (CLI)
To run directly from PowerShell or Command Prompt:
```powershell
# Interactive mode (picks from sample scenarios or custom input):
.\venv\Scripts\python.exe orchestrator.py

# Or pass a custom task directly:
.\venv\Scripts\python.exe orchestrator.py --task "Build a high-performance distributed rate limiter in Python with Redis token bucket"
```

---


## 🔑 Connecting Real OpenAI and Claude API Keys

To switch from Simulation Mode to Live APIs:
1. Open `.env` in `ai-agent-orchestrator`:
```env
OPENAI_API_KEY=sk-proj-your-openai-api-key
ANTHROPIC_API_KEY=sk-ant-your-claude-api-key
SIMULATION_MODE=false
```
2. Run `server.py` or run `orchestrator.py --live`.

---

## A2A protocol

Clients use [Agent2Agent](https://a2a-protocol.org) JSON-RPC 2.0. Agent C is the client entrypoint. It reads A and B's agent cards, tasks them with `message/send`, writes every call to SQLite and `logs/a2a.jsonl`, and sums token cost from each task's `metadata.usage`. If B scores the draft under the threshold, C sends A another `message/send` with skill `revise`.

| Agent | Card | RPC |
| --- | --- | --- |
| C supervisor | `GET /.well-known/agent-card.json` | `POST /a2a/c` |
| A OpenAI | `GET /a2a/a/.well-known/agent-card.json` | `POST /a2a/a` |
| B Claude | `GET /a2a/b/.well-known/agent-card.json` | `POST /a2a/b` |

```json
{"jsonrpc":"2.0","id":1,"method":"message/send","params":{"message":{"role":"user","messageId":"m1","metadata":{"skill":"orchestrate"},"parts":[{"kind":"text","text":"Build a rate limiter"}]}}}
```

`tasks/get` reads one task. `tasks/list` is how C monitors in-process history. `tasks/cancel` cancels a task that is still running.

## 📊 Database Schema (`orchestration.db`)

1. **`agents`**: Registry of discovered agent capabilities, provider, and model.
2. **`runs`**: Execution sessions, objective task, total tokens, total cost (USD), status.
3. **`steps`**: Granular log of every inter-agent communication, sender, receiver, action, prompt/completion tokens, and USD cost.
4. **`evaluations`**: Claude audit results, scores (0-100), identified flaws, and feedback sent to Agent C.
