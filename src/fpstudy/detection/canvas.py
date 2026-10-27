"""Canvas fingerprinting detector based on Englehardt & Narayanan (OpenWPM, 2016)."""

from __future__ import annotations

from typing import Any

from fpstudy.config import CanvasRules
from fpstudy.storage.schema import ClassificationRecord, EventRecord


class CanvasDetector:
    """Detects canvas fingerprinting based on Englehardt & Narayanan (2016) heuristics.

    Criteria:
    1. Canvas width and height each >= min_width/min_height (default 16 px).
    2. Text drawn with >= min_colors (default 2) distinct colors or >= min_text_length (default 10) chars.
    3. Image readback executed (toDataURL or getImageData with area >= min_area).
    4. Manipulation safeguards: no save/restore or event listeners called on that canvas.
    """

    def __init__(self, rules: CanvasRules | None = None):
        self.rules = rules or CanvasRules()

    def analyze_events(
        self,
        script_url: str,
        events: list[EventRecord],
        run_id: str = "",
        visit_id: str = "",
        domain: str = "",
        is_third_party: int = 0,
    ) -> ClassificationRecord:
        """Classify canvas events for a single script within a visit."""
        canvas_events = [e for e in events if e.api == "canvas"]

        # Track evidence
        has_min_dimensions = False
        text_lengths: list[int] = []
        drawn_colors: set[str] = set()
        readback_methods: list[str] = []
        has_save_or_restore = False
        has_event_listener = False
        max_dim = (0, 0)

        for e in canvas_events:
            method = e.method_or_property
            args = e.args_summary or {}

            # Check dimensions
            w = args.get("width")
            h = args.get("height")
            if w is not None and h is not None:
                try:
                    w_int, h_int = int(w), int(h)
                    if w_int > max_dim[0]:
                        max_dim = (w_int, max_dim[1])
                    if h_int > max_dim[1]:
                        max_dim = (max_dim[0], h_int)
                    if w_int >= self.rules.min_width and h_int >= self.rules.min_height:
                        has_min_dimensions = True
                except (ValueError, TypeError):
                    pass

            # Check text drawing
            if method in ("fillText", "strokeText"):
                length = args.get("text_length", 0)
                text_lengths.append(int(length))
                color = args.get("fillStyle") or args.get("strokeStyle")
                if color:
                    drawn_colors.add(str(color).strip().lower())

            # Check readback
            if method in ("toDataURL", "toBlob"):
                readback_methods.append(method)
            elif method == "getImageData":
                area = args.get("area", 0)
                if area >= self.rules.min_image_data_area:
                    readback_methods.append(f"getImageData(area={area})")

            # Check exclusions
            if method in ("save", "restore"):
                has_save_or_restore = True
            if method == "addEventListener":
                has_event_listener = True

        # Evaluate rules
        condition_dim = has_min_dimensions
        condition_text = (
            any(tl >= self.rules.min_text_length for tl in text_lengths)
            or len(drawn_colors) >= self.rules.min_distinct_colors
        )
        condition_readback = len(readback_methods) > 0 if self.rules.require_readback else True
        condition_exclusions = True
        if self.rules.exclude_if_save_or_restore and has_save_or_restore:
            condition_exclusions = False
        if self.rules.exclude_if_event_listener and has_event_listener:
            condition_exclusions = False

        flagged = bool(
            condition_dim and condition_text and condition_readback and condition_exclusions
        )

        confidence = "none"
        if flagged:
            confidence = (
                "high" if len(readback_methods) > 0 and len(drawn_colors) >= 2 else "medium"
            )

        evidence: dict[str, Any] = {
            "max_dimensions": list(max_dim),
            "max_text_length": max(text_lengths) if text_lengths else 0,
            "distinct_colors": list(drawn_colors),
            "readback_methods": readback_methods,
            "has_save_or_restore": has_save_or_restore,
            "has_event_listener": has_event_listener,
            "rule_evaluation": {
                "dimensions_ok": condition_dim,
                "text_drawn_ok": condition_text,
                "readback_ok": condition_readback,
                "exclusions_ok": condition_exclusions,
            },
        }

        return ClassificationRecord(
            run_id=run_id,
            visit_id=visit_id,
            domain=domain,
            script_url=script_url,
            vector="canvas",
            flagged=1 if flagged else 0,
            confidence=confidence,
            evidence=evidence,
            is_third_party=is_third_party,
        )
