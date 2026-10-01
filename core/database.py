import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.models import AgentProfile, StepLog, EvaluationResult, OrchestrationRun, TokenUsage

DB_PATH = Path(__file__).resolve().parent.parent / "orchestration.db"

class Database:
    def __init__(self, db_file: Optional[Path] = None):
        self.db_path = db_file or DB_PATH
        self.init_db()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initialize SQLite tables for agents, runs, steps, and evaluations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Agents Registry
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                name TEXT PRIMARY KEY,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                role TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                description TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """)

            # Orchestration Runs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS runs (
                run_id TEXT PRIMARY KEY,
                task TEXT NOT NULL,
                status TEXT NOT NULL,
                revisions_count INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                total_cost_usd REAL DEFAULT 0.0,
                final_output TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            );
            """)

            # Step-by-step Audit Logs
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                step_index INTEGER NOT NULL,
                sender TEXT NOT NULL,
                receiver TEXT NOT NULL,
                action TEXT NOT NULL,
                content TEXT NOT NULL,
                tokens_prompt INTEGER DEFAULT 0,
                tokens_completion INTEGER DEFAULT 0,
                tokens_total INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                metadata TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs (run_id)
            );
            """)

            # Quality Evaluations & Feedback Loops
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id TEXT NOT NULL,
                revision INTEGER NOT NULL,
                reviewer TEXT NOT NULL,
                score INTEGER NOT NULL,
                passed BOOLEAN NOT NULL,
                strengths TEXT,
                flaws TEXT,
                actionable_feedback TEXT,
                cost_usd REAL DEFAULT 0.0,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (run_id) REFERENCES runs (run_id)
            );
            """)
            conn.commit()

    def register_agent(self, profile: AgentProfile):
        """Save or update agent capability discovery in database."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO agents (name, provider, model, role, capabilities, description, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(name) DO UPDATE SET
                provider=excluded.provider,
                model=excluded.model,
                role=excluded.role,
                capabilities=excluded.capabilities,
                description=excluded.description,
                updated_at=CURRENT_TIMESTAMP;
            """, (
                profile.name,
                profile.provider,
                profile.model,
                profile.role,
                json.dumps(profile.capabilities),
                profile.description
            ))
            conn.commit()

    def create_run(self, run: OrchestrationRun):
        """Create a new run entry."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO runs (run_id, task, status, revisions_count, total_tokens, total_cost_usd, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                run.run_id,
                run.task,
                run.status,
                run.revisions_count,
                run.total_tokens,
                run.total_cost_usd,
                run.created_at.isoformat()
            ))
            conn.commit()

    def update_run(self, run: OrchestrationRun):
        """Update run statistics and completion state."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            UPDATE runs SET
                status = ?,
                revisions_count = ?,
                total_tokens = ?,
                total_cost_usd = ?,
                final_output = ?,
                completed_at = ?
            WHERE run_id = ?
            """, (
                run.status,
                run.revisions_count,
                run.total_tokens,
                run.total_cost_usd,
                run.final_output,
                run.completed_at.isoformat() if run.completed_at else None,
                run.run_id
            ))
            conn.commit()

    def log_step(self, run_id: str, step: StepLog):
        """Log an inter-agent message/action and token usage."""
        p_tokens = step.token_usage.prompt_tokens if step.token_usage else 0
        c_tokens = step.token_usage.completion_tokens if step.token_usage else 0
        t_tokens = step.token_usage.total_tokens if step.token_usage else 0
        cost = step.token_usage.cost_usd if step.token_usage else 0.0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO steps (run_id, step_index, sender, receiver, action, content, tokens_prompt, tokens_completion, tokens_total, cost_usd, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                step.step_index,
                step.sender,
                step.receiver,
                step.action,
                step.content,
                p_tokens,
                c_tokens,
                t_tokens,
                cost,
                json.dumps(step.metadata)
            ))
            conn.commit()

    def log_evaluation(self, run_id: str, eval_res: EvaluationResult):
        """Log a quality evaluation."""
        cost = eval_res.token_usage.cost_usd if eval_res.token_usage else 0.0
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT INTO evaluations (run_id, revision, reviewer, score, passed, strengths, flaws, actionable_feedback, cost_usd)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                run_id,
                eval_res.revision,
                eval_res.reviewer,
                eval_res.score,
                1 if eval_res.passed else 0,
                json.dumps(eval_res.strengths),
                json.dumps(eval_res.flaws),
                eval_res.actionable_feedback,
                cost
            ))
            conn.commit()

    def get_registered_agents(self) -> List[Dict[str, Any]]:
        """Retrieve all registered agents."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM agents ORDER BY updated_at DESC")
            rows = cursor.fetchall()
            return [
                {
                    "name": r["name"],
                    "provider": r["provider"],
                    "model": r["model"],
                    "role": r["role"],
                    "capabilities": json.loads(r["capabilities"]),
                    "description": r["description"],
                    "updated_at": r["updated_at"]
                }
                for r in rows
            ]

    def delete_runs(self, run_id: Optional[str] = None):
        """Delete one run, or every run when no id is given, with its steps and evaluations."""
        where, args = ("WHERE run_id = ?", (run_id,)) if run_id else ("", ())
        with self.get_connection() as conn:
            for table in ("steps", "evaluations", "runs"):
                conn.execute(f"DELETE FROM {table} {where}", args)
            conn.commit()

    def get_run_history(self, limit: int = 15) -> List[Dict[str, Any]]:
        """Retrieve recent runs."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs ORDER BY created_at DESC LIMIT ?", (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_run_details(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full run details including steps and evaluations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            run_row = cursor.fetchone()
            if not run_row:
                return None

            cursor.execute("SELECT * FROM steps WHERE run_id = ? ORDER BY step_index ASC", (run_id,))
            step_rows = cursor.fetchall()

            cursor.execute("SELECT * FROM evaluations WHERE run_id = ? ORDER BY revision ASC", (run_id,))
            eval_rows = cursor.fetchall()

            cursor.execute("""
            SELECT sender AS agent, COUNT(*) AS steps, SUM(tokens_prompt) AS prompt_tokens,
                   SUM(tokens_completion) AS completion_tokens, SUM(tokens_total) AS total_tokens,
                   ROUND(SUM(cost_usd), 6) AS cost_usd
            FROM steps WHERE run_id = ? GROUP BY sender
            """, (run_id,))
            usage_rows = cursor.fetchall()

            return {
                "run": dict(run_row),
                "steps": [dict(s) for s in step_rows],
                "evaluations": [dict(e) for e in eval_rows],
                "usage": [dict(u) for u in usage_rows]
            }

    def fail_run(self, run_id: str, error: str):
        """Mark a run FAILED so it never sits in a half-finished status."""
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE runs SET status = 'FAILED', final_output = ?, completed_at = CURRENT_TIMESTAMP WHERE run_id = ?",
                (f"Error: {error}", run_id),
            )
            conn.commit()
