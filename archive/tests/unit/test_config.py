"""Unit tests for configuration models, validation, and loading."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from fpstudy.config import (
    CrawlerConfig,
    SampleConfig,
    StudyConfig,
    load_study_config,
    load_yaml,
)


def test_load_yaml_valid() -> None:
    data = load_yaml("config/default.yaml")
    assert "sample" in data
    assert "crawler" in data


def test_load_yaml_missing() -> None:
    with pytest.raises(FileNotFoundError):
        load_yaml("config/non_existent_file.yaml")


def test_sample_config_bounds() -> None:
    cfg = SampleConfig(top_n=500)
    assert cfg.top_n == 500

    with pytest.raises(ValidationError):
        SampleConfig(top_n=0)


def test_crawler_contact_validation() -> None:
    cfg = CrawlerConfig(contact_email="student@univ.ac.uk")
    assert cfg.contact_email == "student@univ.ac.uk"
    assert "student@univ.ac.uk" in cfg.full_user_agent()

    # Must refuse placeholder
    cfg_placeholder = CrawlerConfig(contact_email="CONTACT_FROM_CONFIG")
    with pytest.raises(ValueError, match="Responsible crawling requires a real contact email"):
        cfg_placeholder.verify_contact_configured()

    with pytest.raises(ValidationError):
        CrawlerConfig(contact_email="   ")


def test_load_study_config_full() -> None:
    config = load_study_config("config/default.yaml")
    assert isinstance(config, StudyConfig)
    assert config.crawler.concurrency >= 1
    assert "baseline" in config.conditions.conditions
    assert config.detection_rules.canvas.min_width == 16
