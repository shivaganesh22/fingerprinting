"""Font enumeration and probing detector."""

from __future__ import annotations

import re
from typing import Any

from fpstudy.config import FontsRules
from fpstudy.storage.schema import ClassificationRecord, EventRecord


def extract_font_family_from_css(font_string: str) -> list[str]:
    """Parse distinct font family names from a CSS font or fontFamily string."""
    if not font_string:
        return []
    # Strip size, weight, style tokens if present (e.g. '12px "Comic Sans MS", sans-serif')
    clean = re.sub(r"\b\d+(?:px|pt|em|rem|%)\b", "", font_string)
    clean = re.sub(r"\b(?:bold|italic|normal|small-caps|bolder|lighter)\b", "", clean, flags=re.I)
    # Split comma separated font lists
    families = []
    for part in clean.split(","):
        f = part.strip().strip("'\"")
        if (
            f
            and len(f) > 1
            and f.lower() not in ("sans-serif", "serif", "monospace", "cursive", "fantasy")
        ):
            families.append(f.lower())
    return families


class FontsDetector:
    """Detects font probing and enumeration (measureText, element dimensions, document.fonts.check)."""

    def __init__(self, rules: FontsRules | None = None):
        self.rules = rules or FontsRules()

    def analyze_events(
        self,
        script_url: str,
        events: list[EventRecord],
        run_id: str = "",
        visit_id: str = "",
        domain: str = "",
        is_third_party: int = 0,
    ) -> ClassificationRecord:
        """Classify font probing events for a single script within a visit."""
        tested_fonts: set[str] = set()
        methods_observed: set[str] = set()
        probe_count = 0

        for e in events:
            method = e.method_or_property
            args = e.args_summary or {}

            # Canvas measureText probing
            if e.api == "canvas" and method == "measureText":
                probe_count += 1
                font_str = str(args.get("font", ""))
                for f in extract_font_family_from_css(font_str):
                    tested_fonts.add(f)
                    methods_observed.add("canvas.measureText")

            # DOM element dimension probing
            elif e.api == "fonts":
                probe_count += 1
                if method.startswith("element.offset"):
                    font_family = str(args.get("fontFamily", ""))
                    for f in extract_font_family_from_css(font_family):
                        tested_fonts.add(f)
                        methods_observed.add(method)
                elif method == "document.fonts.check":
                    font_name = str(args.get("font", ""))
                    for f in extract_font_family_from_css(font_name):
                        tested_fonts.add(f)
                        methods_observed.add("document.fonts.check")
                elif method == "FontFace":
                    family = str(args.get("family", ""))
                    if family:
                        tested_fonts.add(family.lower())
                        methods_observed.add("FontFace")

        distinct_count = len(tested_fonts)
        flagged = distinct_count >= self.rules.min_distinct_fonts

        confidence = "none"
        if flagged:
            confidence = "high" if distinct_count >= 50 else "medium"

        evidence: dict[str, Any] = {
            "distinct_fonts_count": distinct_count,
            "sample_tested_fonts": sorted(tested_fonts)[:30],
            "total_font_probes": probe_count,
            "methods_observed": list(methods_observed),
            "threshold": self.rules.min_distinct_fonts,
        }

        return ClassificationRecord(
            run_id=run_id,
            visit_id=visit_id,
            domain=domain,
            script_url=script_url,
            vector="fonts",
            flagged=1 if flagged else 0,
            confidence=confidence,
            evidence=evidence,
            is_third_party=is_third_party,
        )
