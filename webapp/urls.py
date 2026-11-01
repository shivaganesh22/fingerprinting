"""URL configuration for the browser fingerprinting web application."""

from django.urls import path
from webapp import views

urlpatterns = [
    # Dashboard / Home
    path("", views.dashboard_view, name="dashboard"),

    # Run management
    path("run/", views.run_create_view, name="run_create"),
    path("run/<str:run_id>/", views.run_live_view, name="run_live"),
    path("api/run/<str:run_id>/progress/", views.api_run_progress, name="api_run_progress"),
    path("api/run/<str:run_id>/cancel/", views.api_run_cancel, name="api_run_cancel"),
    path("api/estimate/", views.api_workload_estimate, name="api_workload_estimate"),

    # Reports
    path("reports/", views.reports_list_view, name="reports_list"),
    path("reports/compare/", views.report_compare_view, name="report_compare"),
    path("compare/", views.report_compare_view),
    path("reports/<str:run_id>/", views.report_detail_view, name="report_detail"),
    path("reports/<str:run_id>/export-csv/", views.report_export_csv_view, name="report_export_csv"),

    # Docs / Methodology
    path("docs/", views.docs_view, name="docs"),

    # Authentication
    path("auth/signup/", views.auth_signup_view, name="signup"),
    path("auth/login/", views.auth_login_view, name="login"),
    path("auth/logout/", views.auth_logout_view, name="logout"),
]
