"""Core orchestration: PDF -> text chunks -> TTS -> concatenated audio."""

from __future__ import annotations

import io
import os
import re
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.io import wavfile

from .extract import extract_text
from .tts import DEFAULT_LANG, DEFAULT_VOICE, SAMPLE_RATE, load_pipeline, synthesise


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
# ETA formatting
# ---------------------------------------------------------------------------

def _fmt_duration(seconds: float) -> str:
    """Format a duration in seconds as a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m"


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
    verbose: int = 1,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Convert a PDF document to a speech audio file.

    Parameters
    ----------
    pdf_path:
        Path to the input PDF.
    output_path:
        Destination path for the output audio file.  The format is
        auto-detected from the extension: ``.wav`` or ``.mp3``.
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
    verbose:
        Verbosity level.  ``0`` = silent, ``1`` = chunk progress with ETA,
        ``2`` = extraction and model info, ``3`` = per-chunk text previews.
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
    if verbose >= 2:
        print(f"Extracting text from {pdf_path}")
    text = extract_text(pdf_path, pages=pages)
    if not text.strip():
        raise ValueError("No text could be extracted from the PDF.")

    # 2. Chunk
    chunks = chunk_text(text, max_chars=max_chars_per_chunk)
    if verbose >= 2:
        total_chars = sum(len(c) for c in chunks)
        print(f"Extracted {total_chars:,} characters — {len(chunks)} chunks")

    # 3. Load pipeline
    if verbose >= 2:
        print(f"Loading Kokoro pipeline (lang={lang_code}, voice={voice})")
    pipeline = load_pipeline(lang_code=lang_code)
    if verbose >= 2:
        print("Pipeline ready")

    # 4. Synthesise each chunk
    audio_parts: list[np.ndarray] = []
    silence = _silence(0.3)
    # Warmup: the first chunk often includes one-time overhead (model/cache).
    # Start ETA timing after the warmup chunk to stabilize early estimates.
    warmup_chunks = 1
    t_start: float | None = None

    for idx, chunk in enumerate(chunks):
        if verbose >= 3:
            preview = chunk[:80] + ("…" if len(chunk) > 80 else "")
            print(f"  [{idx+1}/{len(chunks)}] ({len(chunk)} chars) {preview}")

        audio = synthesise(chunk, pipeline, voice=voice, speed=speed)
        if audio_parts:
            audio_parts.append(silence)
        audio_parts.append(audio)

        if on_progress is not None:
            on_progress(idx, len(chunks))

        if verbose >= 1:
            done = idx + 1
            if done <= warmup_chunks:
                print(f"  Chunk {done}/{len(chunks)} — ETA calibrating")
            else:
                if t_start is None:
                    t_start = time.monotonic()
                elapsed = time.monotonic() - t_start
                effective_done = done - warmup_chunks
                per_chunk = elapsed / effective_done
                remaining = per_chunk * (len(chunks) - done)
                eta = f"ETA {_fmt_duration(remaining)}" if done < len(chunks) else "done"
                print(f"  Chunk {done}/{len(chunks)} — {eta}")

    # 5. Concatenate and save
    full_audio = np.concatenate(audio_parts)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".mp3":
        from pydub import AudioSegment
        import shutil

        # Help pydub find ffmpeg inside a conda env on Windows.
        if shutil.which("ffmpeg") is None:
            _conda_bin = Path(sys.prefix) / "Library" / "bin"
            if (_conda_bin / "ffmpeg.exe").exists():
                os.environ["PATH"] = str(_conda_bin) + os.pathsep + os.environ.get("PATH", "")

        buf = io.BytesIO()
        wavfile.write(buf, SAMPLE_RATE, full_audio)
        buf.seek(0)
        audio_seg = AudioSegment.from_wav(buf)
        audio_seg.export(str(output_path), format="mp3")
    else:
        wavfile.write(str(output_path), SAMPLE_RATE, full_audio)

    duration = len(full_audio) / SAMPLE_RATE
    if t_start is None:
        t_start = time.monotonic()
    elapsed = time.monotonic() - t_start
    if verbose >= 1:
        print(f"Saved {output_path} ({_fmt_duration(duration)} audio, "
              f"took {_fmt_duration(elapsed)})")

    return output_path.resolve()
