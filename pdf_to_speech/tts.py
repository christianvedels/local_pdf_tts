"""TTS pipeline loading and audio synthesis using Kokoro (82M)."""

from __future__ import annotations

from typing import Any

import numpy as np

SAMPLE_RATE = 24_000

# Available language codes:
#   'a' = American English, 'b' = British English,
#   'e' = Spanish, 'f' = French, 'h' = Hindi,
#   'i' = Italian, 'j' = Japanese, 'p' = Portuguese, 'z' = Mandarin
DEFAULT_LANG = "a"
DEFAULT_VOICE = "af_heart"


def load_pipeline(lang_code: str = DEFAULT_LANG) -> Any:
    """Load the Kokoro TTS pipeline.

    Parameters
    ----------
    lang_code:
        Language code — ``"a"`` (American English), ``"b"`` (British English),
        ``"e"`` (Spanish), ``"f"`` (French), etc.

    Returns
    -------
    KPipeline
        The ready-to-use Kokoro pipeline instance.
    """
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code=lang_code)
    return pipeline


def synthesise(
    text: str,
    pipeline: Any,
    *,
    voice: str = DEFAULT_VOICE,
    speed: float = 1.0,
) -> np.ndarray:
    """Synthesise speech for a single text chunk.

    Returns a 1-D float32 numpy array at :data:`SAMPLE_RATE` Hz.
    """
    audio_parts: list[np.ndarray] = []
    for _gs, _ps, audio in pipeline(text, voice=voice, speed=speed):
        if audio is not None:
            audio_parts.append(audio)

    if not audio_parts:
        raise RuntimeError("Kokoro returned no audio for the given text.")

    return np.concatenate(audio_parts).astype(np.float32)
