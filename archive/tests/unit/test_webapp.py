"""Unit tests for the Django web application and research reporting endpoints."""

import os
import pytest
from django.contrib.auth.models import User
from django.test import Client

from webapp.crawler_service import estimate_workload, get_supported_conditions
from webapp.models import Run


@pytest.fixture
def client() -> Client:
    """Create Django test client."""
    return Client()


@pytest.fixture
def test_user() -> User:
    """Create a temporary test researcher user."""
    user, _ = User.objects.get_or_create(
        username="test_researcher",
        defaults={"email": "test@research.ac.uk"},
    )
    user.set_password("SecurePass123!")
    user.save()
    return user


def test_supported_conditions_honesty():
    """Verify that supported conditions honestly reflect host environment capabilities."""
    conditions = get_supported_conditions()
    assert conditions["baseline"]["supported"] is True
    assert conditions["blocklist"]["supported"] is True
    assert conditions["canvas_defender"]["supported"] is True
    assert conditions["extension_ubol"]["supported"] is True

    # On this host, Firefox is not installed, so firefox_rfp must be marked unavailable
    assert conditions["firefox_rfp"]["supported"] is False
    assert "not installed" in conditions["firefox_rfp"]["description"].lower()


def test_workload_estimator():
    """Verify workload calculation formula and warning thresholds."""
    est_small = estimate_workload(sample_size=50, dwell_time_seconds=5.0, concurrency=2)
    # (50 * (5 + 4)) / 2 = 225s = 3m 45s
    assert est_small["estimated_total_seconds"] == 225.0
    assert est_small["estimated_time_formatted"] == "~3m 45s"
    assert est_small["is_large"] is False

    est_large = estimate_workload(sample_size=1500, dwell_time_seconds=10.0, concurrency=2)
    assert est_large["is_large"] is True
    assert "several hours" in est_large["warning"].lower()


def test_dashboard_view(client: Client):
    """Verify dashboard loads with headline metrics."""
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"Research Dashboard" in resp.content
    assert b"Total Experimental Runs" in resp.content
    assert b"Observed API Signals by Vector" in resp.content


def test_reports_list_view(client: Client):
    """Verify reports listing page and filtering."""
    resp = client.get("/reports/")
    assert resp.status_code == 200
    assert b"Research Reports" in resp.content

    # Filter by condition
    resp_filtered = client.get("/reports/?condition=baseline")
    assert resp_filtered.status_code == 200


def test_report_detail_and_csv_export(client: Client):
    """Verify report detail and CSV export for an existing run."""
    run = Run.objects.first()
    if not run:
        pytest.skip("No runs in SQLite database")

    # Detail page
    resp = client.get(f"/reports/{run.run_id}/")
    assert resp.status_code == 200
    assert run.run_id.encode("utf-8") in resp.content
    assert b"Page Load Health" in resp.content
    assert b"Observed API Signals" in resp.content
    assert b"Network Request Telemetry" in resp.content

    # CSV export
    resp_csv = client.get(f"/reports/{run.run_id}/export-csv/")
    assert resp_csv.status_code == 200
    assert resp_csv["Content-Type"] == "text/csv"
    assert b"run_id,condition,domain" in resp_csv.content


def test_paired_comparison_view(client: Client):
    """Verify paired comparison executes McNemar test on existing runs."""
    base_run = Run.objects.filter(condition="baseline").first()
    treat_run = Run.objects.filter(condition__in=["blocklist", "extension_ubol"]).first()

    if not base_run or not treat_run:
        pytest.skip("Insufficient paired runs in database")

    url = f"/reports/compare/?baseline_run_id={base_run.run_id}&treatment_run_id={treat_run.run_id}"
    resp = client.get(url)
    assert resp.status_code == 200
    assert b"Paired Countermeasure Comparison" in resp.content
    assert b"2 \xc3\x97 2 Contingency Table" in resp.content or b"Contingency Table" in resp.content


def test_auth_and_protected_run_views(client: Client, test_user: User):
    """Verify that /run/ is protected by login and allows authenticated users."""
    # Unauthenticated -> redirect
    resp = client.get("/run/")
    assert resp.status_code == 302
    assert "/auth/login/" in resp.url

    # Authenticated -> 200
    client.force_login(test_user)
    resp = client.get("/run/")
    assert resp.status_code == 200
    assert b"Configure &amp; Launch Crawl" in resp.content or b"Configure & Launch Crawl" in resp.content


def test_docs_view(client: Client):
    """Verify docs and replication guide renders."""
    resp = client.get("/docs/")
    assert resp.status_code == 200
    assert b"Documentation &amp; Replication Guide" in resp.content or b"Documentation & Replication Guide" in resp.content
    assert b"RFC 9309" in resp.content
