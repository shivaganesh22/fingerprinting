"""Supporting browser signals and property breadth analysis."""

from __future__ import annotations

from typing import Any

from fpstudy.config import SignalsRules
from fpstudy.storage.schema import EventRecord


class SignalsAnalyzer:
    """Analyzes supporting high-entropy navigator, screen, and system property reads."""

    def __init__(self, rules: SignalsRules | None = None):
        self.rules = rules or SignalsRules()

    def analyze_script_signals(
        self,
        script_url: str,
        events: list[EventRecord],
    ) -> dict[str, Any]:
        """Compute signal breadth and enumerate distinct high-entropy properties accessed."""
        signals_events = [e for e in events if e.api == "signals"]
        accessed_properties: set[str] = set()

        for e in signals_events:
            prop = e.method_or_property
            accessed_properties.add(prop)

        breadth_score = len(accessed_properties)
        high_breadth = breadth_score >= self.rules.breadth_threshold

        return {
            "script_url": script_url,
            "breadth_score": breadth_score,
            "high_breadth": high_breadth,
            "accessed_properties": sorted(accessed_properties),
        }
