"""Condition registry and implementations."""

from fpstudy.crawler.conditions.base import (
    BaseCondition,
    get_available_conditions,
    get_condition_class,
    register_condition,
)
from fpstudy.crawler.conditions.baseline import BaselineCondition
from fpstudy.crawler.conditions.blocklist import BlocklistCondition
from fpstudy.crawler.conditions.brave_shields import BraveShieldsCondition
from fpstudy.crawler.conditions.canvas_defender import CanvasDefenderCondition
from fpstudy.crawler.conditions.extension_ublock import UBlockExtensionCondition
from fpstudy.crawler.conditions.firefox_rfp import FirefoxRFPCondition

__all__ = [
    "BaseCondition",
    "register_condition",
    "get_condition_class",
    "get_available_conditions",
    "BaselineCondition",
    "BlocklistCondition",
    "CanvasDefenderCondition",
    "UBlockExtensionCondition",
    "BraveShieldsCondition",
    "FirefoxRFPCondition",
]
