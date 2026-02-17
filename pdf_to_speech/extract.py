"""PDF text extraction using PyMuPDF."""

from __future__ import annotations

import os
import re
from pathlib import Path

import fitz  # PyMuPDF


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _join_lines(lines: list[str]) -> str:
    """Join lines within a paragraph, rejoining hyphenated words."""
    if not lines:
        return ""
    result = lines[0]
    for line in lines[1:]:
        if result.endswith("-"):
            result = result[:-1] + line
        else:
            result = result + " " + line
    return result


_PAGE_NUMBER = re.compile(r"^\d{1,4}$")


def _is_noise(text: str) -> bool:
    """Return True for fragments that should not be read aloud."""
    t = text.strip()
    if not t:
        return True
    # Standalone page numbers
    if _PAGE_NUMBER.match(t):
        return True
    # Very short fragments that are likely diagram labels / stray numbers
    if len(t) <= 3 and t[-1] not in ".!?":
        return True
    return False


# ---------------------------------------------------------------------------
# Excluded regions: tables (structural detection)
# ---------------------------------------------------------------------------

def _table_rects(page: fitz.Page) -> list[fitz.Rect]:
    """Return bounding rectangles of tables detected via line analysis."""
    try:
        return [fitz.Rect(t.bbox) for t in page.find_tables()]
    except Exception:
        return []


def _in_any_rect(y0: float, y1: float, rects: list[fitz.Rect]) -> bool:
    """Return True if a horizontal band [y0, y1] overlaps any rectangle."""
    for r in rects:
        if y1 > r.y0 and y0 < r.y1:
            return True
    return False


# ---------------------------------------------------------------------------
# Post-processing: remove runs of short fragments (table cells, diagram text)
# ---------------------------------------------------------------------------

_SHORT_THRESHOLD = 60  # characters — shorter than this = "short fragment"
_RUN_MIN = 5           # need at least this many consecutive short fragments


def _remove_short_runs(paragraphs: list[str]) -> list[str]:
    """Remove consecutive runs of short paragraphs (likely table cells).

    A run of >= ``_RUN_MIN`` paragraphs that are all shorter than
    ``_SHORT_THRESHOLD`` characters is dropped entirely.  This catches
    table cell fragments that structural table detection missed.
    """
    n = len(paragraphs)
    keep = [True] * n

    run_start = 0
    while run_start < n:
        # Skip paragraphs that are long enough.
        if len(paragraphs[run_start]) >= _SHORT_THRESHOLD:
            run_start += 1
            continue
        # Found a short paragraph — see how long the run is.
        run_end = run_start + 1
        while run_end < n and len(paragraphs[run_end]) < _SHORT_THRESHOLD:
            run_end += 1
        if run_end - run_start >= _RUN_MIN:
            for i in range(run_start, run_end):
                keep[i] = False
        run_start = run_end

    return [p for p, k in zip(paragraphs, keep) if k]


# ---------------------------------------------------------------------------
# Line-length-based paragraph detection
# ---------------------------------------------------------------------------

def _normalize_text(raw: str) -> str:
    """Turn raw text into clean prose with proper paragraph breaks.

    Uses line-length analysis to distinguish paragraph-internal line wraps
    (full-width lines) from paragraph endings and headings (short lines).
    """
    lines = raw.split("\n")

    # Compute typical line length (ignore very short lines like headings).
    lengths = [len(l.strip()) for l in lines if len(l.strip()) > 20]
    if not lengths:
        return raw.strip()
    typical_len = sorted(lengths)[int(len(lengths) * 0.75)]
    threshold = typical_len * 0.6

    paragraphs: list[str] = []
    current: list[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append(_join_lines(current))
                current = []
            continue

        current.append(stripped)

        if len(stripped) < threshold:
            paragraphs.append(_join_lines(current))
            current = []

    if current:
        paragraphs.append(_join_lines(current))

    # Rejoin paragraphs that were split mid-word by hyphenation at a
    # short-line boundary.
    merged: list[str] = []
    for para in paragraphs:
        if merged and merged[-1].endswith("-") and para and para[0].islower():
            merged[-1] = merged[-1][:-1] + para
        else:
            merged.append(para)

    # Filter noise, then remove runs of short fragments (table cells).
    cleaned = [p for p in merged if not _is_noise(p)]
    cleaned = _remove_short_runs(cleaned)

    return "\n\n".join(cleaned)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text(
    pdf_path: str | os.PathLike,
    pages: range | tuple[int, int] | None = None,
) -> str:
    """Extract text from a PDF file.

    Parameters
    ----------
    pdf_path:
        Path to the PDF file.
    pages:
        Optional page selection.  Can be a ``range``, a ``(start, stop)``
        tuple (0-indexed, stop exclusive), or *None* for all pages.

    Returns
    -------
    str
        Concatenated text from the selected pages with line breaks
        normalised into flowing prose.  Tables, diagram fragments, and
        page numbers are excluded.  Paragraphs are separated by blank
        lines.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    doc = fitz.open(pdf_path)

    if pages is not None:
        if isinstance(pages, tuple):
            start, stop = pages
            page_range = range(start, stop)
        else:
            page_range = pages
    else:
        page_range = range(len(doc))

    raw_parts: list[str] = []
    for page_num in page_range:
        if page_num < 0 or page_num >= len(doc):
            raise IndexError(
                f"Page {page_num} out of range (document has {len(doc)} pages)"
            )
        page = doc[page_num]

        # Identify table regions to exclude (structural detection).
        excluded = _table_rects(page)

        # Extract text blocks, skipping those inside tables or images.
        page_lines: list[str] = []
        for b in page.get_text("blocks"):
            btype = b[6]
            if btype != 0:  # skip image blocks
                continue
            y0, y1 = b[1], b[3]
            if _in_any_rect(y0, y1, excluded):
                continue
            page_lines.append(b[4])

        raw_parts.append("".join(page_lines))

    doc.close()
    return _normalize_text("\n".join(raw_parts))
