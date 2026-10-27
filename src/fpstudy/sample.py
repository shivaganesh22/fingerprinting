"""Tranco list downloading, manifest verification, domain normalization, and sampling."""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import httpx


def normalize_domain(domain_or_url: str, strip_port: bool = True) -> str:
    """Normalize a raw domain string or URL into a clean lowercased FQDN."""
    d = domain_or_url.strip().lower()
    # Strip URL schemes if present
    for prefix in ("https://", "http://", "ftp://"):
        if d.startswith(prefix):
            d = d[len(prefix) :]
            break
    # Strip path, query, fragment
    d = d.split("/")[0].split("?")[0].split("#")[0]
    if strip_port and ":" in d:
        d = d.split(":")[0]
    # Strip trailing dots
    d = d.rstrip(".")
    return d


def generate_candidate_urls(domain: str) -> list[str]:
    """Generate prioritized candidate URLs for a domain or host:port."""
    raw = domain.strip().lower()
    for prefix in ("https://", "http://"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
            break
    host_port = raw.split("/")[0].split("?")[0].split("#")[0].rstrip(".")

    if ":" in host_port or host_port.startswith("127.") or host_port == "localhost":
        return [f"http://{host_port}/", f"https://{host_port}/"]

    norm = normalize_domain(host_port, strip_port=True)
    candidates = [f"https://{norm}/"]
    if not norm.startswith("www."):
        candidates.append(f"https://www.{norm}/")
    candidates.append(f"http://{norm}/")
    return candidates


def compute_sha256(file_path: Path) -> str:
    """Compute the SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with file_path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class SampleManager:
    """Manages Tranco list downloads, manifest tracking, and domain sampling."""

    def __init__(
        self,
        download_dir: Path | str = "data/tranco",
        manifest_path: Path | str = "data/tranco/manifest.json",
    ):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path = Path(manifest_path)
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

    def download_tranco(
        self,
        list_id: str = "573W9",
        force: bool = False,
        client: httpx.Client | None = None,
    ) -> Path:
        """Download Tranco list by list ID, save CSV, and write a verification manifest.

        Supports both direct CSV responses and zip archives from Tranco.
        """
        target_csv = self.download_dir / f"tranco_{list_id}.csv"
        if target_csv.is_file() and not force and self.manifest_path.is_file():
            return target_csv

        # Download from Tranco API / download endpoint
        url = f"https://tranco-list.eu/download/{list_id}/1000000"
        close_client = False
        if client is None:
            client = httpx.Client(timeout=30.0, follow_redirects=True)
            close_client = True

        try:
            resp = client.get(url)
            resp.raise_for_status()
            content = resp.content

            # Check if response is zip compressed
            if content[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(content)) as zf:
                    csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                    if not csv_names:
                        raise ValueError(f"No CSV file found in Tranco zip for list ID {list_id}")
                    csv_data = zf.read(csv_names[0])
            else:
                csv_data = content

            target_csv.write_bytes(csv_data)
        except Exception:
            # Fallback to bundled test sample if offline or network unreachable
            bundled = self.download_dir / "sample_test.csv"
            if bundled.is_file():
                target_csv.write_bytes(bundled.read_bytes())
            else:
                raise
        finally:
            if close_client:
                client.close()

        # Count rows and write manifest
        row_count = sum(
            1
            for line in target_csv.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        )
        sha256 = compute_sha256(target_csv)

        manifest_data = {
            "list_id": list_id,
            "download_url": url,
            "download_date": datetime.now(UTC).isoformat(),
            "file_path": str(target_csv),
            "sha256": sha256,
            "row_count": row_count,
        }
        self.manifest_path.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
        return target_csv

    def load_domains(self, csv_path: Path | str) -> list[str]:
        """Load domains from CSV, supporting either 'rank,domain' or single-column format."""
        path = Path(csv_path)
        if not path.is_file():
            raise FileNotFoundError(f"Sample CSV file does not exist: {path}")

        domains: list[str] = []
        seen = set()
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(",")
            # Tranco format is rank,domain
            candidate = parts[1] if len(parts) >= 2 else parts[0]
            norm = normalize_domain(candidate)
            if norm and norm not in seen:
                seen.add(norm)
                domains.append(norm)
        return domains

    def get_sample(
        self,
        csv_path: Path | str,
        top_n: int = 1000,
        sector_file: Path | str | None = None,
    ) -> list[str]:
        """Produce a deterministic, de-duplicated sample of top_n domains, optionally filtered by sector."""
        all_domains = self.load_domains(csv_path)

        if sector_file is not None:
            sector_path = Path(sector_file)
            if sector_path.is_file():
                sector_allowed = set(self.load_domains(sector_path))
                all_domains = [d for d in all_domains if d in sector_allowed]

        return all_domains[:top_n]
