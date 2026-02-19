"""Convert a LaTeX/Overleaf project folder to a speech audio file.

Public API
----------
latex_folder_to_speech(folder, output_path, ...)
    High-level entry point: parse the LaTeX project, convert each content
    element to speech using the Kokoro TTS pipeline, and save the result.
"""

from __future__ import annotations

import io
import os
import sys
import time
from pathlib import Path
from typing import Callable

import numpy as np
from scipy.io import wavfile

from .latex import Element, parse_latex_project
from .tts import DEFAULT_LANG, DEFAULT_VOICE, SAMPLE_RATE, load_pipeline, synthesise
from .core import chunk_text, _silence, _fmt_duration


# ---------------------------------------------------------------------------
# Element → speakable text
# ---------------------------------------------------------------------------

# Element types whose value is read aloud directly (in full)
_READ_DIRECTLY = frozenset(
    ["Title", "Abstract", "Paragraph", "Table_caption", "Figure_caption"]
)

# Element types that get a short spoken prefix before the value
_PREFIXED = {
    "Headline": "",           # heading text already carries its own label
    "Table": "Table data: ",  # short spoken intro before raw table text
}


def _element_to_text(element: Element) -> str | None:
    """Return the speakable text for a content *element*, or ``None`` to skip.

    Tables are announced with a brief prefix; headings are read as-is;
    all other element types are read verbatim.
    """
    (kind, value), = element.items()

    if kind in _READ_DIRECTLY:
        return value.strip() or None

    if kind == "Headline":
        return value.strip() or None

    if kind == "Table":
        # For tables, read the cell values row by row (already text-ified)
        lines = [line.strip() for line in value.splitlines() if line.strip()]
        if not lines:
            return None
        return "Table data: " + ".  ".join(lines)

    return None  # unknown element type – skip


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def latex_folder_to_speech(
    folder: str | os.PathLike,
    output_path: str | os.PathLike,
    *,
    main_file: str = "main.tex",
    voice: str = DEFAULT_VOICE,
    lang_code: str = DEFAULT_LANG,
    speed: float = 1.0,
    max_chars_per_chunk: int = 500,
    verbose: int = 1,
    on_progress: Callable[[int, int], None] | None = None,
) -> Path:
    """Convert a LaTeX/Overleaf project folder to a speech audio file.

    Parameters
    ----------
    folder:
        Path to the project root directory (must contain *main_file*).
    output_path:
        Destination path for the output audio file.  Format is
        auto-detected from the extension: ``.wav`` or ``.mp3``.
    main_file:
        Name of the root ``.tex`` file (default ``"main.tex"``).
    voice:
        Kokoro voice identifier (e.g. ``"af_heart"``).
    lang_code:
        Language code — ``"a"`` (American English), ``"b"`` (British), etc.
    speed:
        Playback speed multiplier (default 1.0).
    max_chars_per_chunk:
        Maximum characters per chunk sent to the TTS model.
    verbose:
        Verbosity level.  ``0`` = silent, ``1`` = progress, ``2`` = details.
    on_progress:
        Optional callback ``(current_chunk_index, total_chunks)`` fired
        after each chunk is synthesised.

    Returns
    -------
    Path
        The *output_path* as a resolved :class:`~pathlib.Path`.
    """
    output_path = Path(output_path)

    # 1. Parse the LaTeX project into an ordered element list
    if verbose >= 2:
        print(f"Parsing LaTeX project in {folder}")
    elements = parse_latex_project(folder, main_file=main_file)
    if not elements:
        raise ValueError("No content could be extracted from the LaTeX project.")

    if verbose >= 2:
        print(f"Extracted {len(elements)} elements from the project")

    # 2. Convert elements to text chunks
    all_texts: list[str] = []
    for element in elements:
        text = _element_to_text(element)
        if text:
            all_texts.extend(chunk_text(text, max_chars=max_chars_per_chunk))

    if not all_texts:
        raise ValueError("No speakable text found in the LaTeX project.")

    if verbose >= 2:
        total_chars = sum(len(c) for c in all_texts)
        print(f"Total: {total_chars:,} characters — {len(all_texts)} chunks")

    # 3. Load TTS pipeline
    if verbose >= 2:
        print(f"Loading Kokoro pipeline (lang={lang_code}, voice={voice})")
    pipeline = load_pipeline(lang_code=lang_code)
    if verbose >= 2:
        print("Pipeline ready")

    # 4. Synthesise each chunk
    audio_parts: list[np.ndarray] = []
    silence = _silence(0.3)
    t_start = time.monotonic()

    for idx, chunk in enumerate(all_texts):
        if verbose >= 3:
            preview = chunk[:80] + ("…" if len(chunk) > 80 else "")
            print(f"  [{idx+1}/{len(all_texts)}] ({len(chunk)} chars) {preview}")

        audio = synthesise(chunk, pipeline, voice=voice, speed=speed)
        if audio_parts:
            audio_parts.append(silence)
        audio_parts.append(audio)

        if on_progress is not None:
            on_progress(idx, len(all_texts))

        if verbose >= 1:
            done = idx + 1
            elapsed = time.monotonic() - t_start
            per_chunk = elapsed / done
            remaining = per_chunk * (len(all_texts) - done)
            eta = f"ETA {_fmt_duration(remaining)}" if done < len(all_texts) else "done"
            print(f"  Chunk {done}/{len(all_texts)} — {eta}")

    # 5. Concatenate and save
    full_audio = np.concatenate(audio_parts)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.suffix.lower() == ".mp3":
        from pydub import AudioSegment
        import shutil

        if shutil.which("ffmpeg") is None:
            _conda_bin = Path(sys.prefix) / "Library" / "bin"
            if (_conda_bin / "ffmpeg.exe").exists():
                os.environ["PATH"] = (
                    str(_conda_bin) + os.pathsep + os.environ.get("PATH", "")
                )

        buf = io.BytesIO()
        wavfile.write(buf, SAMPLE_RATE, full_audio)
        buf.seek(0)
        audio_seg = AudioSegment.from_wav(buf)
        audio_seg.export(str(output_path), format="mp3")
    else:
        wavfile.write(str(output_path), SAMPLE_RATE, full_audio)

    duration = len(full_audio) / SAMPLE_RATE
    elapsed = time.monotonic() - t_start
    if verbose >= 1:
        print(
            f"Saved {output_path} ({_fmt_duration(duration)} audio, "
            f"took {_fmt_duration(elapsed)})"
        )

    return output_path.resolve()
