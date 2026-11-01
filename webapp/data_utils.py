"""Small helpers for presenting research records without changing stored data."""

from __future__ import annotations

import csv
from pathlib import Path

from fpstudy.sample import normalize_domain


def blocking_counter_is_measured(condition: str) -> bool:
    """The crawler counts network request blocks via route aborts and extension ERR_BLOCKED_BY_CLIENT."""
    return condition in {"baseline", "blocklist", "extension_ubol", "extension_ublock", "brave_shields"}


def get_protection_info(condition: str) -> dict[str, str | bool]:
    """Return academic metadata describing the countermeasure architecture and proof mechanism."""
    mapping: dict[str, dict[str, str | bool]] = {
        "baseline": {
            "name": "Control Baseline (Stock Chromium)",
            "short_name": "Baseline",
            "type": "Control Group",
            "layer": "None (Unmodified Browser)",
            "mechanism": "Unmodified stock Chromium with no content filters, extensions, or API spoofing active.",
            "proof_metric": "Serves as the empirical reference standard for baseline prevalence and fingerprinting scripts.",
            "is_network_blocking": False,
            "is_execution_spoofing": False,
            "badge_color": "secondary",
            "icon": "bi-circle",
        },
        "blocklist": {
            "name": "EasyPrivacy Network Filter (Brave Adblock Engine)",
            "short_name": "EasyPrivacy",
            "type": "Network Rule Matcher",
            "layer": "Network Perimeter (Pre-dispatch Abort)",
            "mechanism": "Intercepts all outgoing subresource requests against the EasyPrivacy ruleset using Brave's Rust adblock engine. Tracking and fingerprinting requests are aborted with blockedbyclient before downloading.",
            "proof_metric": "Exact count of aborted network requests + elimination of third-party tracking scripts.",
            "is_network_blocking": True,
            "is_execution_spoofing": False,
            "badge_color": "primary",
            "icon": "bi-shield-fill-check",
        },
        "extension_ubol": {
            "name": "uBlock Origin Lite (Manifest V3)",
            "short_name": "uBlock Origin Lite",
            "type": "Browser Extension (MV3 DNR)",
            "layer": "Native Chromium Network Stack",
            "mechanism": "Enforces precompiled declarativeNetRequest (DNR) filter rules (EasyPrivacy + uBlock Filters) directly inside Chromium's network layer. Blocked tracking requests fail natively with net::ERR_BLOCKED_BY_CLIENT.",
            "proof_metric": "Count of native net::ERR_BLOCKED_BY_CLIENT network drops + script suppression in paired comparison.",
            "is_network_blocking": True,
            "is_execution_spoofing": False,
            "badge_color": "info",
            "icon": "bi-shield-shaded",
        },
        "extension_ublock": {
            "name": "uBlock Origin Lite (Manifest V3)",
            "short_name": "uBlock Origin Lite",
            "type": "Browser Extension (MV3 DNR)",
            "layer": "Native Chromium Network Stack",
            "mechanism": "Enforces precompiled declarativeNetRequest (DNR) filter rules inside Chromium. Blocked requests fail with net::ERR_BLOCKED_BY_CLIENT.",
            "proof_metric": "Count of native net::ERR_BLOCKED_BY_CLIENT network drops + script suppression.",
            "is_network_blocking": True,
            "is_execution_spoofing": False,
            "badge_color": "info",
            "icon": "bi-shield-shaded",
        },
        "canvas_defender": {
            "name": "Canvas Defender (Pixel Farbling / Noise Injection)",
            "short_name": "Canvas Defender",
            "type": "DOM / API Data Poisoning",
            "layer": "Execution / Readback Layer (In-Memory Buffer)",
            "mechanism": "Does NOT block network requests. Instead, intercepts CanvasRenderingContext2D.getImageData and HTMLCanvasElement.toDataURL, injecting subtle pseudo-random RGB noise (Farbling) so trackers receive dynamic, poisoned hashes.",
            "proof_metric": "API farbling active; canvas readbacks dynamically poisoned across visits, preventing persistent cross-session tracking.",
            "is_network_blocking": False,
            "is_execution_spoofing": True,
            "badge_color": "warning",
            "icon": "bi-palette2",
        },
        "brave_shields": {
            "name": "Brave Shields (Hybrid Network + Farbling)",
            "short_name": "Brave Shields",
            "type": "Native Browser Protections",
            "layer": "Hybrid (C++ Adblock Engine + Farbling Subsystem)",
            "mechanism": "Combines native Rust network filter blocking (dropping tracker requests) with built-in farbling on Canvas, WebGL, and Audio readback APIs.",
            "proof_metric": "Dual proof: native network request blocks + randomized canvas/WebGL/audio signatures.",
            "is_network_blocking": True,
            "is_execution_spoofing": True,
            "badge_color": "success",
            "icon": "bi-shield-lock-fill",
        },
        "firefox_rfp": {
            "name": "Firefox Resist Fingerprinting (RFP)",
            "short_name": "Firefox RFP",
            "type": "Browser Standardization",
            "layer": "Browser Engine (Tor Uplift)",
            "mechanism": "Standardizes browser metrics: rounds display dimensions, locks timezone to UTC, spoofing canvas readbacks, and adds noise to audio/timing APIs.",
            "proof_metric": "Metric homogenization: UTC timezone lock, fixed screen resolution buckets, and canvas permission prompts.",
            "is_network_blocking": False,
            "is_execution_spoofing": True,
            "badge_color": "secondary",
            "icon": "bi-browser-firefox",
        },
    }
    return mapping.get(
        condition,
        {
            "name": condition.replace("_", " ").title(),
            "short_name": condition,
            "type": "Experimental Countermeasure",
            "layer": "Configured Condition",
            "mechanism": "Applied countermeasure for browser privacy evaluation.",
            "proof_metric": "Observed reduction in fingerprinting prevalence and script activity.",
            "is_network_blocking": False,
            "is_execution_spoofing": False,
            "badge_color": "secondary",
            "icon": "bi-shield",
        },
    )


def rank_domains(domains: set[str], preferred_list_id: str | None = None) -> dict[str, int]:
    """Find Tranco ranks for displayed domains, scanning only the sampled top 5,000."""
    if not domains:
        return {}

    directory = Path("data/tranco")
    preferred = directory / f"tranco_{preferred_list_id}.csv" if preferred_list_id else None
    files = ([preferred] if preferred and preferred.is_file() else []) + [
        path for path in sorted(directory.glob("*.csv")) if path != preferred
    ]
    found: dict[str, int] = {}

    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row_number, row in enumerate(csv.reader(source), start=1):
                if not row:
                    continue
                if len(row) > 1 and row[0].strip().isdigit():
                    rank, domain = int(row[0]), normalize_domain(row[1])
                else:
                    rank, domain = row_number, normalize_domain(row[0])
                if rank > 5000:
                    break
                if domain in domains:
                    found[domain] = rank
                    if len(found) == len(domains):
                        return found
    return found


def rank_domains_from_file(path: Path, domains: set[str]) -> dict[str, int]:
    """Read ranks from the exact list selected for a crawl."""
    found: dict[str, int] = {}
    if not path.is_file() or not domains:
        return found
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row_number, row in enumerate(csv.reader(source), start=1):
            if not row:
                continue
            if len(row) > 1 and row[0].strip().isdigit():
                rank, domain = int(row[0]), normalize_domain(row[1])
            else:
                rank, domain = row_number, normalize_domain(row[0])
            if domain in domains:
                found[domain] = rank
                if len(found) == len(domains):
                    break
    return found
