"""Re-export FontsDetector and font helper from detectors."""
from fpstudy.detection.detectors import FontsDetector, extract_font_family_from_css

__all__ = ["FontsDetector", "extract_font_family_from_css"]
