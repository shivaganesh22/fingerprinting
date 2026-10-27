"""AudioContext fingerprinting detector."""

from __future__ import annotations

from typing import Any

from fpstudy.config import AudioRules
from fpstudy.storage.schema import ClassificationRecord, EventRecord


class AudioDetector:
    """Detects AudioContext fingerprinting (oscillator + dynamics compressor + buffer readback).

    Distinguishes classic stateless audio fingerprinting from benign web audio playback.
    """

    def __init__(self, rules: AudioRules | None = None):
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
        """Classify audio events for a single script within a visit."""
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

        # Pure benign audio check (e.g. game or sound effect using normal AudioContext)
        is_benign_playback = has_normal_context and not has_offline_context and not has_readback

        flagged = False
        confidence = "none"

        # Classic synthetic audio fingerprinting pattern
        if has_offline_context:
            if has_oscillator and has_compressor and has_readback:
                flagged = True
                confidence = "high"
            elif has_oscillator and has_readback:
                flagged = True
                confidence = "medium"
        elif has_normal_context and has_analyser and has_frequency_read and has_oscillator:
            # Real-time frequency buffer fingerprinting
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
