"""WebGL fingerprinting detector."""

from __future__ import annotations

from typing import Any

from fpstudy.config import WebGLRules
from fpstudy.storage.schema import ClassificationRecord, EventRecord


class WebGLDetector:
    """Detects WebGL parameter extraction and renderer fingerprinting.

    Criteria:
    1. Querying unmasked vendor/renderer info via WEBGL_debug_renderer_info.
    2. Querying >= min_distinct_parameters parameters combined with getSupportedExtensions / shader format.
    3. Offscreen/pixel readout via readPixels.
    """

    def __init__(self, rules: WebGLRules | None = None):
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
        """Classify WebGL events for a single script within a visit."""
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

        # Rule evaluation
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
