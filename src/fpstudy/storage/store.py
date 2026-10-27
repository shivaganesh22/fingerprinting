"""SQLite storage manager with WAL mode, batching, and JSONL export/import."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fpstudy.storage.schema import (
    CREATE_TABLES_SQL,
    SCHEMA_VERSION,
    ClassificationRecord,
    EventRecord,
    RunRecord,
    ScriptRecord,
    VisitRecord,
)


class DataStore:
    """Thread-safe SQLite database manager for crawl events and classifications."""

    def __init__(self, db_path: Path | str = "data/raw/fpstudy.sqlite"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Create and configure a SQLite connection with WAL mode and pragmas."""
        conn = sqlite3.connect(self.db_path, timeout=60.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA busy_timeout=60000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        """Initialize database tables, schema version, and indexes."""
        with self._get_connection() as conn:
            conn.executescript(CREATE_TABLES_SQL)
            cur = conn.execute(
                "SELECT version FROM schema_version WHERE version = ?", (SCHEMA_VERSION,)
            )
            if not cur.fetchone():
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, datetime.now(UTC).isoformat()),
                )

    def insert_run(self, run: RunRecord) -> None:
        """Insert or replace a run record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id, condition, config_hash, git_commit, tranco_list_id,
                    browser_version, os_info, library_versions, start_time, end_time,
                    canary_passed, canary_details
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.run_id,
                    run.condition,
                    run.config_hash,
                    run.git_commit,
                    run.tranco_list_id,
                    run.browser_version,
                    run.os_info,
                    json.dumps(run.library_versions),
                    run.start_time,
                    run.end_time,
                    run.canary_passed,
                    json.dumps(run.canary_details),
                ),
            )

    def finish_run(self, run_id: str, end_time: str | None = None) -> None:
        """Update end_time for an active run."""
        ts = end_time or datetime.now(UTC).isoformat()
        with self._get_connection() as conn:
            conn.execute("UPDATE runs SET end_time = ? WHERE run_id = ?", (ts, run_id))

    def insert_visit(self, visit: VisitRecord) -> None:
        """Insert or replace a visit record."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO visits (
                    visit_id, run_id, domain, initial_url, final_url, status,
                    http_status, load_time_ms, dwell_time_ms, console_errors_count,
                    requests_count, failed_requests_count, blocked_requests_count,
                    events_count, events_truncated, start_time, end_time, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    visit.visit_id,
                    visit.run_id,
                    visit.domain,
                    visit.initial_url,
                    visit.final_url,
                    visit.status,
                    visit.http_status,
                    visit.load_time_ms,
                    visit.dwell_time_ms,
                    visit.console_errors_count,
                    visit.requests_count,
                    visit.failed_requests_count,
                    visit.blocked_requests_count,
                    visit.events_count,
                    visit.events_truncated,
                    visit.start_time,
                    visit.end_time,
                    visit.error_message,
                ),
            )

    def insert_events(self, events: Iterable[EventRecord]) -> None:
        """Batch insert raw browser events."""
        event_list = list(events)
        if not event_list:
            return

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO events (
                    visit_id, ts, api, method_or_property, args_summary,
                    return_summary, script_url, stack_excerpt, frame_url,
                    top_level_url, is_third_party
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        e.visit_id,
                        e.ts,
                        e.api,
                        e.method_or_property,
                        json.dumps(e.args_summary),
                        json.dumps(e.return_summary),
                        e.script_url,
                        e.stack_excerpt,
                        e.frame_url,
                        e.top_level_url,
                        e.is_third_party,
                    )
                    for e in event_list
                ],
            )

    def insert_scripts(self, scripts: Iterable[ScriptRecord]) -> None:
        """Batch insert script metadata."""
        script_list = list(scripts)
        if not script_list:
            return

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO scripts (
                    visit_id, script_url, is_third_party, matched_blocklist_entries,
                    high_entropy_signals_count
                ) VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        s.visit_id,
                        s.script_url,
                        s.is_third_party,
                        json.dumps(s.matched_blocklist_entries),
                        s.high_entropy_signals_count,
                    )
                    for s in script_list
                ],
            )

    def insert_classifications(self, classifications: Iterable[ClassificationRecord]) -> None:
        """Batch insert or replace classification records."""
        records = list(classifications)
        if not records:
            return

        with self._get_connection() as conn:
            conn.executemany(
                """
                INSERT INTO classifications (
                    run_id, visit_id, domain, script_url, vector, flagged,
                    confidence, evidence, is_third_party
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        c.run_id,
                        c.visit_id,
                        c.domain,
                        c.script_url,
                        c.vector,
                        c.flagged,
                        c.confidence,
                        json.dumps(c.evidence),
                        c.is_third_party,
                    )
                    for c in records
                ],
            )

    def get_completed_domains(self, run_id: str) -> set[str]:
        """Query set of domains already completed for a given run ID (for resuming)."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT domain FROM visits WHERE run_id = ?", (run_id,))
            return {row["domain"] for row in cur.fetchall()}

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        """Fetch run record dictionary."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_visits(self, run_id: str) -> list[dict[str, Any]]:
        """Fetch all visits for a run ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM visits WHERE run_id = ? ORDER BY domain", (run_id,))
            return [dict(row) for row in cur.fetchall()]

    def get_events_for_visit(self, visit_id: str) -> list[dict[str, Any]]:
        """Fetch all events logged for a specific visit ID."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM events WHERE visit_id = ? ORDER BY ts ASC", (visit_id,)
            )
            return [dict(row) for row in cur.fetchall()]

    def get_events_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """Fetch all events logged across all visits in a run."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """
                SELECT e.*, v.domain
                FROM events e
                JOIN visits v ON e.visit_id = v.visit_id
                WHERE v.run_id = ?
                ORDER BY e.ts ASC
                """,
                (run_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_classifications_for_run(self, run_id: str) -> list[dict[str, Any]]:
        """Fetch all script classification rows for a run ID."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM classifications WHERE run_id = ? ORDER BY domain, script_url, vector",
                (run_id,),
            )
            return [dict(row) for row in cur.fetchall()]

    def clear_classifications(self, run_id: str) -> None:
        """Clear existing classifications for a run prior to re-classifying."""
        with self._get_connection() as conn:
            conn.execute("DELETE FROM classifications WHERE run_id = ?", (run_id,))

    def export_jsonl(self, run_id: str, output_path: Path | str) -> None:
        """Export all visits, events, and classifications for a run into a line-delimited JSON file."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        run = self.get_run(run_id)
        visits = self.get_visits(run_id)

        with out.open("w", encoding="utf-8") as f:
            f.write(json.dumps({"type": "run", "data": run}) + "\n")
            for v in visits:
                f.write(json.dumps({"type": "visit", "data": v}) + "\n")
                events = self.get_events_for_visit(v["visit_id"])
                for e in events:
                    f.write(json.dumps({"type": "event", "data": e}) + "\n")

    def import_jsonl(self, input_path: Path | str) -> None:
        """Import a JSONL export file into the SQLite database."""
        path = Path(input_path)
        if not path.is_file():
            raise FileNotFoundError(f"Export file not found: {path}")

        events_batch: list[EventRecord] = []
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                record = json.loads(line)
                rec_type = record.get("type")
                data = record.get("data", {})

                if rec_type == "run":
                    self.insert_run(
                        RunRecord(
                            run_id=data["run_id"],
                            condition=data["condition"],
                            config_hash=data["config_hash"],
                            start_time=data["start_time"],
                            git_commit=data.get("git_commit"),
                            tranco_list_id=data.get("tranco_list_id"),
                            browser_version=data.get("browser_version"),
                            os_info=data.get("os_info"),
                            library_versions=json.loads(data["library_versions"])
                            if isinstance(data.get("library_versions"), str)
                            else data.get("library_versions", {}),
                            end_time=data.get("end_time"),
                            canary_passed=data.get("canary_passed", 1),
                            canary_details=json.loads(data["canary_details"])
                            if isinstance(data.get("canary_details"), str)
                            else data.get("canary_details", {}),
                        )
                    )
                elif rec_type == "visit":
                    self.insert_visit(
                        VisitRecord(
                            visit_id=data["visit_id"],
                            run_id=data["run_id"],
                            domain=data["domain"],
                            initial_url=data["initial_url"],
                            final_url=data.get("final_url"),
                            status=data["status"],
                            http_status=data.get("http_status"),
                            load_time_ms=data.get("load_time_ms"),
                            dwell_time_ms=data.get("dwell_time_ms"),
                            console_errors_count=data.get("console_errors_count", 0),
                            requests_count=data.get("requests_count", 0),
                            failed_requests_count=data.get("failed_requests_count", 0),
                            blocked_requests_count=data.get("blocked_requests_count", 0),
                            events_count=data.get("events_count", 0),
                            events_truncated=data.get("events_truncated", 0),
                            start_time=data["start_time"],
                            end_time=data.get("end_time"),
                            error_message=data.get("error_message"),
                        )
                    )
                elif rec_type == "event":
                    events_batch.append(
                        EventRecord(
                            visit_id=data["visit_id"],
                            ts=data["ts"],
                            api=data["api"],
                            method_or_property=data["method_or_property"],
                            args_summary=json.loads(data["args_summary"])
                            if isinstance(data.get("args_summary"), str)
                            else data.get("args_summary", {}),
                            return_summary=json.loads(data["return_summary"])
                            if isinstance(data.get("return_summary"), str)
                            else data.get("return_summary", {}),
                            script_url=data.get("script_url"),
                            stack_excerpt=data.get("stack_excerpt"),
                            frame_url=data.get("frame_url"),
                            top_level_url=data.get("top_level_url"),
                            is_third_party=data.get("is_third_party", 0),
                        )
                    )
                    if len(events_batch) >= 1000:
                        self.insert_events(events_batch)
                        events_batch.clear()

        if events_batch:
            self.insert_events(events_batch)
