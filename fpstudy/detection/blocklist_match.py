"""Blocklist cross-checking against EasyPrivacy and Disconnect datasets."""

from __future__ import annotations

import json
from pathlib import Path

from adblock import Engine, FilterSet

from fpstudy.instrumentation.loader import get_etld_plus_one


class BlocklistMatcher:
    """Matches script URLs against EasyPrivacy and Disconnect rules for tracking attribution."""

    def __init__(
        self,
        easyprivacy_path: Path | str | None = "data/blocklists/easyprivacy.txt",
        disconnect_path: Path | str | None = "data/blocklists/disconnect_blacklist.json",
    ):
        self.easyprivacy_path = Path(easyprivacy_path) if easyprivacy_path else None
        self.disconnect_path = Path(disconnect_path) if disconnect_path else None
        self._engine: Engine | None = None
        self._disconnect_domains: set[str] = set()
        self._init_matchers()

    def _init_matchers(self) -> None:
        """Initialize EasyPrivacy adblock engine and Disconnect domain set."""
        if self.easyprivacy_path and self.easyprivacy_path.is_file():
            try:
                fs = FilterSet()
                content = self.easyprivacy_path.read_text(encoding="utf-8", errors="ignore")
                fs.add_filter_list(content)
                self._engine = Engine(fs)
            except Exception:
                self._engine = None

        if self.disconnect_path and self.disconnect_path.is_file():
            try:
                data = json.loads(self.disconnect_path.read_text(encoding="utf-8"))
                for _category, services in data.get("categories", {}).items():
                    for service in services:
                        for entry in service.values():
                            if isinstance(entry, dict):
                                for domain_list in entry.values():
                                    if isinstance(domain_list, list):
                                        for d in domain_list:
                                            self._disconnect_domains.add(d.lower())
            except Exception:
                pass

    def match_script(self, script_url: str, top_level_url: str = "") -> list[str]:
        """Check if script URL or domain matches EasyPrivacy or Disconnect."""
        matches: list[str] = []
        if not script_url or script_url.startswith("inline:"):
            return matches

        # 1. EasyPrivacy match via adblock engine
        if self._engine:
            try:
                res = self._engine.check_network_urls(script_url, top_level_url, "script")
                if res.matched:
                    matches.append("EasyPrivacy")
            except Exception:
                pass

        # 2. Disconnect domain match
        etld = get_etld_plus_one(script_url)
        if etld and etld in self._disconnect_domains:
            matches.append("Disconnect")

        return matches
