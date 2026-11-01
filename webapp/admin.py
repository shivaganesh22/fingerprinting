"""Django administrator registration for browser fingerprinting research models."""

from django.contrib import admin
from webapp.models import Classification, CrawlJob, Event, Run, Script, Visit


@admin.register(Run)
class RunAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "condition",
        "tranco_list_id",
        "canary_passed",
        "start_time",
        "end_time",
    )
    list_filter = ("condition", "canary_passed", "tranco_list_id")
    search_fields = ("run_id", "condition", "config_hash", "git_commit")
    readonly_fields = (
        "run_id",
        "condition",
        "config_hash",
        "git_commit",
        "tranco_list_id",
        "browser_version",
        "os_info",
        "library_versions",
        "start_time",
        "end_time",
        "canary_passed",
        "canary_details",
    )


@admin.register(Visit)
class VisitAdmin(admin.ModelAdmin):
    list_display = (
        "domain",
        "run",
        "status",
        "http_status",
        "load_time_ms",
        "requests_count",
        "blocked_requests_count",
        "events_count",
    )
    list_filter = ("status", "http_status", "run__condition")
    search_fields = ("domain", "visit_id", "initial_url", "final_url")
    readonly_fields = [f.name for f in Visit._meta.fields]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "visit",
        "api",
        "method_or_property",
        "is_third_party",
        "ts",
    )
    list_filter = ("api", "is_third_party")
    search_fields = ("method_or_property", "script_url", "visit__domain")
    readonly_fields = [f.name for f in Event._meta.fields]


@admin.register(Script)
class ScriptAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "visit",
        "script_url",
        "is_third_party",
        "high_entropy_signals_count",
    )
    list_filter = ("is_third_party",)
    search_fields = ("script_url", "matched_blocklist_entries", "visit__domain")
    readonly_fields = [f.name for f in Script._meta.fields]


@admin.register(Classification)
class ClassificationAdmin(admin.ModelAdmin):
    list_display = (
        "domain",
        "vector",
        "flagged",
        "confidence",
        "is_third_party",
        "run",
    )
    list_filter = ("vector", "flagged", "confidence", "is_third_party", "run__condition")
    search_fields = ("domain", "script_url", "run__run_id")
    readonly_fields = [f.name for f in Classification._meta.fields]


@admin.register(CrawlJob)
class CrawlJobAdmin(admin.ModelAdmin):
    list_display = (
        "run_id",
        "condition",
        "status",
        "domains_total",
        "completed_count",
        "failed_count",
        "skipped_count",
        "created_at",
    )
    list_filter = ("condition", "status")
    search_fields = ("run_id", "current_domain", "error_message")
    readonly_fields = ("created_at", "started_at", "finished_at")
