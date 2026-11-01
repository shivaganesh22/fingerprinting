"""Django models for the browser fingerprinting study."""

import json
from django.db import models


class Run(models.Model):
    """Crawl campaign run matching existing SQLite schema."""

    run_id = models.CharField(max_length=128, primary_key=True)
    condition = models.CharField(max_length=64)
    config_hash = models.CharField(max_length=64)
    git_commit = models.CharField(max_length=64, null=True, blank=True)
    tranco_list_id = models.CharField(max_length=64, null=True, blank=True)
    browser_version = models.CharField(max_length=128, null=True, blank=True)
    os_info = models.CharField(max_length=128, null=True, blank=True)
    library_versions = models.TextField(null=True, blank=True)
    start_time = models.CharField(max_length=64)
    end_time = models.CharField(max_length=64, null=True, blank=True)
    canary_passed = models.IntegerField(default=1)
    canary_details = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "runs"
        ordering = ["-start_time"]

    def __str__(self):
        return f"{self.run_id} ({self.condition})"

    @property
    def canary_details_dict(self):
        if not self.canary_details:
            return {}
        try:
            return json.loads(self.canary_details)
        except Exception:
            return {}

    @property
    def library_versions_dict(self):
        if not self.library_versions:
            return {}
        try:
            return json.loads(self.library_versions)
        except Exception:
            return {}


class Visit(models.Model):
    """Domain visit outcome record."""

    visit_id = models.CharField(max_length=64, primary_key=True)
    run = models.ForeignKey(Run, on_delete=models.DO_NOTHING, db_column="run_id", related_name="visits")
    domain = models.CharField(max_length=255)
    initial_url = models.TextField()
    final_url = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=32)
    http_status = models.IntegerField(null=True, blank=True)
    load_time_ms = models.FloatField(null=True, blank=True)
    dwell_time_ms = models.FloatField(null=True, blank=True)
    console_errors_count = models.IntegerField(default=0)
    requests_count = models.IntegerField(default=0)
    failed_requests_count = models.IntegerField(default=0)
    blocked_requests_count = models.IntegerField(default=0)
    events_count = models.IntegerField(default=0)
    events_truncated = models.IntegerField(default=0)
    start_time = models.CharField(max_length=64)
    end_time = models.CharField(max_length=64)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = "visits"
        ordering = ["domain"]

    def __str__(self):
        return f"{self.domain} ({self.status})"


class Event(models.Model):
    """Raw browser API interaction event."""

    id = models.AutoField(primary_key=True)
    visit = models.ForeignKey(Visit, on_delete=models.DO_NOTHING, db_column="visit_id", related_name="events")
    ts = models.FloatField()
    api = models.CharField(max_length=64)
    method_or_property = models.CharField(max_length=128)
    args_summary = models.TextField(null=True, blank=True)
    return_summary = models.TextField(null=True, blank=True)
    script_url = models.TextField(null=True, blank=True)
    stack_excerpt = models.TextField(null=True, blank=True)
    frame_url = models.TextField(null=True, blank=True)
    top_level_url = models.TextField(null=True, blank=True)
    is_third_party = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "events"
        ordering = ["ts"]


class Script(models.Model):
    """Script-level metadata and matched blocklist telemetry."""

    id = models.AutoField(primary_key=True)
    visit = models.ForeignKey(Visit, on_delete=models.DO_NOTHING, db_column="visit_id", related_name="scripts")
    script_url = models.TextField()
    is_third_party = models.IntegerField(default=0)
    matched_blocklist_entries = models.TextField(null=True, blank=True)
    high_entropy_signals_count = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "scripts"


class Classification(models.Model):
    """Detector classification record."""

    id = models.AutoField(primary_key=True)
    run = models.ForeignKey(Run, on_delete=models.DO_NOTHING, db_column="run_id", related_name="classifications")
    visit = models.ForeignKey(Visit, on_delete=models.DO_NOTHING, db_column="visit_id")
    domain = models.CharField(max_length=255)
    script_url = models.TextField()
    vector = models.CharField(max_length=32)
    flagged = models.IntegerField(default=0)
    confidence = models.CharField(max_length=16)
    evidence = models.TextField()
    is_third_party = models.IntegerField(default=0)

    class Meta:
        managed = False
        db_table = "classifications"
        ordering = ["domain", "vector"]

    @property
    def evidence_dict(self):
        if not self.evidence:
            return {}
        try:
            return json.loads(self.evidence)
        except Exception:
            return {}


class CrawlJob(models.Model):
    """Managed crawl job state for web interface monitoring and persistence."""

    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("running", "Running"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("failed", "Failed"),
    ]

    run_id = models.CharField(max_length=128, unique=True)
    condition = models.CharField(max_length=64)
    sample_size = models.IntegerField(default=10)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default="queued")
    current_domain = models.CharField(max_length=255, blank=True, null=True)
    domains_total = models.IntegerField(default=0)
    completed_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    finished_at = models.DateTimeField(blank=True, null=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "webapp_crawl_jobs"
        ordering = ["-created_at"]

    def __str__(self):
        return f"CrawlJob {self.run_id} [{self.status}]"
