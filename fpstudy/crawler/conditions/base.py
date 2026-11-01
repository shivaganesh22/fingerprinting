"""Base class and registry for countermeasure conditions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from playwright.async_api import Browser, BrowserContext

from fpstudy.config import ConditionDefinition, StudyConfig


class BaseCondition(ABC):
    """Abstract base class for a countermeasure condition."""

    def __init__(self, definition: ConditionDefinition, study_config: StudyConfig):
        self.definition = definition
        self.study_config = study_config
        self.name = definition.name

    @abstractmethod
    async def prepare(self) -> None:
        """Asynchronous preparation: download or parse blocklists, check extensions, etc."""
        raise NotImplementedError

    @abstractmethod
    async def launch_context(
        self,
        browser: Browser,
        context_options: dict[str, Any],
    ) -> BrowserContext:
        """Create and configure a fresh BrowserContext for a single visit."""
        raise NotImplementedError

    @abstractmethod
    async def teardown(self) -> None:
        """Clean up any temporary state or persistent resources."""
        raise NotImplementedError

    @abstractmethod
    async def self_check(self, browser: Browser) -> dict[str, Any]:
        """Perform a canary self-check to prove the countermeasure is actively working.

        Returns a dict with 'passed': bool and 'details': dict/str.
        Must raise an exception or return passed=False if the defense fails.
        """
        raise NotImplementedError

    def consume_visit_metrics(self, _context: BrowserContext) -> dict[str, int]:
        """Return and clear condition-specific metrics collected for one visit."""
        return {}

    def describe(self) -> dict[str, Any]:
        """Return human-readable metadata describing the condition."""
        return {
            "name": self.name,
            "description": self.definition.description,
            "type": self.definition.type,
            "enabled": self.definition.enabled,
        }


# Condition Registry
_CONDITION_REGISTRY: dict[str, type[BaseCondition]] = {}


def register_condition(name: str) -> Any:
    """Decorator to register a condition class by name."""

    def decorator(cls: type[BaseCondition]) -> type[BaseCondition]:
        _CONDITION_REGISTRY[name] = cls
        return cls

    return decorator


def get_condition_class(name: str) -> type[BaseCondition]:
    """Retrieve registered condition class."""
    if name not in _CONDITION_REGISTRY:
        raise KeyError(
            f"Condition '{name}' is not registered. Available: {list(_CONDITION_REGISTRY.keys())}"
        )
    return _CONDITION_REGISTRY[name]


def get_available_conditions() -> list[str]:
    """List all registered condition identifiers."""
    return list(_CONDITION_REGISTRY.keys())
