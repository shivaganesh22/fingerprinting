"""Consolidated browser fingerprinting detectors (Canvas, WebGL, Audio, Fonts, Signals).

Follows established academic heuristics:
- Canvas: Englehardt & Narayanan (OpenWPM, 2016)
- WebGL: Debug renderer unmasking, parameter enumeration, readback
- Audio: OfflineAudioContext oscillator + dynamics compressor synthesis
- Fonts: Multi-font probing via measureText, element dimensions, FontFace
- Signals: High-entropy navigator and screen property breadth analysis
"""

from __future__ import annotations

import re
from typing import Any

from fpstudy.config import (
    AudioRules,
    CanvasRules,
    FontsRules,
    SignalsRules,
    WebGLRules,
)
from fpstudy.storage.schema import ClassificationRecord, EventRecord


# -----------------------------------------------------------------------------
# Font Family Parsing Helper
# -----------------------------------------------------------------------------

def extract_font_family_from_css(font_string: str) -> list[str]:
    """Parse distinct font family names from a CSS font or fontFamily string."""
    if not font_string:
        return []
    clean = re.sub(r"\b\d+(?:px|pt|em|rem|%)\b", "", font_string)
    clean = re.sub(r"\b(?:bold|italic|normal|small-caps|bolder|lighter)\b", "", clean, flags=re.I)
    families = []
    for part in clean.split(","):
        f = part.strip().strip("'\"")
        if (
            f
            and len(f) > 1
            and f.lower() not in ("sans-serif", "serif", "monospace", "cursive", "fantasy")
        ):
            families.append(f.lower())
    return families


# -----------------------------------------------------------------------------
# Canvas Fingerprinting Detector
# -----------------------------------------------------------------------------

class CanvasDetector:
    """Detects canvas fingerprinting based on Englehardt & Narayanan (2016) heuristics."""

    def __init__(self, rules: CanvasRules | None = None) -> None:
        self.rules = rules or CanvasRules()

    def analyze_events(
        self,
        script_url: str,
        events: list[EventRecord],
        run_id: str = "",
        visit_id: str = "",
        domain: str = "",
        is_third_party: int = 0,
    ) -> ClassificationRecord:
        canvas_events = [e for e in events if e.api == "canvas"]

        has_min_dimensions = False
        text_lengths: list[int] = []
        drawn_colors: set[str] = set()
        readback_methods: list[str] = []
        has_save_or_restore = False
        has_event_listener = False
        max_dim = (0, 0)

        for e in canvas_events:
            method = e.method_or_property
            args = e.args_summary or {}

            w = args.get("width")
            h = args.get("height")
            if w is not None and h is not None:
                try:
                    w_int, h_int = int(w), int(h)
                    if w_int > max_dim[0]:
                        max_dim = (w_int, max_dim[1])
                    if h_int > max_dim[1]:
                        max_dim = (max_dim[0], h_int)
                    if w_int >= self.rules.min_width and h_int >= self.rules.min_height:
                        has_min_dimensions = True
                except (ValueError, TypeError):
                    pass

            if method in ("fillText", "strokeText"):
                length = args.get("text_length", 0)
                text_lengths.append(int(length))
                color = args.get("fillStyle") or args.get("strokeStyle")
                if color:
                    drawn_colors.add(str(color).strip().lower())

            if method in ("toDataURL", "toBlob"):
                readback_methods.append(method)
            elif method == "getImageData":
                area = args.get("area", 0)
                if area >= self.rules.min_image_data_area:
                    readback_methods.append(f"getImageData(area={area})")

            if method in ("save", "restore"):
                has_save_or_restore = True
            if method == "addEventListener":
                has_event_listener = True

        condition_dim = has_min_dimensions
        condition_text = (
            any(tl >= self.rules.min_text_length for tl in text_lengths)
            or len(drawn_colors) >= self.rules.min_distinct_colors
        )
        condition_readback = len(readback_methods) > 0 if self.rules.require_readback else True
        condition_exclusions = True
        if self.rules.exclude_if_save_or_restore and has_save_or_restore:
            condition_exclusions = False
        if self.rules.exclude_if_event_listener and has_event_listener:
            condition_exclusions = False

        flagged = bool(
            condition_dim and condition_text and condition_readback and condition_exclusions
        )

        confidence = "none"
        if flagged:
            confidence = (
                "high" if len(readback_methods) > 0 and len(drawn_colors) >= 2 else "medium"
            )

        evidence: dict[str, Any] = {
            "max_dimensions": list(max_dim),
            "max_text_length": max(text_lengths) if text_lengths else 0,
            "distinct_colors": list(drawn_colors),
            "readback_methods": readback_methods,
            "has_save_or_restore": has_save_or_restore,
            "has_event_listener": has_event_listener,
            "rule_evaluation": {
                "dimensions_ok": condition_dim,
                "text_drawn_ok": condition_text,
                "readback_ok": condition_readback,
                "exclusions_ok": condition_exclusions,
            },
        }

        return ClassificationRecord(
            run_id=run_id,
            visit_id=visit_id,
            domain=domain,
            script_url=script_url,
            vector="canvas",
            flagged=1 if flagged else 0,
            confidence=confidence,
            evidence=evidence,
            is_third_party=is_third_party,
        )


# -----------------------------------------------------------------------------
# WebGL Fingerprinting Detector
# -----------------------------------------------------------------------------

class WebGLDetector:
    """Detects WebGL parameter extraction and renderer fingerprinting."""

    def __init__(self, rules: WebGLRules | None = None) -> None:
        self.rules = rules or WebGLRules()

    def analyze_events(
        self,
        script_url: str,
        events: list[EventRecord],
        run_id: str = "",
        visit_id: str = "",
        domain: str = "",
        is_third_party: int = 0,
    ) -> ClassificationRecord:
        webgl_events = [e for e in events if e.api == "webgl"]

        queried_params: set[str] = set()
        queried_extensions: set[str] = set()
        unmasked_debug_accessed = False
        supported_extensions_queried = False
        shader_precision_queried = False
        read_pixels_called = False

        for e in webgl_events:
            method = e.method_or_property
            args = e.args_summary or {}

            if method == "getParameter":
                pname = str(args.get("pname", ""))
                queried_params.add(pname)
                if args.get("is_unmasked_vendor_or_renderer"):
                    unmasked_debug_accessed = True

            elif method == "getExtension":
                ext = str(args.get("name", ""))
                queried_extensions.add(ext)
                if ext == "WEBGL_debug_renderer_info" or args.get("is_debug_renderer_info"):
                    unmasked_debug_accessed = True

            elif method == "getSupportedExtensions":
                supported_extensions_queried = True

            elif method == "getShaderPrecisionFormat":
                shader_precision_queried = True

            elif method == "readPixels":
                read_pixels_called = True

        flagged = False
        confidence = "none"

        # Path 1: Unmasked hardware info
        if self.rules.unmasked_vendor_renderer and unmasked_debug_accessed:
            flagged = True
            confidence = "high"
        # Path 2: Parameter enumeration combined with extensions or precision
        elif len(queried_params) >= self.rules.min_distinct_parameters:
            if self.rules.require_extension_or_precision:
                if supported_extensions_queried or shader_precision_queried:
                    flagged = True
                    confidence = "medium"
            else:
                flagged = True
                confidence = "medium"

        # Path 3: Render and read pixels with parameter probing
        if read_pixels_called and (len(queried_params) >= 5 or unmasked_debug_accessed):
            flagged = True
            confidence = "high"

        evidence: dict[str, Any] = {
            "unmasked_debug_accessed": unmasked_debug_accessed,
            "distinct_parameters_count": len(queried_params),
            "parameters_sample": list(queried_params)[:20],
            "queried_extensions": list(queried_extensions),
            "supported_extensions_queried": supported_extensions_queried,
            "shader_precision_queried": shader_precision_queried,
            "read_pixels_called": read_pixels_called,
        }

        return ClassificationRecord(
            run_id=run_id,
            visit_id=visit_id,
            domain=domain,
            script_url=script_url,
            vector="webgl",
            flagged=1 if flagged else 0,
            confidence=confidence,
            evidence=evidence,
            is_third_party=is_third_party,
        )


# -----------------------------------------------------------------------------
# AudioContext Fingerprinting Detector
# -----------------------------------------------------------------------------

class AudioDetector:
    """Detects AudioContext oscillator/compressor synthetic readback fingerprinting."""

    def __init__(self, rules: AudioRules | None = None) -> None:
        self.rules = rules or AudioRules()

    def analyze_events(
        self,
        script_url: str,
        events: list[EventRecord],
        run_id: str = "",
        visit_id: str = "",
        domain: str = "",
        is_third_party: int = 0,
    ) -> ClassificationRecord:
        audio_events = [e for e in events if e.api == "audio"]

        has_offline_context = False
        has_normal_context = False
        has_oscillator = False
        has_compressor = False
        has_analyser = False
        has_start_rendering = False
        has_channel_data_read = False
        has_frequency_read = False

        for e in audio_events:
            method = e.method_or_property
            if method == "OfflineAudioContext":
                has_offline_context = True
            elif method == "AudioContext":
                has_normal_context = True
            elif method == "createOscillator":
                has_oscillator = True
            elif method == "createDynamicsCompressor":
                has_compressor = True
            elif method == "createAnalyser":
                has_analyser = True
            elif method == "startRendering":
                has_start_rendering = True
            elif method == "getChannelData":
                has_channel_data_read = True
            elif method == "analyser.getFloatFrequencyData":
                has_frequency_read = True

        has_readback = (
            (has_start_rendering or has_channel_data_read or has_frequency_read)
            if self.rules.require_readback
            else True
        )

        is_benign_playback = has_normal_context and not has_offline_context and not has_readback

        flagged = False
        confidence = "none"

        if has_offline_context:
            if has_oscillator and has_compressor and has_readback:
                flagged = True
                confidence = "high"
            elif has_oscillator and has_readback:
                flagged = True
                confidence = "medium"
        elif has_normal_context and has_analyser and has_frequency_read and has_oscillator:
            flagged = True
            confidence = "medium"

        evidence: dict[str, Any] = {
            "has_offline_context": has_offline_context,
            "has_normal_context": has_normal_context,
            "has_oscillator": has_oscillator,
            "has_dynamics_compressor": has_compressor,
            "has_analyser": has_analyser,
            "has_start_rendering": has_start_rendering,
            "has_channel_data_read": has_channel_data_read,
            "has_frequency_read": has_frequency_read,
            "is_benign_playback": is_benign_playback,
        }

        return ClassificationRecord(
            run_id=run_id,
            visit_id=visit_id,
            domain=domain,
            script_url=script_url,
            vector="audio",
            flagged=1 if flagged else 0,
            confidence=confidence,
            evidence=evidence,
            is_third_party=is_third_party,
        )


# -----------------------------------------------------------------------------
# Fonts Probing Detector
# -----------------------------------------------------------------------------

class FontsDetector:
    """Detects font probing and enumeration (measureText, element dimensions, document.fonts.check)."""

    def __init__(self, rules: FontsRules | None = None) -> None:
        self.rules = rules or FontsRules()

    def analyze_events(
        self,
        script_url: str,
        events: list[EventRecord],
        run_id: str = "",
        visit_id: str = "",
        domain: str = "",
        is_third_party: int = 0,
    ) -> ClassificationRecord:
        tested_fonts: set[str] = set()
        methods_observed: set[str] = set()
        probe_count = 0

        for e in events:
            method = e.method_or_property
            args = e.args_summary or {}

            if e.api == "canvas" and method == "measureText":
                probe_count += 1
                font_str = str(args.get("font", ""))
                for f in extract_font_family_from_css(font_str):
                    tested_fonts.add(f)
                    methods_observed.add("canvas.measureText")

            elif e.api == "fonts":
                probe_count += 1
                if method.startswith("element.offset"):
                    font_family = str(args.get("fontFamily", ""))
                    for f in extract_font_family_from_css(font_family):
                        tested_fonts.add(f)
                        methods_observed.add(method)
                elif method == "document.fonts.check":
                    font_name = str(args.get("font", ""))
                    for f in extract_font_family_from_css(font_name):
                        tested_fonts.add(f)
                        methods_observed.add("document.fonts.check")
                elif method == "FontFace":
                    family = str(args.get("family", ""))
                    if family:
                        tested_fonts.add(family.lower())
                        methods_observed.add("FontFace")

        distinct_count = len(tested_fonts)
        flagged = distinct_count >= self.rules.min_distinct_fonts

        confidence = "none"
        if flagged:
            confidence = "high" if distinct_count >= 50 else "medium"

        evidence: dict[str, Any] = {
            "distinct_fonts_count": distinct_count,
            "sample_tested_fonts": sorted(tested_fonts)[:30],
            "total_font_probes": probe_count,
            "methods_observed": list(methods_observed),
            "threshold": self.rules.min_distinct_fonts,
        }

        return ClassificationRecord(
            run_id=run_id,
            visit_id=visit_id,
            domain=domain,
            script_url=script_url,
            vector="fonts",
            flagged=1 if flagged else 0,
            confidence=confidence,
            evidence=evidence,
            is_third_party=is_third_party,
        )


# -----------------------------------------------------------------------------
# Signals Breadth Analyzer
# -----------------------------------------------------------------------------

class SignalsAnalyzer:
    """Analyzes supporting high-entropy navigator, screen, and system property reads."""

    def __init__(self, rules: SignalsRules | None = None) -> None:
        self.rules = rules or SignalsRules()

    def analyze_script_signals(
        self,
        script_url: str,
        events: list[EventRecord],
    ) -> dict[str, Any]:
        signals_events = [e for e in events if e.api == "signals"]
        accessed_properties: set[str] = set()

        for e in signals_events:
            prop = e.method_or_property
            accessed_properties.add(prop)

        breadth_score = len(accessed_properties)
        high_breadth = breadth_score >= self.rules.breadth_threshold

        return {
            "script_url": script_url,
            "breadth_score": breadth_score,
            "high_breadth": high_breadth,
            "accessed_properties": sorted(accessed_properties),
        }
