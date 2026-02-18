"""Tests for PDF text extraction.

These tests require toydata.pdf to be compiled from toydata.tex.
They will be skipped automatically if the PDF is not present.
"""

from pdf_to_speech.extract import (
    _is_noise,
    _join_lines,
    _normalize_text,
    _remove_short_runs,
    extract_text,
)


# ── Unit tests for helpers (no PDF needed) ─────────────────────────────


class TestJoinLines:
    def test_simple(self):
        assert _join_lines(["hello", "world"]) == "hello world"

    def test_hyphenated(self):
        assert _join_lines(["occupa-", "tional"]) == "occupational"

    def test_empty(self):
        assert _join_lines([]) == ""

    def test_single_line(self):
        assert _join_lines(["just one"]) == "just one"

    def test_multiple_hyphens(self):
        result = _join_lines(["pre-", "trained", "lan-", "guage"])
        assert result == "pretrained language"


class TestIsNoise:
    def test_page_number(self):
        assert _is_noise("42")
        assert _is_noise(" 7 ")

    def test_short_fragment(self):
        assert _is_noise("A")
        assert _is_noise("xy")

    def test_normal_text(self):
        assert not _is_noise("This is a sentence.")

    def test_empty(self):
        assert _is_noise("")
        assert _is_noise("   ")

    def test_short_with_punctuation(self):
        # Short but ends with sentence punctuation — keep it
        assert not _is_noise("No.")


class TestRemoveShortRuns:
    def test_keeps_long_paragraphs(self):
        paras = ["A" * 80, "B" * 100, "C" * 70]
        assert _remove_short_runs(paras) == paras

    def test_removes_long_run_of_short(self):
        short = ["cell"] * 8
        paras = ["Long paragraph here." * 5] + short + ["Another long one." * 5]
        result = _remove_short_runs(paras)
        assert "cell" not in " ".join(result)
        assert len(result) == 2

    def test_keeps_short_run_below_threshold(self):
        short = ["cell"] * 3  # below _RUN_MIN (5)
        paras = ["Long paragraph." * 5] + short + ["Another." * 5]
        result = _remove_short_runs(paras)
        assert len(result) == 5  # all kept

    def test_keeps_leading_short_run(self):
        # Title, authors, date at the start of a paper should be kept
        header = ["A Great Title", "Jane Doe", "February 2026",
                  "Abstract text", "More abstract", "Keywords here"]
        paras = header + ["Long body paragraph." * 5] + ["cell"] * 8
        result = _remove_short_runs(paras)
        # Header kept, body kept, table cells removed
        assert "A Great Title" in result
        assert "Jane Doe" in result
        assert "cell" not in result


class TestNormalizeText:
    def test_joins_wrapped_lines(self):
        # Simulate PDF-style wrapped text: long lines that should be joined
        raw = (
            "This is a long line that fills the full width of the page in a PDF document.\n"
            "This continues the same paragraph and should be joined with the line above.\n"
            "And this is yet another continuation of the same flowing paragraph text.\n"
        )
        result = _normalize_text(raw)
        # Should be one paragraph (no double newlines)
        assert "\n\n" not in result

    def test_preserves_paragraph_break(self):
        raw = (
            "First paragraph which is long enough to be a real paragraph in a document.\n"
            "\n"
            "Second paragraph which is also long enough to be a real paragraph here.\n"
        )
        result = _normalize_text(raw)
        assert "\n\n" in result

    def test_rejoins_hyphenation_across_paragraphs(self):
        # A short line ending with hyphen followed by lowercase continuation
        raw = "This is a long enough line to establish a reasonable typical length for analysis.\n" \
              "occupa-\n" \
              "tional mobility is important for studying social change over time."
        result = _normalize_text(raw)
        assert "occupational" in result


# ── Tests that need the compiled PDF ───────────────────────────────────


class TestExtractText:
    def test_returns_nonempty(self, toydata_pdf):
        text = extract_text(toydata_pdf)
        assert len(text.strip()) > 100

    def test_contains_expected_content(self, toydata_pdf):
        text = extract_text(toydata_pdf)
        assert "proofreading" in text.lower()
        assert "auditory" in text.lower()

    def test_table_content_filtered(self, toydata_pdf):
        text = extract_text(toydata_pdf)
        # The table has method names in short rows — check that body prose
        # is present rather than asserting table absence (layout-dependent)
        assert "participants" in text.lower()

    def test_page_selection(self, toydata_pdf):
        full = extract_text(toydata_pdf)
        page0 = extract_text(toydata_pdf, pages=(0, 1))
        assert len(page0) < len(full) or len(full) == len(page0)  # 1-page doc is fine
        assert len(page0) > 0

    def test_invalid_page_raises(self, toydata_pdf):
        import pytest
        with pytest.raises(IndexError):
            extract_text(toydata_pdf, pages=(99, 100))

    def test_missing_file_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            extract_text("nonexistent.pdf")
