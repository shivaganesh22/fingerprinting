"""Small helpers for presenting research records without changing stored data."""

from __future__ import annotations

import csv
from pathlib import Path

from fpstudy.sample import normalize_domain


def blocking_counter_is_measured(condition: str) -> bool:
    """The crawler can count its own route blocks; native extension blocks are opaque."""
    return condition in {"baseline", "blocklist"}


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
