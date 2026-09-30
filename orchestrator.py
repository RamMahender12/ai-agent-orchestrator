import os
import sys
import json
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Ensure root directory is on Python path
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
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.markdown import Markdown

from core.database import Database
from core.models import OrchestrationRun
from agents.agent_a_openai import AgentAOpenAI
from agents.agent_b_claude import AgentBClaude
from agents.agent_c_supervisor import AgentCSupervisor

console = Console(force_terminal=True, legacy_windows=False)


SAMPLE_TASKS = [
    "Design a resilient, high-throughput financial transaction processing engine with audit logging and rate limiting.",
    "Implement an asynchronous in-memory caching utility in Python with TTL expiration and LRU eviction policy.",
    "Draft a security-compliant multi-cloud Kubernetes deployment architecture proposal for an enterprise healthcare app."
]

def print_banner():
    console.print(Panel.fit(
        "[bold cyan]AI Agent Supervisor & Multi-Agent Orchestration System[/bold cyan]\n"
        "[dim]Agent A (OpenAI) + Agent B (Claude) orchestrated by Agent C (Supervisor)[/dim]",
        border_style="cyan"
    ))

def main():
    parser = argparse.ArgumentParser(description="Multi-Agent Orchestrator CLI")
    parser.add_argument("--task", type=str, help="The task for the agents to accomplish")
    parser.add_argument("--live", action="store_true", help="Force Live API mode (requires API keys in .env)")
    parser.add_argument("--model-a", type=str, default=os.getenv("AGENT_A_MODEL", "gpt-4o"), help="OpenAI Model for Agent A")
    parser.add_argument("--model-b", type=str, default=os.getenv("AGENT_B_MODEL", "claude-3-5-sonnet-20241022"), help="Claude Model for Agent B")
    parser.add_argument("--threshold", type=int, default=int(os.getenv("QUALITY_THRESHOLD", 80)), help="Quality pass score (0-100)")
    args = parser.parse_args()

    print_banner()

    # Determine simulation vs live mode
    simulation_mode = not args.live
    if not simulation_mode:
        openai_key = os.getenv("OPENAI_API_KEY", "")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not openai_key or not anthropic_key:
            console.print("[yellow]Notice: One or both API keys are missing in .env. Falling back to realistic simulation mode.[/yellow]")
            simulation_mode = True
        else:
            console.print("[green]Running in LIVE API Mode with OpenAI & Anthropic credentials![/green]")
    else:
        console.print("[cyan]Running in SIMULATION Mode (Zero-cost, works immediately without API keys). Pass --live to use real APIs.[/cyan]\n")

    task = args.task
    if not task:
        console.print("[bold yellow]Select a demonstration scenario or enter a custom task:[/bold yellow]")
        for i, sample in enumerate(SAMPLE_TASKS, 1):
            console.print(f"  [cyan]{i}[/cyan]. {sample}")
        console.print("  [cyan]4[/cyan]. Enter custom task\n")

        choice = input("Enter choice (1-4, default 1): ").strip()
        if choice in ["1", "2", "3"]:
            task = SAMPLE_TASKS[int(choice) - 1]
        elif choice == "4":
            task = input("Enter your custom task: ").strip()
            if not task:
                task = SAMPLE_TASKS[0]
        else:
            task = SAMPLE_TASKS[0]

    console.print(f"\n[bold green]Goal Task:[/bold green] {task}\n")

    # Initialize components
    db = Database()
    agent_a = AgentAOpenAI(model=args.model_a, simulation_mode=simulation_mode)
    agent_b = AgentBClaude(model=args.model_b, simulation_mode=simulation_mode)
    supervisor = AgentCSupervisor(
        agent_a=agent_a,
        agent_b=agent_b,
        database=db,
        quality_threshold=args.threshold,
        max_revisions=3
    )

    # Event listener for live console updates
    def on_event(event_type: str, data: dict):
        if event_type == "status_change":
            console.print(f"[bold magenta]>> [{data.get('status')}][/bold magenta] {data.get('message')}")
        elif event_type == "agent_registered":
            agent = data["agent"]
            console.print(f"  [green][+] Registered:[/green] [bold]{agent['name']}[/bold] ({agent['provider']} - {agent['model']})")
        elif event_type == "draft_produced":
            rev = data["revision"]
            tokens = data["tokens"]
            console.print(f"\n[bold blue]=== Agent A (OpenAI) Draft - Revision {rev} ===[/bold blue]")
            console.print(f"[dim]Tokens: {tokens['total_tokens']} | Step Cost: ${tokens['cost_usd']:.6f}[/dim]")
            preview = data["draft"][:380] + ("..." if len(data["draft"]) > 380 else "")
            console.print(Markdown(preview))
        elif event_type == "audit_completed":
            ev = data["evaluation"]
            color = "green" if ev["passed"] else "red"
            console.print(f"\n[bold {color}]=== Agent B (Claude) Audit Result ===[/bold {color}]")
            console.print(f"Score: [{color} bold]{ev['score']}/100[/{color} bold] | Verdict: [{color}]{'PASSED' if ev['passed'] else 'REVISION REQUIRED'}[/{color}]")
            if ev["flaws"]:
                console.print(f"[bold red]Flaws Identified:[/bold red]")
                for flaw in ev["flaws"]:
                    console.print(f"  [-] {flaw}")
            console.print(f"[bold yellow]Feedback Sent to Supervisor:[/bold yellow] {ev['actionable_feedback']}")
        elif event_type == "supervisor_intervention":
            console.print(Panel(
                f"[bold red]Supervisor Intervention Triggered:[/bold red]\n"
                f"Agent A's work did not meet threshold ({data['score']}/{args.threshold}).\n"
                f"[bold cyan]Action:[/bold cyan] Supervisor commanding Agent A to execute Revision {data['revision'] + 1} addressing all feedback.",
                title="Agent C (Supervisor)",
                border_style="red"
            ))
        elif event_type == "workflow_completed":
            console.print(f"\n[bold green][*] Deliverable Approved! Quality Score: {data['final_score']}/100[/bold green]")


    # Run the workflow
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        transient=True
    ) as progress:
        progress.add_task(description="Orchestrating agents...", total=None)
        run = supervisor.run_workflow(task, event_callback=on_event)

    # Display telemetry summary table
    summary_table = Table(title=f"Telemetry & Telemetry Breakdown (Run ID: {run.run_id})")
    summary_table.add_column("Agent / Role", style="cyan")
    summary_table.add_column("Steps", justify="right")
    summary_table.add_column("Prompt Tokens", justify="right")
    summary_table.add_column("Completion Tokens", justify="right")
    summary_table.add_column("Total Tokens", justify="right")
    summary_table.add_column("Total Cost (USD)", justify="right", style="green")

    # Aggregate by agent
    by_agent = {}
    for s in run.steps:
        agent_name = s.sender
        if agent_name not in by_agent:
            by_agent[agent_name] = {"steps": 0, "prompt": 0, "completion": 0, "total": 0, "cost": 0.0}
        by_agent[agent_name]["steps"] += 1
        if s.token_usage:
            by_agent[agent_name]["prompt"] += s.token_usage.prompt_tokens
            by_agent[agent_name]["completion"] += s.token_usage.completion_tokens
            by_agent[agent_name]["total"] += s.token_usage.total_tokens
            by_agent[agent_name]["cost"] += s.token_usage.cost_usd

    for agent_name, stats in by_agent.items():
        summary_table.add_row(
            agent_name,
            str(stats["steps"]),
            f"{stats['prompt']:,}",
            f"{stats['completion']:,}",
            f"{stats['total']:,}",
            f"${stats['cost']:.6f}"
        )

    summary_table.add_section()
    summary_table.add_row(
        "[bold]TOTAL COMBINED[/bold]",
        str(len(run.steps)),
        "-",
        "-",
        f"[bold]{run.total_tokens:,}[/bold]",
        f"[bold green]${run.total_cost_usd:.6f}[/bold green]"
    )
    console.print("\n")
    console.print(summary_table)

    # Save JSON log file
    logs_dir = Path(__file__).resolve().parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_file = logs_dir / f"run_{run.run_id}.json"
    with open(log_file, "w", encoding="utf-8") as f:
        json.dump(run.model_dump(), f, indent=2, default=str)

    console.print(f"\n[green][*] Full run persisted to SQLite: [bold]orchestration.db[/bold][/green]")
    console.print(f"[green][*] Audit log saved to: [bold]{log_file}[/bold][/green]\n")

if __name__ == "__main__":
    main()

