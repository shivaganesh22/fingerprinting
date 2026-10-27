"""Classification coordinator: per-script and per-site aggregation."""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from fpstudy.config import StudyConfig
from fpstudy.detection.audio import AudioDetector
from fpstudy.detection.blocklist_match import BlocklistMatcher
from fpstudy.detection.canvas import CanvasDetector
from fpstudy.detection.fonts import FontsDetector
from fpstudy.detection.signals import SignalsAnalyzer
from fpstudy.detection.webgl import WebGLDetector
from fpstudy.storage.schema import ClassificationRecord, EventRecord
from fpstudy.storage.store import DataStore

logger = logging.getLogger(__name__)


class ScriptClassifier:
    """Classifies script-level and site-level fingerprinting behavior from raw events."""

    def __init__(
        self,
        config: StudyConfig,
        store: DataStore | None = None,
        blocklist_matcher: BlocklistMatcher | None = None,
    ):
        self.config = config
        self.store = store or DataStore(config.storage.database_path)
        self.rules = config.detection_rules

        self.canvas_detector = CanvasDetector(self.rules.canvas)
        self.webgl_detector = WebGLDetector(self.rules.webgl)
        self.audio_detector = AudioDetector(self.rules.audio)
        self.fonts_detector = FontsDetector(self.rules.fonts)
        self.signals_analyzer = SignalsAnalyzer(self.rules.signals)
        self.blocklist_matcher = blocklist_matcher or BlocklistMatcher(
            easyprivacy_path=config.paths.get(
                "easyprivacy_path", "data/blocklists/easyprivacy.txt"
            ),
            disconnect_path=config.paths.get(
                "disconnect_path", "data/blocklists/disconnect_blacklist.json"
            ),
        )

    def classify_visit(
        self,
        run_id: str,
        visit_id: str,
        domain: str,
        events: list[EventRecord],
    ) -> list[ClassificationRecord]:
        """Classify all scripts observed during a single site visit."""
        # Group events by script_url
        script_events: dict[str, list[EventRecord]] = defaultdict(list)
        for e in events:
            script_url = e.script_url or "unknown"
            script_events[script_url].append(e)

        records: list[ClassificationRecord] = []

        for script_url, s_events in script_events.items():
            is_3p = s_events[0].is_third_party if s_events else 0

            # 1. Canvas
            rec_canvas = self.canvas_detector.analyze_events(
                script_url, s_events, run_id, visit_id, domain, is_3p
            )
            records.append(rec_canvas)

            # 2. WebGL
            rec_webgl = self.webgl_detector.analyze_events(
                script_url, s_events, run_id, visit_id, domain, is_3p
            )
            records.append(rec_webgl)

            # 3. Audio
            rec_audio = self.audio_detector.analyze_events(
                script_url, s_events, run_id, visit_id, domain, is_3p
            )
            records.append(rec_audio)

            # 4. Fonts
            rec_fonts = self.fonts_detector.analyze_events(
                script_url, s_events, run_id, visit_id, domain, is_3p
            )
            records.append(rec_fonts)

        return records

    def classify_run(self, run_id: str) -> dict[str, Any]:
        """Regenerate and store all classifications for a run directly from raw events."""
        logger.info(f"Classifying raw events for run_id: {run_id}")
        self.store.clear_classifications(run_id)

        visits = self.store.get_visits(run_id)
        all_classifications: list[ClassificationRecord] = []

        for v in visits:
            visit_id = v["visit_id"]
            domain = v["domain"]
            raw_events_rows = self.store.get_events_for_visit(visit_id)
            event_records = [
                EventRecord(
                    visit_id=row["visit_id"],
                    ts=row["ts"],
                    api=row["api"],
                    method_or_property=row["method_or_property"],
                    args_summary=eval(row["args_summary"])
                    if isinstance(row["args_summary"], str)
                    else (row["args_summary"] or {}),
                    return_summary=eval(row["return_summary"])
                    if isinstance(row["return_summary"], str)
                    else (row["return_summary"] or {}),
                    script_url=row["script_url"],
                    stack_excerpt=row["stack_excerpt"],
                    frame_url=row["frame_url"],
                    top_level_url=row["top_level_url"],
                    is_third_party=row["is_third_party"],
                )
                for row in raw_events_rows
            ]

            visit_records = self.classify_visit(run_id, visit_id, domain, event_records)
            all_classifications.extend(visit_records)

        self.store.insert_classifications(all_classifications)
        logger.info(f"Stored {len(all_classifications)} classification records for run {run_id}")

        summary = self.aggregate_site_metrics(run_id)
        return summary

    def aggregate_site_metrics(self, run_id: str) -> dict[str, Any]:
        """Aggregate script classifications into per-site fingerprinting outcomes."""
        rows = self.store.get_classifications_for_run(run_id)

        site_metrics: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "fingerprints_any": False,
                "vectors_flagged": set(),
                "flagged_scripts": set(),
                "first_party_fp": False,
                "third_party_fp": False,
            }
        )

        for r in rows:
            domain = r["domain"]
            flagged = bool(r["flagged"])
            vector = r["vector"]
            script = r["script_url"]
            is_3p = bool(r["is_third_party"])

            if flagged:
                site_metrics[domain]["fingerprints_any"] = True
                site_metrics[domain]["vectors_flagged"].add(vector)
                site_metrics[domain]["flagged_scripts"].add(script)
                if is_3p:
                    site_metrics[domain]["third_party_fp"] = True
                else:
                    site_metrics[domain]["first_party_fp"] = True

        total_sites = len(self.store.get_visits(run_id))
        fp_sites = sum(1 for m in site_metrics.values() if m["fingerprints_any"])

        return {
            "run_id": run_id,
            "total_sites_visited": total_sites,
            "sites_fingerprinting": fp_sites,
            "overall_prevalence": (fp_sites / total_sites) if total_sites > 0 else 0.0,
            "site_details": {
                dom: {
                    "fingerprints_any": m["fingerprints_any"],
                    "vectors_flagged": list(m["vectors_flagged"]),
                    "n_fp_scripts": len(m["flagged_scripts"]),
                    "first_party_fp": m["first_party_fp"],
                    "third_party_fp": m["third_party_fp"],
                }
                for dom, m in site_metrics.items()
            },
        }
