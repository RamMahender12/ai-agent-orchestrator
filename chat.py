import os
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from core.database import Database
from agents.agent_a_openai import AgentAOpenAI
from agents.agent_b_claude import AgentBClaude
from agents.agent_c_supervisor import AgentCSupervisor

console = Console(force_terminal=True, legacy_windows=False)

def main():
    console.print(Panel.fit(
        "[bold cyan]AI Agent Interactive Chat Room[/bold cyan]\n"
        "[dim]Chat directly with OpenAI (A), Claude (B), Supervisor (C), or Collaborative Triad[/dim]",
        border_style="cyan"
    ))

    # Mode detection
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    sim_mode = not (openai_key and anthropic_key)
    
    if sim_mode:
        console.print("[dim cyan]Running in Simulation Mode (Zero-cost demo). Set API keys in .env for live models.[/dim cyan]\n")
    else:
        console.print("[green]Running in LIVE API Mode with OpenAI & Claude keys![/green]\n")

    db = Database()
    agent_a = AgentAOpenAI(simulation_mode=sim_mode)
    agent_b = AgentBClaude(simulation_mode=sim_mode)
    supervisor = AgentCSupervisor(agent_a=agent_a, agent_b=agent_b, database=db)

    console.print("[bold yellow]Choose whom you want to chat with:[/bold yellow]")
    console.print("  [cyan]1[/cyan]. [bold]Collaborative Triad[/bold] (Supervisor C coordinates, Agent A drafts, Agent B critiques)")
    console.print("  [cyan]2[/cyan]. [bold]Agent C (Supervisor)[/bold] - Meta-orchestrator directing workflow")
    console.print("  [cyan]3[/cyan]. [bold]Agent A (OpenAI)[/bold] - Creator & software engineer")
    console.print("  [cyan]4[/cyan]. [bold]Agent B (Claude)[/bold] - Quality auditor & security evaluator")
    
    choice = input("\nSelect mode (1-4, default 1): ").strip() or "1"
    
    mode_names = {
        "1": "Collaborative Triad (A + B + C)",
        "2": "Agent C (Supervisor)",
        "3": "Agent A (OpenAI)",
        "4": "Agent B (Claude)"
    }
    console.print(f"\n[green]Connected to: [bold]{mode_names.get(choice, 'Collaborative Triad')}[/bold][/green]")
    console.print("[dim]Type your message or prompt below. Type 'exit' or 'quit' to end session.[/dim]\n")

    history = []

    while True:
        try:
            user_msg = input("\n👤 You: ").strip()
            if not user_msg:
                continue
            if user_msg.lower() in ["exit", "quit", "q"]:
                console.print("\n[yellow]Exiting chat session. Goodbye![/yellow]\n")
                break

            if choice == "1":
                # Triad collaborative
                console.print("\n[magenta]>> Supervisor coordinating Triad response...[/magenta]")
                responses = supervisor.triad_chat(user_msg)
                for r in responses:
                    sender = r["sender"]
                    role = r["role"]
                    reply = r["reply"]
                    tokens = r.get("tokens", {})
                    
                    if "Agent C" in sender:
                        color = "blue"
                    elif "Agent A" in sender:
                        color = "green"
                    else:
                        color = "magenta"

                    console.print(f"\n[bold {color}]─── {sender} ({role}) ───[/bold {color}]")
                    if tokens:
                        console.print(f"[dim]Tokens: {tokens.get('total_tokens', 0)} | Cost: ${tokens.get('cost_usd', 0.0):.6f}[/dim]")
                    console.print(Markdown(reply))

            elif choice == "2":
                # Direct Supervisor
                res = supervisor.chat(user_msg)
                tokens = res.get("tokens", {})
                console.print(f"\n[bold blue]─── Agent C (Supervisor) ───[/bold blue]")
                console.print(f"[dim]Tokens: {tokens.get('total_tokens', 0)} | Cost: ${tokens.get('cost_usd', 0.0):.6f}[/dim]")
                console.print(Markdown(res["reply"]))

            elif choice == "3":
                # Direct OpenAI Agent A
                reply, usage = agent_a.chat(user_msg, history)
                history.append({"role": "user", "content": user_msg})
                history.append({"role": "assistant", "content": reply})
                console.print(f"\n[bold green]─── Agent A (OpenAI) ───[/bold green]")
                console.print(f"[dim]Tokens: {usage.total_tokens} | Cost: ${usage.cost_usd:.6f}[/dim]")
                console.print(Markdown(reply))

            elif choice == "4":
                # Direct Claude Agent B
                reply, usage = agent_b.chat(user_msg, history)
                history.append({"role": "user", "content": user_msg})
                history.append({"role": "assistant", "content": reply})
                console.print(f"\n[bold magenta]─── Agent B (Claude) ───[/bold magenta]")
                console.print(f"[dim]Tokens: {usage.total_tokens} | Cost: ${usage.cost_usd:.6f}[/dim]")
                console.print(Markdown(reply))

        except (KeyboardInterrupt, EOFError):
            console.print("\n[yellow]Session terminated.[/yellow]\n")
            break

if __name__ == "__main__":
    main()
