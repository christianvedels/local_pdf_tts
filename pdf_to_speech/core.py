"""Core orchestration: PDF -> text chunks -> TTS -> concatenated WAV."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.io import wavfile

from .extract import extract_text
from .tts import DEFAULT_LANG, DEFAULT_VOICE, SAMPLE_RATE, load_pipeline, synthesise

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text chunking
# ---------------------------------------------------------------------------

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, max_chars: int = 500) -> list[str]:
    """Split *text* into chunks of at most *max_chars* characters.

    Splitting is done on sentence boundaries where possible.  If a single
    sentence exceeds *max_chars* it is included as-is (the TTS model handles
    long inputs, albeit more slowly).
    """
    sentences = _SENTENCE_END.split(text.strip())
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        # If adding this sentence would exceed the limit, flush first.
        added_len = len(sentence) + (1 if current else 0)
        if current and current_len + added_len > max_chars:
            chunks.append(" ".join(current))
            current = []
            current_len = 0
        current.append(sentence)
        current_len += added_len

    if current:
        chunks.append(" ".join(current))
    return chunks


# ---------------------------------------------------------------------------
# Silence gap
# ---------------------------------------------------------------------------

def _silence(seconds: float = 0.3) -> np.ndarray:
    """Return a silence array of the given duration at :data:`SAMPLE_RATE`."""
    return np.zeros(int(SAMPLE_RATE * seconds), dtype=np.float32)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def pdf_to_speech(
    pdf_path: str | os.PathLike,
    output_path: str | os.PathLike,
    *,
    voice: str = DEFAULT_VOICE,
    lang_code: str = DEFAULT_LANG,
    speed: float = 1.0,
    pages: range | tuple[int, int] | None = None,
    max_chars_per_chunk: int = 500,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Convert a PDF document to a speech WAV file.

    Parameters
    ----------
    pdf_path:
        Path to the input PDF.
    output_path:
        Destination path for the output ``.wav`` file.
    voice:
        Kokoro voice identifier.  American English voices include
        ``"af_heart"``, ``"af_bella"``, ``"am_adam"``, ``"am_michael"``, etc.
        See https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
    lang_code:
        Language code — ``"a"`` (American English), ``"b"`` (British English),
        ``"e"`` (Spanish), ``"f"`` (French), ``"h"`` (Hindi), ``"i"``
        (Italian), ``"j"`` (Japanese), ``"p"`` (Portuguese), ``"z"``
        (Mandarin Chinese).
    speed:
        Playback speed multiplier (default 1.0).
    pages:
        Page selection — a ``range``, a ``(start, stop)`` tuple (0-indexed,
        stop exclusive), or *None* for all pages.
    max_chars_per_chunk:
        Maximum characters per text chunk sent to the TTS model.
    on_progress:
        Optional callback ``(current_chunk_index, total_chunks)`` fired
        after each chunk is synthesised.

    Returns
    -------
    Path
        The *output_path* as a resolved :class:`~pathlib.Path`.
    """
    output_path = Path(output_path)

    # 1. Extract text
    log.info("Extracting text from %s", pdf_path)
    text = extract_text(pdf_path, pages=pages)
    if not text.strip():
        raise ValueError("No text could be extracted from the PDF.")

    # 2. Chunk
    chunks = chunk_text(text, max_chars=max_chars_per_chunk)
    log.info("Split text into %d chunks", len(chunks))

    # 3. Load pipeline
    pipeline = load_pipeline(lang_code=lang_code)

    # 4. Synthesise each chunk
    audio_parts: list[np.ndarray] = []
    silence = _silence(0.3)

    for idx, chunk in enumerate(chunks):
        log.info("Synthesising chunk %d/%d (%d chars)", idx + 1, len(chunks), len(chunk))
        audio = synthesise(chunk, pipeline, voice=voice, speed=speed)
        if audio_parts:
            audio_parts.append(silence)
        audio_parts.append(audio)

        if on_progress is not None:
            on_progress(idx, len(chunks))

    # 5. Concatenate and save
    full_audio = np.concatenate(audio_parts)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(output_path), SAMPLE_RATE, full_audio)
    log.info("Saved %s (%.1f s)", output_path, len(full_audio) / SAMPLE_RATE)

    return output_path.resolve()
