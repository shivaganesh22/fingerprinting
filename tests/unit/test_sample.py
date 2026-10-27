"""Unit tests for Tranco list management, domain normalization, and sampling."""

from __future__ import annotations

import tempfile
from pathlib import Path

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
