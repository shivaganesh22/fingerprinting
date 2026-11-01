"""Forms for crawl configuration, paired comparisons, and authentication."""

from pathlib import Path
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from webapp.crawler_service import get_supported_conditions
from webapp.models import Run


def get_available_tranco_files() -> list[tuple[str, str]]:
    """Scan data/tranco for available CSV files."""
    tranco_dir = Path("data/tranco")
    choices = []
    if tranco_dir.is_dir():
        for p in sorted(tranco_dir.glob("*.csv")):
            choices.append((p.name, f"{p.name} ({p.stat().st_size / (1024*1024):.1f} MB)" if p.stat().st_size > 1024*1024 else p.name))
    if not choices:
        choices = [("tranco_GQ3LK.csv", "tranco_GQ3LK.csv (1M Domains)")]
    return choices


class RunCreateForm(forms.Form):
    """Configuration form for launching a new crawl campaign."""

    condition = forms.ChoiceField(
        label="Privacy Protection / Condition",
        help_text="Select baseline or one of the installed, verified privacy countermeasures.",
        widget=forms.Select(attrs={"class": "form-select form-select-lg", "id": "id_condition"}),
    )

    sample_size = forms.IntegerField(
        label="Domain Sample Size",
        initial=100,
        min_value=1,
        max_value=5000,
        help_text="Number of domains to crawl from the selected Tranco list (up to 5,000).",
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "e.g. 100", "id": "id_sample_size"}
        ),
    )

    domain_source = forms.ChoiceField(
        label="Domain Source (Tranco List)",
        help_text="Select verified Tranco research ranking file.",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_domain_source"}),
    )

    dwell_time_seconds = forms.FloatField(
        label="Page Dwell Time (seconds)",
        initial=5.0,
        min_value=1.0,
        max_value=30.0,
        help_text="Time to let JavaScript scripts execute and trigger fingerprinting APIs after DOM load.",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.5", "id": "id_dwell_time"}),
    )

    navigation_timeout_seconds = forms.FloatField(
        label="Navigation Timeout (seconds)",
        initial=30.0,
        min_value=5.0,
        max_value=60.0,
        help_text="Maximum seconds to wait for initial page navigation.",
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "1.0", "id": "id_timeout"}),
    )

    max_retries = forms.IntegerField(
        label="Transient Failure Retries",
        initial=1,
        min_value=0,
        max_value=3,
        help_text="Number of retries with exponential backoff on timeout/network errors.",
        widget=forms.NumberInput(attrs={"class": "form-control", "id": "id_retries"}),
    )

    concurrency = forms.IntegerField(
        label="Crawler Concurrency",
        initial=2,
        min_value=1,
        max_value=4,
        help_text="Simultaneous browser contexts (polite crawler limit: 1-4).",
        widget=forms.NumberInput(attrs={"class": "form-control", "id": "id_concurrency"}),
    )

    headless = forms.BooleanField(
        label="Headless Mode",
        initial=True,
        required=False,
        help_text="Run browser headlessly (recommended for high throughput and server environments).",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input", "id": "id_headless"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate conditions
        supported = get_supported_conditions()
        condition_choices = []
        for k, v in supported.items():
            if v["supported"]:
                condition_choices.append((k, v["label"]))
        self.fields["condition"].choices = condition_choices

        # Populate Tranco CSV choices
        self.fields["domain_source"].choices = get_available_tranco_files()

    def clean_condition(self):
        cond = self.cleaned_data["condition"]
        supported = get_supported_conditions()
        if cond not in supported or not supported[cond]["supported"]:
            reason = supported.get(cond, {}).get("description", "Unsupported condition")
            raise forms.ValidationError(f"Condition '{cond}' cannot be run: {reason}")
        return cond


class ComparisonSelectForm(forms.Form):
    """Form to select two comparable crawl runs for paired statistical analysis."""

    baseline_run_id = forms.ChoiceField(
        label="Baseline Run (Control Condition)",
        help_text="Select standard unhindered browsing run.",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_baseline_run"}),
    )

    treatment_run_id = forms.ChoiceField(
        label="Countermeasure Run (Treatment Condition)",
        help_text="Select privacy protection run evaluated against the same domain sample.",
        widget=forms.Select(attrs={"class": "form-select", "id": "id_treatment_run"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        runs = Run.objects.all().order_by("-start_time")
        choices = [
            (
                r.run_id,
                f"{r.run_id} | {r.condition.upper()} | {r.start_time[:19]} ({r.visits.count()} visits)",
            )
            for r in runs
        ]
        self.fields["baseline_run_id"].choices = choices
        self.fields["treatment_run_id"].choices = choices

    def clean(self):
        cleaned_data = super().clean()
        b_id = cleaned_data.get("baseline_run_id")
        t_id = cleaned_data.get("treatment_run_id")
        if b_id and t_id and b_id == t_id:
            raise forms.ValidationError(
                "Please select two different runs for comparative analysis (e.g. Baseline vs Blocklist)."
            )
        return cleaned_data


class SignUpForm(UserCreationForm):
    """Researcher user registration form."""

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "researcher@university.ac.uk"}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class LoginForm(AuthenticationForm):
    """Researcher login form."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
