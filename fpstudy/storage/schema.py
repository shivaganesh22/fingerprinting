"""Database schema definitions, migration notes, and dataclasses for storage."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = 1

CREATE_TABLES_SQL = """
-- Migration Notes:
-- Schema Version 1: Initial schema for runs, visits, events, scripts, and classifications.
-- WAL mode enabled by default for high-concurrency writes.

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    condition TEXT NOT NULL,
    config_hash TEXT NOT NULL,
    git_commit TEXT,
    tranco_list_id TEXT,
    browser_version TEXT,
    os_info TEXT,
    library_versions TEXT,
    start_time TEXT NOT NULL,
    end_time TEXT,
    canary_passed INTEGER NOT NULL DEFAULT 1,
    canary_details TEXT
);

CREATE TABLE IF NOT EXISTS visits (
    visit_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    initial_url TEXT NOT NULL,
    final_url TEXT,
    status TEXT NOT NULL,
    http_status INTEGER,
    load_time_ms REAL,
    dwell_time_ms REAL,
    console_errors_count INTEGER DEFAULT 0,
    requests_count INTEGER DEFAULT 0,
    failed_requests_count INTEGER DEFAULT 0,
    blocked_requests_count INTEGER DEFAULT 0,
    events_count INTEGER DEFAULT 0,
    events_truncated INTEGER DEFAULT 0,
    start_time TEXT NOT NULL,
    end_time TEXT,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    ts REAL NOT NULL,
    api TEXT NOT NULL,
    method_or_property TEXT NOT NULL,
    args_summary TEXT,
    return_summary TEXT,
    script_url TEXT,
    stack_excerpt TEXT,
    frame_url TEXT,
    top_level_url TEXT,
    is_third_party INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    script_url TEXT NOT NULL,
    is_third_party INTEGER NOT NULL DEFAULT 0,
    matched_blocklist_entries TEXT,
    high_entropy_signals_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
    visit_id TEXT NOT NULL REFERENCES visits(visit_id) ON DELETE CASCADE,
    domain TEXT NOT NULL,
    script_url TEXT NOT NULL,
    vector TEXT NOT NULL,
    flagged INTEGER NOT NULL,
    confidence TEXT NOT NULL,
    evidence TEXT,
    is_third_party INTEGER NOT NULL DEFAULT 0
);

-- Performance Indexes
CREATE INDEX IF NOT EXISTS idx_visits_run_domain ON visits(run_id, domain);
CREATE INDEX IF NOT EXISTS idx_visits_status ON visits(status);
CREATE INDEX IF NOT EXISTS idx_events_visit ON events(visit_id);
CREATE INDEX IF NOT EXISTS idx_events_api ON events(api);
CREATE INDEX IF NOT EXISTS idx_events_script ON events(script_url);
CREATE INDEX IF NOT EXISTS idx_scripts_visit ON scripts(visit_id);
CREATE INDEX IF NOT EXISTS idx_classifications_run ON classifications(run_id);
CREATE INDEX IF NOT EXISTS idx_classifications_visit ON classifications(visit_id);
CREATE INDEX IF NOT EXISTS idx_classifications_domain ON classifications(domain);
"""


@dataclass
class RunRecord:
    run_id: str
    condition: str
    config_hash: str
    start_time: str
    git_commit: str | None = None
    tranco_list_id: str | None = None
    browser_version: str | None = None
    os_info: str | None = None
    library_versions: dict[str, str] = field(default_factory=dict)
    end_time: str | None = None
    canary_passed: int = 1
    canary_details: dict[str, Any] = field(default_factory=dict)


@dataclass
class VisitRecord:
    visit_id: str
    run_id: str
    domain: str
    initial_url: str
    status: str
    start_time: str
    final_url: str | None = None
    http_status: int | None = None
    load_time_ms: float | None = None
    dwell_time_ms: float | None = None
    console_errors_count: int = 0
    requests_count: int = 0
    failed_requests_count: int = 0
    blocked_requests_count: int = 0
    events_count: int = 0
    events_truncated: int = 0
    end_time: str | None = None
    error_message: str | None = None


@dataclass
class EventRecord:
    visit_id: str
    ts: float
    api: str
    method_or_property: str
    args_summary: dict[str, Any] = field(default_factory=dict)
    return_summary: dict[str, Any] = field(default_factory=dict)
    script_url: str | None = None
    stack_excerpt: str | None = None
    frame_url: str | None = None
    top_level_url: str | None = None
    is_third_party: int = 0


@dataclass
class ScriptRecord:
    visit_id: str
    script_url: str
    is_third_party: int = 0
    matched_blocklist_entries: list[str] = field(default_factory=list)
    high_entropy_signals_count: int = 0


@dataclass
class ClassificationRecord:
    run_id: str
    visit_id: str
    domain: str
    script_url: str
    vector: str
    flagged: int
    confidence: str
    evidence: dict[str, Any] = field(default_factory=dict)
    is_third_party: int = 0
