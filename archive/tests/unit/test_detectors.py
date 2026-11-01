"""Unit tests for heuristic fingerprinting detectors across all vectors."""

from __future__ import annotations

from fpstudy.detection.blocklist_match import BlocklistMatcher
from fpstudy.detection.detectors import (
    AudioDetector,
    CanvasDetector,
    FontsDetector,
    SignalsAnalyzer,
    WebGLDetector,
    extract_font_family_from_css,
)
from fpstudy.storage.schema import EventRecord


def make_event(
    api: str,
    method: str,
    args: dict | None = None,
    returns: dict | None = None,
    script_url: str = "https://tracker.com/fp.js",
) -> EventRecord:
    return EventRecord(
        visit_id="v_test",
        ts=100.0,
        api=api,
        method_or_property=method,
        args_summary=args or {},
        return_summary=returns or {},
        script_url=script_url,
    )


# ==========================================
# CANVAS TESTS
# ==========================================
def test_canvas_detector_positive() -> None:
    detector = CanvasDetector()
    events = [
        make_event("canvas", "getContext", {"width": 200, "height": 50}),
        make_event(
            "canvas",
            "fillText",
            {"text_length": 15, "width": 200, "height": 50, "fillStyle": "#f00"},
        ),
        make_event(
            "canvas",
            "fillText",
            {"text_length": 15, "width": 200, "height": 50, "fillStyle": "#00f"},
        ),
        make_event("canvas", "toDataURL", {"width": 200, "height": 50}),
    ]
    res = detector.analyze_events("https://tracker.com/fp.js", events)
    assert res.flagged == 1
    assert res.confidence == "high"


def test_canvas_detector_exclusions() -> None:
    detector = CanvasDetector()

    # Case A: Save/restore called (drawing app)
    events_save = [
        make_event("canvas", "getContext", {"width": 200, "height": 50}),
        make_event("canvas", "save"),
        make_event(
            "canvas",
            "fillText",
            {"text_length": 15, "width": 200, "height": 50, "fillStyle": "#f00"},
        ),
        make_event(
            "canvas",
            "fillText",
            {"text_length": 15, "width": 200, "height": 50, "fillStyle": "#00f"},
        ),
        make_event("canvas", "restore"),
        make_event("canvas", "toDataURL", {"width": 200, "height": 50}),
    ]
    assert detector.analyze_events("https://app.com/draw.js", events_save).flagged == 0

    # Case B: Event listener attached
    events_listener = [
        make_event("canvas", "getContext", {"width": 200, "height": 50}),
        make_event("canvas", "addEventListener", {"eventType": "mousemove"}),
        make_event(
            "canvas",
            "fillText",
            {"text_length": 15, "width": 200, "height": 50, "fillStyle": "#f00"},
        ),
        make_event("canvas", "toDataURL", {"width": 200, "height": 50}),
    ]
    assert detector.analyze_events("https://app.com/draw.js", events_listener).flagged == 0

    # Case C: Dimensions too small (< 16px)
    events_small = [
        make_event("canvas", "getContext", {"width": 10, "height": 10}),
        make_event(
            "canvas",
            "fillText",
            {"text_length": 15, "width": 10, "height": 10, "fillStyle": "#f00"},
        ),
        make_event("canvas", "toDataURL", {"width": 10, "height": 10}),
    ]
    assert detector.analyze_events("https://tracker.com/fp.js", events_small).flagged == 0

    # Case D: No image readback
    events_no_readback = [
        make_event("canvas", "getContext", {"width": 200, "height": 50}),
        make_event(
            "canvas",
            "fillText",
            {"text_length": 15, "width": 200, "height": 50, "fillStyle": "#f00"},
        ),
    ]
    assert detector.analyze_events("https://tracker.com/fp.js", events_no_readback).flagged == 0


# ==========================================
# WEBGL TESTS
# ==========================================
def test_webgl_detector_unmasked_hardware() -> None:
    detector = WebGLDetector()
    events = [
        make_event(
            "webgl",
            "getExtension",
            {"name": "WEBGL_debug_renderer_info", "is_debug_renderer_info": True},
        ),
        make_event(
            "webgl", "getParameter", {"pname": 0x9245, "is_unmasked_vendor_or_renderer": True}
        ),
    ]
    res = detector.analyze_events("https://tracker.com/fp.js", events)
    assert res.flagged == 1
    assert res.confidence == "high"


def test_webgl_detector_parameter_enumeration() -> None:
    detector = WebGLDetector()
    events = [make_event("webgl", "getParameter", {"pname": i}) for i in range(12)]
    events.append(make_event("webgl", "getSupportedExtensions"))

    res = detector.analyze_events("https://tracker.com/fp.js", events)
    assert res.flagged == 1
    assert res.confidence == "medium"

    # Benign with only 2 parameters and no extensions
    events_benign = [
        make_event("webgl", "getParameter", {"pname": 1}),
        make_event("webgl", "getParameter", {"pname": 2}),
    ]
    assert detector.analyze_events("https://site.com/3d.js", events_benign).flagged == 0


# ==========================================
# AUDIO TESTS
# ==========================================
def test_audio_detector_positive() -> None:
    detector = AudioDetector()
    events = [
        make_event("audio", "OfflineAudioContext"),
        make_event("audio", "createOscillator"),
        make_event("audio", "createDynamicsCompressor"),
        make_event("audio", "startRendering"),
        make_event("audio", "getChannelData"),
    ]
    res = detector.analyze_events("https://tracker.com/fp.js", events)
    assert res.flagged == 1
    assert res.confidence == "high"


def test_audio_detector_benign() -> None:
    detector = AudioDetector()
    events = [
        make_event("audio", "AudioContext"),
        make_event("audio", "createOscillator"),
    ]
    res = detector.analyze_events("https://site.com/sound.js", events)
    assert res.flagged == 0


# ==========================================
# FONTS TESTS
# ==========================================
def test_fonts_detector() -> None:
    detector = FontsDetector()
    # 32 distinct font probes
    events = [
        make_event("canvas", "measureText", {"font": f"12px 'FontFamily{i}', sans-serif"})
        for i in range(32)
    ]
    res = detector.analyze_events("https://tracker.com/fp.js", events)
    assert res.flagged == 1

    # Less than threshold
    events_small = [
        make_event("canvas", "measureText", {"font": "12px 'Arial', sans-serif"}),
        make_event("canvas", "measureText", {"font": "12px 'Georgia', serif"}),
    ]
    assert detector.analyze_events("https://site.com/app.js", events_small).flagged == 0


def test_extract_font_family_from_css() -> None:
    families = extract_font_family_from_css("bold 14px 'Comic Sans MS', 'Helvetica', sans-serif")
    assert "comic sans ms" in families
    assert "helvetica" in families
    assert "sans-serif" not in families


# ==========================================
# SIGNALS TESTS
# ==========================================
def test_signals_analyzer() -> None:
    analyzer = SignalsAnalyzer()
    events = [
        make_event("signals", "navigator.userAgent"),
        make_event("signals", "navigator.platform"),
        make_event("signals", "navigator.hardwareConcurrency"),
        make_event("signals", "navigator.deviceMemory"),
        make_event("signals", "screen.width"),
        make_event("signals", "screen.height"),
    ]
    res = analyzer.analyze_script_signals("https://tracker.com/fp.js", events)
    assert res["breadth_score"] == 6
    assert res["high_breadth"] is True


# ==========================================
# BLOCKLIST MATCHER
# ==========================================
def test_blocklist_matcher() -> None:
    matcher = BlocklistMatcher(easyprivacy_path="data/blocklists/easyprivacy.txt")
    matches = matcher.match_script(
        "https://google-analytics.com/analytics.js", "https://example.com"
    )
    assert "EasyPrivacy" in matches
