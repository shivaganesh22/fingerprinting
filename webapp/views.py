"""Views for dashboard, crawl runs, detailed reports, paired comparisons, docs, and authentication."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC, datetime
from typing import Any

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from fpstudy.analysis.compare import CountermeasureComparator
from fpstudy.analysis.prevalence import PrevalenceAnalyzer
from fpstudy.config import load_study_config
from fpstudy.storage.store import DataStore
from webapp.crawler_service import (
    cancel_crawl_job,
    estimate_workload,
    get_job_progress,
    get_supported_conditions,
    start_crawl_job,
)
from webapp.data_utils import blocking_counter_is_measured, rank_domains
from webapp.forms import ComparisonSelectForm, LoginForm, RunCreateForm, SignUpForm
from webapp.models import Classification, CrawlJob, Event, Run, Script, Visit


def dashboard_view(request: HttpRequest) -> HttpResponse:
    """Home / Dashboard view with headline research metrics, condition comparison, and recent runs."""
    total_runs = Run.objects.count()
    total_visits = Visit.objects.count()
    total_events = Event.objects.count()
    easyprivacy_blocked = sum(
        Visit.objects.filter(run__condition="blocklist").values_list("blocked_requests_count", flat=True)
    )
    successful_visits = Visit.objects.filter(status="ok").count()
    success_rate = round((successful_visits / total_visits * 100), 1) if total_visits > 0 else 0.0

    # Load outcomes breakdown
    timeout_visits = Visit.objects.filter(status="timeout").count()
    dns_visits = Visit.objects.filter(status="dns_error").count()
    crash_visits = Visit.objects.filter(status="crash").count()
    skipped_robots = Visit.objects.filter(status="skipped_robots").count()

    # Fingerprinting prevalence across conditions
    conditions = ["baseline", "blocklist", "extension_ubol", "canvas_defender", "brave_shields"]
    condition_stats = []
    for cond in conditions:
        runs_in_cond = Run.objects.filter(condition=cond)
        run_count = runs_in_cond.count()
        if run_count == 0:
            continue
        loaded_domains = Visit.objects.filter(run__condition=cond, status="ok").values("domain").distinct()
        v_ok = loaded_domains.count()
        # Distinct domains with at least 1 flagged vector in this condition
        fp_domains = (
            Classification.objects.filter(run__condition=cond, flagged=1)
            .values("domain")
            .distinct()
            .count()
        )
        prevalence = round((fp_domains / v_ok * 100), 1) if v_ok > 0 else 0.0
        condition_stats.append(
            {
                "condition": cond,
                "label": cond.replace("_", " ").title(),
                "runs_count": run_count,
                "successful_visits": v_ok,
                "successful_visits_label": "unique loaded domains",
                "fp_domains_count": fp_domains,
                "prevalence_percent": prevalence,
            }
        )

    # Detected vectors breakdown across all classifications
    vectors_list = ["canvas", "webgl", "audio", "fonts"]
    vector_counts = {}
    for vec in vectors_list:
        c = (
            Classification.objects.filter(vector=vec, flagged=1)
            .values("domain")
            .distinct()
            .count()
        )
        vector_counts[vec] = c

    # Recent runs table
    recent_runs = Run.objects.all().order_by("-start_time")[:10]
    runs_data = []
    for r in recent_runs:
        v_count = r.visits.count()
        v_ok = r.visits.filter(status="ok").count()
        fp_count = (
            Classification.objects.filter(run=r, flagged=1)
            .values("domain")
            .distinct()
            .count()
        )
        runs_data.append(
            {
                "run": r,
                "visits_total": v_count,
                "visits_ok": v_ok,
                "success_rate": round((v_ok / v_count * 100), 1) if v_count else 0.0,
                "fp_domains": fp_count,
                "prevalence": round((fp_count / v_ok * 100), 1) if v_ok > 0 else 0.0,
            }
        )

    # Supported condition status
    supported = get_supported_conditions()

    context = {
        "total_runs": total_runs,
        "total_visits": total_visits,
        "total_events": total_events,
        "easyprivacy_blocked": easyprivacy_blocked,
        "successful_visits": successful_visits,
        "success_rate": success_rate,
        "timeout_visits": timeout_visits,
        "dns_visits": dns_visits,
        "crash_visits": crash_visits,
        "skipped_robots": skipped_robots,
        "condition_stats": condition_stats,
        "vector_counts": vector_counts,
        "recent_runs": runs_data,
        "supported_conditions": supported,
    }
    return render(request, "dashboard.html", context)


@login_required
def run_create_view(request: HttpRequest) -> HttpResponse:
    """Run configuration and execution launch view."""
    supported = get_supported_conditions()

    if request.method == "POST":
        form = RunCreateForm(request.POST)
        if form.is_valid():
            try:
                run_id = start_crawl_job(
                    condition=form.cleaned_data["condition"],
                    sample_size=form.cleaned_data["sample_size"],
                    domain_source=form.cleaned_data["domain_source"],
                    dwell_time_seconds=form.cleaned_data["dwell_time_seconds"],
                    navigation_timeout_seconds=form.cleaned_data["navigation_timeout_seconds"],
                    max_retries=form.cleaned_data["max_retries"],
                    concurrency=form.cleaned_data["concurrency"],
                    headless=form.cleaned_data["headless"],
                )
                messages.success(
                    request,
                    f"Crawl job started successfully: {run_id}. Progress is being tracked live below.",
                )
                return redirect("run_live", run_id=run_id)
            except Exception as exc:
                messages.error(request, f"Failed to start crawl: {exc}")
    else:
        form = RunCreateForm()

    workload_default = estimate_workload(sample_size=100, dwell_time_seconds=5.0, concurrency=2)

    context = {
        "form": form,
        "supported_conditions": supported,
        "workload_estimate": workload_default,
    }
    return render(request, "run_create.html", context)


def run_live_view(request: HttpRequest, run_id: str) -> HttpResponse:
    """Live monitor view for active or finished crawl jobs."""
    progress = get_job_progress(run_id)
    run_record = Run.objects.filter(run_id=run_id).first()

    context = {
        "run_id": run_id,
        "progress": progress,
        "run_record": run_record,
    }
    return render(request, "run_live.html", context)


def api_run_progress(request: HttpRequest, run_id: str) -> JsonResponse:
    """REST JSON endpoint returning live progress and recent visit events."""
    data = get_job_progress(run_id)
    return JsonResponse(data)


@require_POST
def api_run_cancel(request: HttpRequest, run_id: str) -> JsonResponse:
    """Cancel an active crawl run."""
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required to cancel a crawl."}, status=403)

    cancelled = cancel_crawl_job(run_id)
    return JsonResponse({"run_id": run_id, "cancelled": cancelled})


def api_workload_estimate(request: HttpRequest) -> JsonResponse:
    """REST endpoint to dynamically estimate workload based on user inputs."""
    sample_size = int(request.GET.get("sample_size", 100))
    dwell_time = float(request.GET.get("dwell_time_seconds", 5.0))
    concurrency = int(request.GET.get("concurrency", 2))
    estimate = estimate_workload(sample_size, dwell_time, concurrency)
    return JsonResponse(estimate)


def reports_list_view(request: HttpRequest) -> HttpResponse:
    """Reports overview listing all runs with filtering and summary metrics."""
    condition_filter = request.GET.get("condition", "").strip()
    status_filter = request.GET.get("status", "").strip()
    search_query = request.GET.get("q", "").strip()

    qs = Run.objects.all().order_by("-start_time")
    if condition_filter:
        qs = qs.filter(condition=condition_filter)
    if search_query:
        qs = qs.filter(run_id__icontains=search_query)

    runs_data = []
    for r in qs:
        v_count = r.visits.count()
        v_ok = r.visits.filter(status="ok").count()
        v_timeouts = r.visits.filter(status="timeout").count()
        v_dns = r.visits.filter(status="dns_error").count()
        v_crash = r.visits.filter(status="crash").count()
        v_http_errors = r.visits.filter(status__startswith="http_").count()
        v_failed = r.visits.exclude(status="ok").exclude(status__startswith="skipped").count()
        v_skipped = r.visits.filter(status__startswith="skipped").count()
        v_blocked = sum(r.visits.values_list("blocked_requests_count", flat=True))
        v_failed_requests = sum(r.visits.values_list("failed_requests_count", flat=True))
        fp_count = (
            Classification.objects.filter(run=r, flagged=1)
            .values("domain")
            .distinct()
            .count()
        )
        prevalence = round((fp_count / v_ok * 100), 1) if v_ok > 0 else 0.0

        # Optional filter by status
        is_completed = bool(r.end_time)
        if status_filter == "completed" and not is_completed:
            continue
        if status_filter == "in_progress" and is_completed:
            continue

        runs_data.append(
            {
                "run": r,
                "visits_total": v_count,
                "visits_ok": v_ok,
                "visits_ok_percent": round((v_ok / v_count * 100), 1) if v_count else 0.0,
                "visits_failed": v_failed,
                "visits_skipped": v_skipped,
                "visits_timeouts": v_timeouts,
                "visits_dns": v_dns,
                "visits_http_errors": v_http_errors,
                "requests_blocked": v_blocked,
                "blocked_counter_measured": blocking_counter_is_measured(r.condition),
                "requests_failed": v_failed_requests,
                "fp_domains": fp_count,
                "prevalence_percent": prevalence,
                "is_completed": is_completed,
            }
        )

    context = {
        "runs": runs_data,
        "selected_condition": condition_filter,
        "selected_status": status_filter,
        "search_query": search_query,
    }
    return render(request, "reports_list.html", context)


def report_detail_view(request: HttpRequest, run_id: str) -> HttpResponse:
    """Detailed scientific report for a single crawl run."""
    run = get_object_or_404(Run, run_id=run_id)
    visits_qs = Visit.objects.filter(run=run)

    # 1. Outcomes breakdown
    total_visits = visits_qs.count()
    ok_visits = visits_qs.filter(status="ok").count()
    timeout_visits = visits_qs.filter(status="timeout").count()
    dns_visits = visits_qs.filter(status="dns_error").count()
    crash_visits = visits_qs.filter(status="crash").count()
    skipped_robots = visits_qs.filter(status="skipped_robots").count()
    other_skipped = visits_qs.filter(status__startswith="skipped").exclude(status="skipped_robots").count()

    # 2. Observed fingerprinting signals
    classifications_qs = Classification.objects.filter(run=run)
    total_flagged_records = classifications_qs.filter(flagged=1).count()
    fp_domains = classifications_qs.filter(flagged=1).values("domain").distinct().count()
    overall_prevalence = round((fp_domains / ok_visits * 100), 1) if ok_visits > 0 else 0.0

    # Vector breakdown
    vectors = ["canvas", "webgl", "audio", "fonts"]
    vector_breakdown = {}
    for vec in vectors:
        c_doms = (
            classifications_qs.filter(vector=vec, flagged=1)
            .values("domain")
            .distinct()
            .count()
        )
        prev = round((c_doms / ok_visits * 100), 1) if ok_visits > 0 else 0.0
        vector_breakdown[vec] = {
            "label": {
                "canvas": "Canvas 2D Readback",
                "webgl": "WebGL Context / Parameters",
                "audio": "AudioContext Dynamics",
                "fonts": "Font Enumeration Probing",
            }.get(vec, vec),
            "domains_count": c_doms,
            "prevalence_percent": prev,
        }

    # Third-party vs first-party breakdown
    third_party_fp_domains = (
        classifications_qs.filter(flagged=1, is_third_party=1)
        .values("domain")
        .distinct()
        .count()
    )
    first_party_fp_domains = (
        classifications_qs.filter(flagged=1, is_third_party=0)
        .values("domain")
        .distinct()
        .count()
    )

    # 3. Network telemetry
    requests_total = sum(v.requests_count for v in visits_qs)
    blocked_counter_measured = blocking_counter_is_measured(run.condition)
    blocked_total = sum(v.blocked_requests_count for v in visits_qs) if blocked_counter_measured else None
    failed_requests_total = sum(v.failed_requests_count for v in visits_qs)

    # 4. Filterable & Paginated Visits Data Table
    search_query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    signal_filter = request.GET.get("signals", "").strip()
    status_choices = visits_qs.values_list("status", flat=True).distinct().order_by("status")

    filtered_visits = visits_qs.order_by("domain")
    if search_query:
        filtered_visits = filtered_visits.filter(domain__icontains=search_query)
    if status_filter:
        filtered_visits = filtered_visits.filter(status=status_filter)
    flagged_domains = classifications_qs.filter(flagged=1).values("domain").distinct()
    if signal_filter == "detected":
        filtered_visits = filtered_visits.filter(domain__in=flagged_domains)
    elif signal_filter == "none":
        filtered_visits = filtered_visits.exclude(domain__in=flagged_domains)

    # Pre-fetch flagged vectors per domain for fast display
    flagged_map: dict[str, list[str]] = {}
    for c in classifications_qs.filter(flagged=1).values("domain", "vector"):
        flagged_map.setdefault(c["domain"], []).append(c["vector"])

    paginator = Paginator(filtered_visits, 50)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    domain_ranks = rank_domains(set(visits_qs.values_list("domain", flat=True)), run.tranco_list_id)
    visits_rows = []
    for v in page_obj:
        v_vectors = flagged_map.get(v.domain, [])
        visits_rows.append(
            {
                "visit": v,
                "rank": domain_ranks.get(v.domain),
                "vectors": v_vectors,
                "has_fp": len(v_vectors) > 0,
            }
        )

    context = {
        "run": run,
        "total_visits": total_visits,
        "ok_visits": ok_visits,
        "timeout_visits": timeout_visits,
        "dns_visits": dns_visits,
        "crash_visits": crash_visits,
        "skipped_robots": skipped_robots,
        "other_skipped": other_skipped,
        "fp_domains": fp_domains,
        "overall_prevalence": overall_prevalence,
        "total_flagged_records": total_flagged_records,
        "vector_breakdown": vector_breakdown,
        "third_party_fp_domains": third_party_fp_domains,
        "first_party_fp_domains": first_party_fp_domains,
        "requests_total": requests_total,
        "blocked_total": blocked_total,
        "blocked_counter_measured": blocked_counter_measured,
        "failed_requests_total": failed_requests_total,
        "page_obj": page_obj,
        "visits_rows": visits_rows,
        "search_query": search_query,
        "status_filter": status_filter,
        "signal_filter": signal_filter,
        "status_choices": status_choices,
    }
    return render(request, "report_detail.html", context)


def report_export_csv_view(request: HttpRequest, run_id: str) -> HttpResponse:
    """Download clean CSV export of visits and detector outcomes for a run."""
    run = get_object_or_404(Run, run_id=run_id)
    visits = Visit.objects.filter(run=run).order_by("domain")

    # Map classifications
    flagged_map: dict[str, set[str]] = {}
    for c in Classification.objects.filter(run=run, flagged=1).values("domain", "vector"):
        flagged_map.setdefault(c["domain"], set()).add(c["vector"])
    blocked_counter_measured = blocking_counter_is_measured(run.condition)
    domain_ranks = rank_domains(set(visits.values_list("domain", flat=True)), run.tranco_list_id)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "run_id",
            "condition",
            "domain",
            "tranco_rank",
            "initial_url",
            "final_url",
            "status",
            "http_status",
            "load_time_ms",
            "dwell_time_ms",
            "requests_count",
            "blocked_requests_count",
            "failed_requests_count",
            "fingerprinting_detected",
            "flagged_vectors",
            "error_message",
        ]
    )

    for v in visits:
        vecs = sorted(flagged_map.get(v.domain, set()))
        writer.writerow(
            [
                run.run_id,
                run.condition,
                v.domain,
                domain_ranks.get(v.domain, ""),
                v.initial_url,
                v.final_url or "",
                v.status,
                v.http_status or "",
                v.load_time_ms or "",
                v.dwell_time_ms or "",
                v.requests_count,
                v.blocked_requests_count if blocked_counter_measured else "",
                v.failed_requests_count,
                1 if vecs else 0,
                ";".join(vecs),
                v.error_message or "",
            ]
        )

    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="fpstudy_{run.run_id}_report.csv"'
    return response


def report_compare_view(request: HttpRequest) -> HttpResponse:
    """Cross-condition paired comparison view using McNemar test and effect sizes."""
    form = ComparisonSelectForm(request.GET or None)
    comparison_data: dict[str, Any] | None = None
    baseline_run = None
    treatment_run = None
    unpaired_info = None

    if form.is_valid():
        b_id = form.cleaned_data["baseline_run_id"]
        t_id = form.cleaned_data["treatment_run_id"]
        baseline_run = Run.objects.filter(run_id=b_id).first()
        treatment_run = Run.objects.filter(run_id=t_id).first()

        if baseline_run and treatment_run:
            store = DataStore("data/raw/fpstudy.sqlite")
            comparator = CountermeasureComparator(store)
            res = comparator.compare_runs(b_id, t_id)

            # Unpaired and missing accounting
            base_visits = Visit.objects.filter(run=baseline_run)
            treat_visits = Visit.objects.filter(run=treatment_run)
            b_total = base_visits.count()
            t_total = treat_visits.count()
            b_ok = base_visits.filter(status="ok").count()
            t_ok = treat_visits.filter(status="ok").count()
            paired_n = res["n_paired_domains"]

            unpaired_count = max(0, b_ok - paired_n) + max(0, t_ok - paired_n)

            unpaired_info = {
                "baseline_total": b_total,
                "treatment_total": t_total,
                "baseline_ok": b_ok,
                "treatment_ok": t_ok,
                "paired_n": paired_n,
                "unpaired_count": unpaired_count,
            }
            comparison_data = res

    context = {
        "form": form,
        "comparison_data": comparison_data,
        "baseline_run": baseline_run,
        "treatment_run": treatment_run,
        "unpaired_info": unpaired_info,
    }
    return render(request, "report_compare.html", context)


def docs_view(request: HttpRequest) -> HttpResponse:
    """Documentation and replication guide view."""
    supported = get_supported_conditions()
    context = {
        "supported_conditions": supported,
    }
    return render(request, "docs.html", context)


def auth_signup_view(request: HttpRequest) -> HttpResponse:
    """User registration view."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome to the Fingerprinting Study pipeline, {user.username}!")
            return redirect("dashboard")
    else:
        form = SignUpForm()

    return render(request, "auth_signup.html", {"form": form})


def auth_login_view(request: HttpRequest) -> HttpResponse:
    """User login view."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            next_url = request.GET.get("next") or "dashboard"
            return redirect(next_url)
    else:
        form = LoginForm()

    return render(request, "auth_login.html", {"form": form})


def auth_logout_view(request: HttpRequest) -> HttpResponse:
    """User logout view."""
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("dashboard")
