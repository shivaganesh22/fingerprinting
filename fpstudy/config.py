"""Configuration models and loading utilities using Pydantic v2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator


class SampleConfig(BaseModel):
    """Configuration for sample selection and Tranco list downloads."""

    tranco_list_id: str = Field(default="573W9", description="Pinned Tranco list ID")
    top_n: int = Field(default=1000, ge=1, le=1000000, description="Top N domains to crawl")
    sector_file: Path | None = Field(default=None, description="Optional sector domains CSV")
    manifest_path: Path = Field(
        default=Path("data/tranco/manifest.json"), description="Path to Tranco manifest"
    )
    download_dir: Path = Field(
        default=Path("data/tranco"), description="Directory to store Tranco list"
    )


class ViewportConfig(BaseModel):
    """Browser viewport configuration."""

    width: int = 1920
    height: int = 1080


class CrawlerConfig(BaseModel):
    """Configuration for crawler operation, politeness, and browser environment."""

    concurrency: int = Field(default=4, ge=1, le=32)
    min_domain_delay_seconds: float = Field(default=5.0, ge=0.0)
    dwell_time_seconds: float = Field(default=12.0, ge=1.0)
    navigation_timeout_seconds: float = Field(default=30.0, ge=5.0)
    max_retries: int = Field(default=2, ge=0, le=5)
    retry_backoff_factor: float = Field(default=2.0, ge=1.0)
    viewport: ViewportConfig = Field(default_factory=ViewportConfig)
    locale: str = "en-US"
    timezone_id: str = "Europe/London"
    base_user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    contact_email: str = Field(
        default="researcher@example.ac.uk",
        description="Contact email included in custom crawler User-Agent token",
    )
    user_agent_token: str = Field(
        default="fpstudy-research/1.0",
        description="Identifiable suffix token for research crawler",
    )

    @field_validator("contact_email")
    @classmethod
    def validate_contact_email(cls, v: str) -> str:
        """Validate contact email is provided."""
        v = v.strip()
        if not v:
            raise ValueError("Contact email must be specified for responsible crawling")
        return v

    def full_user_agent(self) -> str:
        """Construct deterministic user-agent header including researcher contact."""
        return f"{self.base_user_agent} {self.user_agent_token} (+mailto:{self.contact_email})"

    def verify_contact_configured(self) -> None:
        """Refuse to run if contact email is left as the unedited placeholder."""
        placeholder_tokens = ["contact_from_config", "todo", "placeholder", "your-email-here"]
        for token in placeholder_tokens:
            if token in self.contact_email.lower():
                raise ValueError(
                    f"Responsible crawling requires a real contact email. "
                    f"Found placeholder value '{self.contact_email}'. "
                    f"Please update 'crawler.contact_email' in config/default.yaml."
                )


class InstrumentationConfig(BaseModel):
    """Configuration for client-side API wrapping and event collection."""

    max_events_per_visit: int = Field(default=5000, ge=100)
    batch_flush_interval_ms: int = Field(default=500, ge=50)
    script_timeout_ms: int = Field(default=5000, ge=500)


class StorageConfig(BaseModel):
    """Database and file export paths."""

    database_path: Path = Field(default=Path("data/raw/fpstudy.sqlite"))
    export_dir: Path = Field(default=Path("data/processed"))


class CanvasRules(BaseModel):
    """Heuristic thresholds for canvas fingerprinting detection."""

    min_width: int = 16
    min_height: int = 16
    min_distinct_colors: int = 2
    min_text_length: int = 10
    min_image_data_area: int = 256
    require_readback: bool = True
    exclude_if_save_or_restore: bool = True
    exclude_if_event_listener: bool = True


class WebGLRules(BaseModel):
    """Heuristic thresholds for WebGL fingerprinting detection."""

    unmasked_vendor_renderer: bool = True
    min_distinct_parameters: int = 10
    require_extension_or_precision: bool = True
    flag_read_pixels: bool = True


class AudioRules(BaseModel):
    """Heuristic thresholds for AudioContext fingerprinting detection."""

    require_offline_context: bool = True
    require_oscillator: bool = True
    require_compressor: bool = True
    require_readback: bool = True


class FontsRules(BaseModel):
    """Heuristic thresholds for font enumeration fingerprinting detection."""

    min_distinct_fonts: int = 30
    track_measure_text: bool = True
    track_element_dimensions: bool = True
    track_fontface_and_check: bool = True


class SignalsRules(BaseModel):
    """Supporting browser signals collection and breadth scoring rules."""

    breadth_threshold: int = 5
    high_entropy_properties: list[str] = Field(default_factory=list)


class DetectionRulesConfig(BaseModel):
    """Composite detection rules configuration."""

    canvas: CanvasRules = Field(default_factory=CanvasRules)
    webgl: WebGLRules = Field(default_factory=WebGLRules)
    audio: AudioRules = Field(default_factory=AudioRules)
    fonts: FontsRules = Field(default_factory=FontsRules)
    signals: SignalsRules = Field(default_factory=SignalsRules)


class ConditionDefinition(BaseModel):
    """Countermeasure condition specification."""

    name: str
    description: str
    type: str
    enabled: bool = True
    browser_type: str = "chromium"
    headless: Any = True
    lists: list[str] = Field(default_factory=list)
    extension_dir: str | None = None
    fallback_condition: str | None = None
    executable_path: str | None = None
    simulation_mode: str | None = None
    firefox_user_prefs: dict[str, Any] = Field(default_factory=dict)


class ConditionsConfig(BaseModel):
    """Registry of countermeasure conditions."""

    conditions: dict[str, ConditionDefinition] = Field(default_factory=dict)


class StudyConfig(BaseModel):
    """Master configuration encompassing all subsystems."""

    sample: SampleConfig = Field(default_factory=SampleConfig)
    crawler: CrawlerConfig = Field(default_factory=CrawlerConfig)
    instrumentation: InstrumentationConfig = Field(default_factory=InstrumentationConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    paths: dict[str, Path] = Field(default_factory=dict)
    detection_rules: DetectionRulesConfig = Field(default_factory=DetectionRulesConfig)
    conditions: ConditionsConfig = Field(default_factory=ConditionsConfig)


def load_yaml(path: Path | str) -> dict[str, Any]:
    """Safely load a YAML file."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Configuration file not found: {p}")
    with p.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or {}


def load_study_config(
    config_path: Path | str = "config/default.yaml",
    conditions_path: Path | str | None = None,
    detection_rules_path: Path | str | None = None,
) -> StudyConfig:
    """Load and merge default, condition, and detection rule configurations."""
    default_dict = load_yaml(config_path)

    # Resolve paths to supplementary config files
    cond_path = (
        conditions_path
        or default_dict.get("paths", {}).get("conditions_config")
        or "config/conditions.yaml"
    )
    det_path = (
        detection_rules_path
        or default_dict.get("paths", {}).get("detection_rules_config")
        or "config/detection_rules.yaml"
    )

    cond_dict = load_yaml(cond_path) if Path(cond_path).is_file() else {"conditions": {}}
    det_dict = load_yaml(det_path) if Path(det_path).is_file() else {}

    default_dict["conditions"] = cond_dict
    default_dict["detection_rules"] = det_dict

    return StudyConfig.model_validate(default_dict)
