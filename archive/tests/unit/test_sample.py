"""Unit tests for Tranco list management, domain normalization, and sampling."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import httpx
import pytest

from fpstudy.sample import (
    SampleManager,
    compute_sha256,
    generate_candidate_urls,
    normalize_domain,
)


def test_normalize_domain() -> None:
    assert normalize_domain("https://EXAMPLE.COM/path?arg=1#frag") == "example.com"
    assert normalize_domain("http://www.sub.domain.co.uk/") == "www.sub.domain.co.uk"
    assert normalize_domain("  FOO.ORG:8080/  ") == "foo.org"
    assert normalize_domain("dot.ending.net.") == "dot.ending.net"


def test_generate_candidate_urls() -> None:
    urls = generate_candidate_urls("example.com")
    assert urls == [
        "https://example.com/",
        "https://www.example.com/",
        "http://example.com/",
    ]

    urls_www = generate_candidate_urls("www.example.com")
    assert urls_www == [
        "https://www.example.com/",
        "http://www.example.com/",
    ]


def test_compute_sha256() -> None:
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("hello world\n")
        tf.flush()
        tf_path = Path(tf.name)

    assert (
        compute_sha256(tf_path)
        == "a948904f2f0f479b8f8197694b30184b0d2ed1c1cd2a1ec0fb85d299a192a447"
    )
    tf_path.unlink()


def test_sample_manager_offline_sampling() -> None:
    sample_csv = Path("data/tranco/sample_test.csv")
    mgr = SampleManager(download_dir="data/tranco")

    domains = mgr.get_sample(sample_csv, top_n=10)
    assert len(domains) == 10
    assert domains[0] == "google.com"
    assert domains[1] == "youtube.com"

    # Test sector subsetting
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("youtube.com\napple.com\n")
        sector_path = Path(tf.name)

    subset = mgr.get_sample(sample_csv, top_n=50, sector_file=sector_path)
    assert subset == ["youtube.com", "apple.com"]
    sector_path.unlink()


def test_verify_manifest_checks_id_hash_and_rows(tmp_path: Path) -> None:
    sample_path = tmp_path / "tranco_test.csv"
    sample_path.write_text("1,example.com\n2,example.org\n", encoding="utf-8")
    manager = SampleManager(tmp_path, tmp_path / "manifest.json")
    manager.manifest_path.write_text(
        json.dumps(
            {
                "list_id": "TEST1",
                "sha256": compute_sha256(sample_path),
                "row_count": 2,
            }
        ),
        encoding="utf-8",
    )

    assert manager.verify_manifest("TEST1", sample_path)["row_count"] == 2
    with pytest.raises(ValueError, match="does not match"):
        manager.verify_manifest("OTHER", sample_path)

    sample_path.write_text("1,changed.example\n", encoding="utf-8")
    with pytest.raises(ValueError, match="checksum"):
        manager.verify_manifest("TEST1", sample_path)


def test_download_failure_does_not_substitute_test_domains(tmp_path: Path) -> None:
    class FailedClient:
        def get(self, _url: str) -> httpx.Response:
            raise httpx.ConnectError("offline")

    (tmp_path / "sample_test.csv").write_text("1,test.example\n", encoding="utf-8")
    manager = SampleManager(tmp_path, tmp_path / "manifest.json")

    with pytest.raises(httpx.ConnectError):
        manager.download_tranco("TEST2", force=True, client=FailedClient())  # type: ignore[arg-type]

    assert not (tmp_path / "tranco_TEST2.csv").exists()
