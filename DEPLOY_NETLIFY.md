# 🌐 How to Host on Netlify: Step-by-Step Guide

This project is configured and ready to be hosted on **Netlify**!

Netlify is a high-performance global hosting platform for web applications. Because our application features a **3-Screen Glassmorphic Frontend** and an **Autonomous Simulation & Telemetry Engine**, you can deploy it in two ways:

---

## ⚡ Method 1: Instant Deployment via Netlify Drop (Recommended - 30 Seconds!)
*Zero command-line, no GitHub account required, 100% free.*

1. Open your browser and navigate to: **[https://app.netlify.com/drop](https://app.netlify.com/drop)**
   *(Log in or create a free Netlify account if prompted)*.
2. Open your Windows File Explorer to your project folder:
   ```
   C:\Users\ramma\OneDrive\Desktop\Projects\ai-agent-orchestrator
   ```
3. Drag and drop the **`static`** folder (or the entire `ai-agent-orchestrator` project folder containing `netlify.toml`) directly into the Netlify Drop box in your browser.
4. **Done!** Netlify will immediately upload the files and generate a live, public HTTPS URL (e.g. `https://agent-nexus-abc123.netlify.app`).

> **What happens when hosted this way?**
> Netlify only hosts the HTML/CSS/JS. **API keys stay on a Python server** — they must never be pasted into the static site.
> Without a backend, the UI runs **demo mode** (canned replies). For **real** Laguna / Nemotron via OpenRouter, use **Method 3** below or run locally: `python server.py` → http://127.0.0.1:8000

---

## 🚀 Method 2: Continuous Deployment via GitHub (Automated Updates)
*Best if you want Netlify to auto-update every time you push code changes.*

### Step 1: Initialize Git and Push to GitHub
Open PowerShell in the project folder:
```powershell
cd C:\Users\ramma\OneDrive\Desktop\Projects\ai-agent-orchestrator
git init
git add .
git commit -m "Initial commit: Agent Nexus Multi-Agent Supervisor"
git branch -M main
```
Create a new repository on [GitHub](https://github.com/new) (e.g. `ai-agent-orchestrator`), then link and push:
```powershell
git remote add origin https://github.com/YOUR_GITHUB_USERNAME/ai-agent-orchestrator.git
git push -u origin main
```

### Step 2: Connect to Netlify
1. Go to your [Netlify Dashboard](https://app.netlify.com/).
2. Click **"Add new site"** ➔ **"Import an existing project"**.
3. Select **GitHub** and authorize access to your repository.
4. Configure the build settings:
   - **Branch to deploy:** `main`
   - **Base directory:** *(leave blank)*
   - **Build command:** *(leave blank)*
   - **Publish directory:** `static`
5. Click **"Deploy site"**!

Netlify will read the included `netlify.toml` file automatically.

---

## 🛠️ Method 3: Full-Stack Mode (Live Python Backend + Netlify Frontend)
*Optional: If you want to connect live OpenAI and Anthropic API keys over the web.*

Because Netlify is a static CDN / serverless host, continuous Python servers (`server.py`) cannot run directly on Netlify's free tier. To run live API calls on the internet 24/7:

### Step 1: Deploy the Python Backend on Render (Free)
1. Go to [Render.com](https://render.com/) and create a free account.
2. Click **"New +"** ➔ **"Web Service"** and select your GitHub repository.
3. Configure the service:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. Under **Environment Variables**, add:
   - `OPENROUTER_API_KEY`: your OpenRouter key
   - `AGENT_A_MODEL`: `poolside/laguna-s-2.1:free`
   - `AGENT_B_MODEL`: `nvidia/nemotron-3-ultra-550b-a55b:free`
   - `SIMULATION_MODE`: `false`
5. Click **"Create Web Service"**. Render will give you a backend URL (e.g. `https://my-agent-backend.onrender.com`).

### Step 2: Point Netlify to your Backend
Open `netlify.toml` in your project folder and uncomment the redirects section:
```toml
[[redirects]]
  from = "/api/*"
  to = "https://my-agent-backend.onrender.com/api/:splat"
  status = 200
  force = true
```
Push the change to GitHub (or re-upload via Netlify Drop). Netlify will now seamlessly proxy all `/api/*` traffic directly to your live Python backend!

---

## 📋 Netlify Configuration Reference (`netlify.toml`)

Here is what your included `netlify.toml` looks like:
```toml
[build]
  publish = "static"

[[headers]]
  for = "/*"
  [headers.values]
    Cache-Control = "public, max-age=0, must-revalidate"
    X-Frame-Options = "DENY"
    X-Content-Type-Options = "nosniff"
```

Enjoy your live deployment!
