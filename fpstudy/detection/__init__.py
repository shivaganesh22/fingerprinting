"""Detection heuristics and script classification coordinator."""

from fpstudy.detection.blocklist_match import BlocklistMatcher
from fpstudy.detection.classify import ScriptClassifier
from fpstudy.detection.detectors import (
    AudioDetector,
    CanvasDetector,
    FontsDetector,
    SignalsAnalyzer,
    WebGLDetector,
)

__all__ = [
    "CanvasDetector",
    "WebGLDetector",
    "AudioDetector",
    "FontsDetector",
    "SignalsAnalyzer",
    "BlocklistMatcher",
    "ScriptClassifier",
]
