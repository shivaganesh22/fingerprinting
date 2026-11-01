"""Background crawler service executing research crawls in non-blocking threads."""

from __future__ import annotations

import asyncio
import copy
import logging
import shutil
import threading
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from django.utils import timezone

from fpstudy.config import StudyConfig, load_study_config
from fpstudy.crawler.runner import CrawlRunner
from fpstudy.detection.classify import ScriptClassifier
from fpstudy.sample import SampleManager
from fpstudy.storage.schema import VisitRecord
from fpstudy.storage.store import DataStore
from webapp.data_utils import blocking_counter_is_measured, rank_domains, rank_domains_from_file
from webapp.models import CrawlJob, Run, Visit

logger = logging.getLogger(__name__)

# In-memory registry of active crawl jobs
_active_jobs_lock = threading.Lock()
_active_jobs: dict[str, dict[str, Any]] = {}


def get_supported_conditions() -> dict[str, dict[str, Any]]:
    """Inspect host system and return supported vs unsupported crawl conditions with honest notes."""
    brave_path = Path("/usr/bin/brave-browser")
    brave_available = brave_path.is_file()
    playwright_firefox_installed = any(Path.home().joinpath(".cache/ms-playwright").glob("firefox-*"))
    firefox_available = shutil.which("firefox") is not None or playwright_firefox_installed
    ubol_manifest = Path("data/extensions/ubol/unpacked/manifest.json").is_file()

    return {
        "baseline": {
            "name": "baseline",
            "label": "Baseline (Vanilla Chromium)",
            "supported": True,
            "browser": "Chromium",
            "type": "Control condition",
            "description": "Stock Chromium with standard user agent and instrumentation hooks. Serves as experimental control.",
            "status_badge": "Supported",
        },
        "blocklist": {
            "name": "blocklist",
            "label": "EasyPrivacy Network Blocklist",
            "supported": True,
            "browser": "Chromium",
            "type": "Network rule matching",
            "description": "Network request blocking compiled via Rust adblock engine with EasyPrivacy tracker rules.",
            "status_badge": "Supported",
        },
        "extension_ubol": {
            "name": "extension_ubol",
            "label": "uBlock Origin Lite (MV3)",
            "supported": ubol_manifest,
            "browser": "Chromium",
            "type": "MV3 Extension",
            "description": "Genuine unpacked uBlock Origin Lite MV3 extension loaded in persistent profile using declarativeNetRequest.",
            "status_badge": "Supported" if ubol_manifest else "Missing Files",
        },
        "canvas_defender": {
            "name": "canvas_defender",
            "label": "Canvas Defender (Noise Simulation)",
            "supported": True,
            "browser": "Chromium",
            "type": "API noise injection",
            "description": "Injects subtle pseudo-random noise into HTML5 Canvas readbacks to disrupt fingerprint uniqueness.",
            "status_badge": "Supported",
        },
        "brave_shields": {
            "name": "brave_shields",
            "label": "Brave Shields",
            "supported": brave_available,
            "browser": "Brave Browser",
            "type": "Native browser defense",
            "description": f"Brave browser binary with native Shields privacy countermeasure active ({brave_path})."
            if brave_available
            else "Brave binary not found at /usr/bin/brave-browser",
            "status_badge": "Supported" if brave_available else "Not Installed",
        },
        "firefox_rfp": {
            "name": "firefox_rfp",
            "label": "Firefox RFP (privacy.resistFingerprinting)",
            "supported": firefox_available,
            "browser": "Firefox",
            "type": "Browser-level defense",
            "description": (
                "Firefox with privacy.resistFingerprinting enabled."
                if firefox_available
                else "Optional condition. Install Firefox on this machine to run it with privacy.resistFingerprinting enabled."
            ),
            "status_badge": "Supported" if firefox_available else "Not Installed",
        },
    }


def estimate_workload(sample_size: int, dwell_time_seconds: float = 5.0, concurrency: int = 2) -> dict[str, Any]:
    """Calculate realistic workload and time estimation for a planned crawl."""
    # Estimated average page navigation + network latency is ~4.0s
    avg_per_domain = dwell_time_seconds + 4.0
    total_effective_seconds = (sample_size * avg_per_domain) / max(1, concurrency)

    minutes = int(total_effective_seconds // 60)
    seconds = int(total_effective_seconds % 60)
    hours = minutes // 60
    rem_minutes = minutes % 60

    if hours > 0:
        time_formatted = f"~{hours}h {rem_minutes}m"
    elif minutes > 0:
        time_formatted = f"~{minutes}m {seconds}s"
    else:
        time_formatted = f"~{seconds}s"

    is_large = sample_size > 500
    warning = ""
    if sample_size > 1000:
        warning = "Caution: Crawling over 1,000 domains will take several hours. The crawl runs in a detached background thread; you may safely navigate away."
    elif sample_size > 300:
        warning = "Note: Medium crawl workload. Robots.txt and per-domain polite rate limits are strictly enforced."

    return {
        "sample_size": sample_size,
        "concurrency": concurrency,
        "dwell_time_seconds": dwell_time_seconds,
        "estimated_total_seconds": round(total_effective_seconds, 1),
        "estimated_time_formatted": time_formatted,
        "is_large": is_large,
        "warning": warning,
    }


class CrawlerWorkerThread(threading.Thread):
    """Background worker thread running a Playwright CrawlRunner."""

    def __init__(
        self,
        run_id: str,
        condition: str,
        domains: list[str],
        config: StudyConfig,
        resume: bool = True,
        domain_ranks: dict[str, int] | None = None,
    ):
        super().__init__(daemon=True, name=f"CrawlWorker-{run_id}")
        self.run_id = run_id
        self.condition = condition
        self.domains = domains
        self.config = config
        self.resume = resume
        self.domain_ranks = domain_ranks or {}
        self.runner: CrawlRunner | None = None
        self.error: Exception | None = None
        self.start_time = time.time()

    def on_visit_done(self, visit_rec: VisitRecord) -> None:
        """Callback invoked immediately when a domain visit finishes."""
        with _active_jobs_lock:
            job_state = _active_jobs.get(self.run_id)
            if not job_state:
                return

            job_state["current_domain"] = visit_rec.domain
            job_state["current_rank"] = self.domain_ranks.get(visit_rec.domain)
            job_state["attempted_count"] += 1
            if visit_rec.status == "ok":
                job_state["completed_count"] += 1
            elif visit_rec.status.startswith("skipped"):
                job_state["skipped_count"] += 1
            else:
                job_state["failed_count"] += 1

            total_visited = job_state["attempted_count"]
            job_state["percent"] = min(
                100, int((total_visited / max(1, job_state["domains_total"])) * 100)
            )

            # Record in recent visits deque
            job_state["recent_visits"].append(
                {
                    "domain": visit_rec.domain,
                    "rank": self.domain_ranks.get(visit_rec.domain),
                    "status": visit_rec.status,
                    "http_status": visit_rec.http_status,
                    "load_time_ms": round(visit_rec.load_time_ms, 1) if visit_rec.load_time_ms else None,
                    "requests_count": visit_rec.requests_count,
                    "blocked_requests": visit_rec.blocked_requests_count if blocking_counter_is_measured(self.condition) else None,
                    "ts": datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%H:%M:%S IST"),
                }
            )
            if len(job_state["recent_visits"]) > 25:
                job_state["recent_visits"].pop(0)

            # Sync to DB model
            try:
                CrawlJob.objects.filter(run_id=self.run_id).update(
                    current_domain=visit_rec.domain,
                    completed_count=job_state["completed_count"],
                    failed_count=job_state["failed_count"],
                    skipped_count=job_state["skipped_count"],
                )
            except Exception:
                pass

    def run(self) -> None:
        """Worker thread entrypoint executing asyncio event loop."""
        logger.info(f"Background worker thread started for run {self.run_id}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        with _active_jobs_lock:
            if self.run_id in _active_jobs:
                _active_jobs[self.run_id]["status"] = "running"
        try:
            CrawlJob.objects.filter(run_id=self.run_id).update(
                status="running", started_at=timezone.now()
            )
        except Exception:
            pass

        try:
            store = DataStore(self.config.storage.database_path)
            self.runner = CrawlRunner(
                config=self.config,
                condition_name=self.condition,
                store=store,
                run_id=self.run_id,
                on_visit_complete=self.on_visit_done,
            )

            with _active_jobs_lock:
                if self.run_id in _active_jobs:
                    _active_jobs[self.run_id]["runner"] = self.runner

            # Run crawler
            loop.run_until_complete(
                self.runner.run(self.domains, resume=self.resume, limit=len(self.domains))
            )

            # Classify raw events immediately after run
            logger.info(f"Running automated classification for run {self.run_id}")
            classifier = ScriptClassifier(self.config, store=store)
            classifier.classify_run(self.run_id)

            status = "cancelled" if self.runner._shutdown_requested else "completed"
            with _active_jobs_lock:
                if self.run_id in _active_jobs:
                    _active_jobs[self.run_id]["status"] = status
                    if status == "completed":
                        _active_jobs[self.run_id]["percent"] = 100

            try:
                CrawlJob.objects.filter(run_id=self.run_id).update(
                    status=status,
                    finished_at=timezone.now(),
                )
            except Exception:
                pass

        except Exception as exc:
            logger.error(f"Background crawler failed for {self.run_id}: {exc}", exc_info=True)
            self.error = exc
            with _active_jobs_lock:
                if self.run_id in _active_jobs:
                    _active_jobs[self.run_id]["status"] = "failed"
                    _active_jobs[self.run_id]["error"] = str(exc)
            try:
                CrawlJob.objects.filter(run_id=self.run_id).update(
                    status="failed",
                    error_message=str(exc),
                    finished_at=timezone.now(),
                )
            except Exception:
                pass
        finally:
            loop.close()
            logger.info(f"Background worker thread finished for run {self.run_id}")


def start_crawl_job(
    condition: str,
    sample_size: int,
    domain_source: str = "tranco_GQ3LK.csv",
    dwell_time_seconds: float = 5.0,
    navigation_timeout_seconds: float = 30.0,
    max_retries: int = 1,
    concurrency: int = 2,
    headless: bool = True,
    resume: bool = True,
    run_id: str | None = None,
) -> str:
    """Launch a new crawl run in the background."""
    supported = get_supported_conditions()
    if condition not in supported or not supported[condition]["supported"]:
        raise ValueError(
            f"Condition '{condition}' is not supported on this host: {supported.get(condition, {}).get('description')}"
        )

    active_run_id = (
        run_id
        or f"run_{condition}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    )

    # Load master config
    cfg = load_study_config("config/default.yaml")

    # Apply user overrides
    cfg.crawler.dwell_time_seconds = float(dwell_time_seconds)
    cfg.crawler.navigation_timeout_seconds = float(navigation_timeout_seconds)
    cfg.crawler.max_retries = int(max_retries)
    cfg.crawler.concurrency = int(concurrency)

    # Enable condition in config if needed (e.g. brave_shields)
    if condition == "brave_shields":
        cond_def = cfg.conditions.conditions.get("brave_shields")
        if cond_def:
            cond_def.enabled = True

    # Load domain sample
    sample_mgr = SampleManager(cfg.sample.download_dir, cfg.sample.manifest_path)
    csv_file = Path(cfg.sample.download_dir) / domain_source
    if not csv_file.is_file():
        # Fallback to standard tranco file
        csv_file = Path(cfg.sample.download_dir) / f"tranco_{cfg.sample.tranco_list_id}.csv"

    domains = sample_mgr.get_sample(csv_file, top_n=min(5000, sample_size))
    domain_ranks = rank_domains_from_file(csv_file, set(domains))

    # Create CrawlJob record
    CrawlJob.objects.update_or_create(
        run_id=active_run_id,
        defaults={
            "condition": condition,
            "sample_size": len(domains),
            "status": "queued",
            "domains_total": len(domains),
            "completed_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "started_at": timezone.now(),
        },
    )

    # Register in-memory job state
    with _active_jobs_lock:
        _active_jobs[active_run_id] = {
            "run_id": active_run_id,
            "condition": condition,
            "domains_total": len(domains),
            "completed_count": 0,
            "attempted_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "current_domain": None,
            "current_rank": None,
            "percent": 0,
            "status": "queued",
            "start_time": time.time(),
            "recent_visits": [],
            "domain_ranks": domain_ranks,
            "error": None,
            "runner": None,
        }

    # Start thread
    worker = CrawlerWorkerThread(
        run_id=active_run_id,
        condition=condition,
        domains=domains,
        config=cfg,
        resume=resume,
        domain_ranks=domain_ranks,
    )
    worker.start()

    return active_run_id


def cancel_crawl_job(run_id: str) -> bool:
    """Request graceful cancellation of a running crawl job."""
    with _active_jobs_lock:
        job = _active_jobs.get(run_id)
        if job and job.get("runner"):
            job["runner"].request_shutdown()
            job["status"] = "cancelling"
            try:
                CrawlJob.objects.filter(run_id=run_id).update(status="cancelled")
            except Exception:
                pass
            return True

    # If not in active memory, check DB
    updated = CrawlJob.objects.filter(run_id=run_id, status__in=["queued", "running"]).update(
        status="cancelled"
    )
    return bool(updated)


def get_job_progress(run_id: str) -> dict[str, Any]:
    """Retrieve structured progress information for polling or status views."""
    with _active_jobs_lock:
        mem_job = _active_jobs.get(run_id)
        if mem_job:
            elapsed = time.time() - mem_job["start_time"]
            total = mem_job["domains_total"]
            done = mem_job["attempted_count"]
            eta = round((elapsed / done * (total - done)), 1) if done > 0 and total > done else 0

            return {
                "run_id": run_id,
                "condition": mem_job["condition"],
                "status": mem_job["status"],
                "current_domain": mem_job["current_domain"],
                "current_rank": mem_job.get("current_rank"),
                "domains_total": total,
                "attempted_count": done,
                "completed_count": mem_job["completed_count"],
                "failed_count": mem_job["failed_count"],
                "skipped_count": mem_job["skipped_count"],
                "percent": mem_job["percent"],
                "elapsed_seconds": int(elapsed),
                "eta_seconds": int(eta),
                "recent_visits": list(mem_job["recent_visits"]),
                "blocked_counter_measured": blocking_counter_is_measured(mem_job["condition"]),
                "error": mem_job.get("error"),
                "is_active": mem_job["status"] in ("queued", "running", "cancelling"),
            }

    # Check database for historical or completed runs
    try:
        db_job = CrawlJob.objects.filter(run_id=run_id).first()
        run_record = Run.objects.filter(run_id=run_id).first()
        visits_count = Visit.objects.filter(run_id=run_id).count()
        ok_count = Visit.objects.filter(run_id=run_id, status="ok").count()
        failed_count = (
            Visit.objects.filter(run_id=run_id)
            .exclude(status="ok")
            .exclude(status__startswith="skipped")
            .count()
        )
        skipped_count = Visit.objects.filter(run_id=run_id, status__startswith="skipped").count()

        status = db_job.status if db_job else ("completed" if run_record else "not_found")
        total = db_job.domains_total if db_job and db_job.domains_total else max(visits_count, 1)

        run_condition = run_record.condition if run_record else (db_job.condition if db_job else "")
        rank_map = rank_domains(
            set(Visit.objects.filter(run_id=run_id).values_list("domain", flat=True)),
            run_record.tranco_list_id if run_record else None,
        )
        recent_v = (
            Visit.objects.filter(run_id=run_id)
            .order_by("-start_time")[:15]
            .values("domain", "status", "http_status", "load_time_ms", "requests_count", "blocked_requests_count")
        )

        return {
            "run_id": run_id,
            "condition": run_condition or "unknown",
            "status": status,
            "current_domain": db_job.current_domain if db_job else None,
            "current_rank": rank_map.get(db_job.current_domain) if db_job else None,
            "domains_total": total,
            "attempted_count": visits_count,
            "completed_count": ok_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
            "percent": 100 if status == "completed" else min(100, int((visits_count / total) * 100)),
            "elapsed_seconds": 0,
            "eta_seconds": 0,
            "recent_visits": [
                {
                    "domain": v["domain"],
                    "status": v["status"],
                    "http_status": v["http_status"],
                    "load_time_ms": round(v["load_time_ms"], 1) if v["load_time_ms"] else None,
                    "requests_count": v["requests_count"],
                    "blocked_requests": v["blocked_requests_count"] if blocking_counter_is_measured(run_condition) else None,
                    "rank": rank_map.get(v["domain"]),
                    "ts": "",
                }
                for v in recent_v
            ],
            "blocked_counter_measured": blocking_counter_is_measured(run_condition),
            "error": db_job.error_message if db_job else None,
            "is_active": False,
        }
    except Exception as exc:
        return {
            "run_id": run_id,
            "status": "unknown",
            "error": str(exc),
            "is_active": False,
        }
