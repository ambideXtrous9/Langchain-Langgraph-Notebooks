"""Agent Memory Blackboard (Run) backed by SQLite for evidence, traps, and findings."""

import json
import logging
import os
import sqlite3
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class RunBlackboard:
    """Per-device or per-run SQLite blackboard for inter-agent evidence sharing, memory, and reflection."""

    def __init__(self, run_id: str, db_dir: str = "data"):
        self.run_id = run_id
        os.makedirs(db_dir, exist_ok=True)
        self.db_path = os.path.join(db_dir, f"blackboard_{run_id}.db")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS subgoals (
                    id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    status TEXT DEFAULT 'unanswered',
                    answered_by TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS traps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trap_name TEXT NOT NULL,
                    warning TEXT NOT NULL,
                    avoided_by TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    lens TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    sql_query TEXT,
                    expected_value REAL,
                    verbatim_quote TEXT,
                    source TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id TEXT PRIMARY KEY,
                    lens TEXT NOT NULL,
                    title TEXT NOT NULL,
                    claim TEXT NOT NULL,
                    confidence REAL DEFAULT 0.85,
                    sql_query TEXT,
                    numeric_scalar REAL,
                    verbatim_quote TEXT,
                    status TEXT DEFAULT 'proposed',
                    verified INTEGER DEFAULT 0,
                    headline TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS kv_store (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()

    def set(self, key: str, value: Any) -> None:
        """Stores an arbitrary JSON-serializable key-value pair in blackboard memory."""
        with self._get_conn() as conn:
            conn.cursor().execute(
                "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
                (key, json.dumps(value)),
            )
            conn.commit()

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a value by key from blackboard memory."""
        with self._get_conn() as conn:
            cur = conn.cursor()
            row = cur.execute("SELECT value FROM kv_store WHERE key = ?", (key,)).fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except Exception:
                    return row["value"]
            return default


    def add_subgoal(self, subgoal_id: str, description: str) -> None:
        with self._get_conn() as conn:
            conn.cursor().execute(
                "INSERT OR REPLACE INTO subgoals (id, description, status) VALUES (?, ?, 'unanswered')",
                (subgoal_id, description),
            )
            conn.commit()

    def update_subgoal(self, subgoal_id: str, status: str, answered_by: Optional[str] = None) -> None:
        with self._get_conn() as conn:
            conn.cursor().execute(
                "UPDATE subgoals SET status = ?, answered_by = ? WHERE id = ?",
                (status, answered_by, subgoal_id),
            )
            conn.commit()

    def get_subgoals(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            rows = cur.execute("SELECT * FROM subgoals").fetchall()
            return [dict(r) for r in rows]

    def add_trap(self, trap_name: str, warning: str) -> None:
        with self._get_conn() as conn:
            conn.cursor().execute(
                "INSERT INTO traps (trap_name, warning) VALUES (?, ?)",
                (trap_name, warning),
            )
            conn.commit()

    def get_traps(self) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            rows = cur.execute("SELECT * FROM traps").fetchall()
            return [dict(r) for r in rows]

    def post_evidence(
        self,
        lens: str,
        claim: str,
        sql_query: Optional[str] = None,
        expected_value: Optional[float] = None,
        verbatim_quote: Optional[str] = None,
        source: Optional[str] = None,
    ) -> int:
        with self._get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                """INSERT INTO evidence (lens, claim, sql_query, expected_value, verbatim_quote, source)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (lens, claim, sql_query, expected_value, verbatim_quote, source),
            )
            conn.commit()
            return cur.lastrowid or 0

    def get_evidence(self, lens: Optional[str] = None) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            if lens:
                rows = cur.execute("SELECT * FROM evidence WHERE lens = ?", (lens,)).fetchall()
            else:
                rows = cur.execute("SELECT * FROM evidence").fetchall()
            return [dict(r) for r in rows]

    def post_finding(
        self,
        finding_id: str,
        lens: str,
        title: str,
        claim: str,
        confidence: float = 0.85,
        sql_query: Optional[str] = None,
        numeric_scalar: Optional[float] = None,
        verbatim_quote: Optional[str] = None,
        status: str = "proposed",
    ) -> None:
        with self._get_conn() as conn:
            conn.cursor().execute(
                """INSERT OR REPLACE INTO findings 
                   (id, lens, title, claim, confidence, sql_query, numeric_scalar, verbatim_quote, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (finding_id, lens, title, claim, confidence, sql_query, numeric_scalar, verbatim_quote, status),
            )
            conn.commit()

    def update_finding_verification(self, finding_id: str, verified: bool, headline: Optional[str] = None) -> None:
        with self._get_conn() as conn:
            conn.cursor().execute(
                "UPDATE findings SET verified = ?, headline = ?, status = ? WHERE id = ?",
                (1 if verified else 0, headline, "verified" if verified else "rejected", finding_id),
            )
            conn.commit()

    def get_findings(self, verified_only: bool = False) -> List[Dict[str, Any]]:
        with self._get_conn() as conn:
            cur = conn.cursor()
            if verified_only:
                rows = cur.execute("SELECT * FROM findings WHERE verified = 1").fetchall()
            else:
                rows = cur.execute("SELECT * FROM findings").fetchall()
            return [dict(r) for r in rows]

    def get_full_context_summary(self) -> str:
        """Returns comprehensive summary of all blackboard memory for Reflection and Synthesis."""
        subgoals = self.get_subgoals()
        traps = self.get_traps()
        findings = self.get_findings()
        evidence = self.get_evidence()

        lines = [f"=== Agent Memory Blackboard [Run: {self.run_id}] ==="]
        lines.append(f"\n1. Subgoals ({len(subgoals)}):")
        for sg in subgoals:
            lines.append(f"  - [{sg.get('status', '').upper()}] {sg.get('id')}: {sg.get('description')}")

        lines.append(f"\n2. Analytical Traps ({len(traps)}):")
        for tr in traps:
            lines.append(f"  - ! {tr.get('trap_name')}: {tr.get('warning')}")

        lines.append(f"\n3. Findings Posted ({len(findings)}):")
        for fn in findings:
            lines.append(f"  - [{fn.get('status')}] {fn.get('id')} ({fn.get('lens')}): {fn.get('title')} | Claim: {fn.get('claim')}")

        lines.append(f"\n4. Evidence Pieces: {len(evidence)} items recorded.")
        return "\n".join(lines)
