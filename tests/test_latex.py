"""Tests for the LaTeX project parser and overleaf-to-speech orchestration.

These tests cover:
 - parse_latex_project() against the mock Overleaf fixture
 - Individual helper functions (_clean_text, _extract_braced, etc.)
 - The _element_to_text conversion used by latex_folder_to_speech
"""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
MOCK_OVERLEAF = FIXTURES / "mock_overleaf"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _kinds(elements: list[dict]) -> list[str]:
    """Return the list of element type keys in order."""
    return [list(e.keys())[0] for e in elements]


def _values_of(elements: list[dict], kind: str) -> list[str]:
    """Return all values whose key equals *kind*."""
    return [list(e.values())[0] for e in elements if list(e.keys())[0] == kind]


# ---------------------------------------------------------------------------
# Unit tests for _clean_text
# ---------------------------------------------------------------------------

class TestCleanText:
    def test_strips_textbf(self):
        from pdf_to_speech.latex import _clean_text
        assert _clean_text(r"\textbf{hello}") == "hello"

    def test_strips_emph(self):
        from pdf_to_speech.latex import _clean_text
        assert _clean_text(r"\emph{important}") == "important"

    def test_strips_cite(self):
        from pdf_to_speech.latex import _clean_text
        result = _clean_text(r"See \cite{smith2020} for details.")
        assert "cite" not in result
        assert "smith" not in result
        assert "for details" in result

    def test_inline_math_replaced(self):
        from pdf_to_speech.latex import _clean_text
        result = _clean_text(r"We find $p < 0.01$.")
        assert "$" not in result
        assert "formula" in result

    def test_noindent_before_textbf(self):
        from pdf_to_speech.latex import _clean_text
        result = _clean_text(r"\noindent\textbf{Disclaimer:} Some text")
        assert "Disclaimer:" in result
        assert "noindent" not in result

    def test_strips_label(self):
        from pdf_to_speech.latex import _clean_text
        result = _clean_text(r"Table \ref{tab:main} shows results.")
        assert "tab:main" not in result
        assert "shows results" in result

    def test_bibliography_commands_stripped(self):
        from pdf_to_speech.latex import _clean_text
        result = _clean_text(r"\bibliographystyle{apalike}\bibliography{references}")
        assert result.strip() == ""

    def test_tilde_becomes_space(self):
        from pdf_to_speech.latex import _clean_text
        result = _clean_text(r"Figure~\ref{fig:1}")
        assert "~" not in result

    def test_double_dash_normalised(self):
        from pdf_to_speech.latex import _clean_text
        assert "\u2013" in _clean_text("1990--2020")

    def test_triple_dash_normalised(self):
        from pdf_to_speech.latex import _clean_text
        assert "\u2014" in _clean_text("however---not always")


# ---------------------------------------------------------------------------
# Unit tests for _extract_braced
# ---------------------------------------------------------------------------

class TestExtractBraced:
    def test_simple(self):
        from pdf_to_speech.latex import _extract_braced
        content, end = _extract_braced("{hello}", 0)
        assert content == "hello"
        assert end == 7

    def test_nested(self):
        from pdf_to_speech.latex import _extract_braced
        content, end = _extract_braced("{a{b}c}", 0)
        assert content == "a{b}c"
        assert end == 7

    def test_not_at_brace(self):
        from pdf_to_speech.latex import _extract_braced
        content, end = _extract_braced("hello", 0)
        assert content == ""
        assert end == 0

    def test_offset(self):
        from pdf_to_speech.latex import _extract_braced
        content, end = _extract_braced(r"\title{My Paper}", 6)
        assert content == "My Paper"
        assert end == 16


# ---------------------------------------------------------------------------
# Unit tests for _strip_comments / _expand_includes
# ---------------------------------------------------------------------------

class TestStripComments:
    def test_strips_comment(self):
        from pdf_to_speech.latex import _strip_comments
        result = _strip_comments("text % a comment\nmore text")
        assert "a comment" not in result
        assert "more text" in result

    def test_keeps_escaped_percent(self):
        from pdf_to_speech.latex import _strip_comments
        result = _strip_comments(r"50\% of respondents")
        assert r"\%" in result


class TestExpandIncludes:
    def test_expands_input(self, tmp_path):
        from pdf_to_speech.latex import _expand_includes
        sub = tmp_path / "sub.tex"
        sub.write_text("Sub content here.", encoding="utf-8")
        text = r"\input{sub}"
        result = _expand_includes(text, tmp_path)
        assert "Sub content here." in result

    def test_missing_file_becomes_empty(self, tmp_path):
        from pdf_to_speech.latex import _expand_includes
        result = _expand_includes(r"\input{nonexistent}", tmp_path)
        assert result.strip() == ""

    def test_expands_without_extension(self, tmp_path):
        from pdf_to_speech.latex import _expand_includes
        (tmp_path / "chap.tex").write_text("Chapter text.", encoding="utf-8")
        result = _expand_includes(r"\input{chap}", tmp_path)
        assert "Chapter text." in result


# ---------------------------------------------------------------------------
# Integration tests: parse_latex_project on the mock Overleaf fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_folder():
    if not MOCK_OVERLEAF.exists():
        pytest.skip("mock_overleaf fixture not found")
    return MOCK_OVERLEAF


class TestParseMockProject:
    def test_returns_list_of_dicts(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        assert isinstance(elements, list)
        assert len(elements) > 0
        for elem in elements:
            assert isinstance(elem, dict)
            assert len(elem) == 1

    def test_title_is_first_element(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        assert list(elements[0].keys())[0] == "Title"
        assert "Economic Returns" in list(elements[0].values())[0]

    def test_abstract_present(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        abstracts = _values_of(elements, "Abstract")
        assert len(abstracts) == 1
        assert "42 countries" in abstracts[0]

    def test_section_headlines_numbered(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        headlines = _values_of(elements, "Headline")
        assert any(h.startswith("1.") for h in headlines)
        assert any(h.startswith("2.") for h in headlines)
        assert any(h.startswith("3.") for h in headlines)
        assert any(h.startswith("4.") for h in headlines)

    def test_subsection_headlines_numbered(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        headlines = _values_of(elements, "Headline")
        assert any("2.1" in h for h in headlines)
        assert any("2.2" in h for h in headlines)

    def test_appendix_uses_letters(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        headlines = _values_of(elements, "Headline")
        assert any(h.startswith("A.") for h in headlines)

    def test_table_extracted(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        tables = _values_of(elements, "Table")
        assert len(tables) >= 1
        assert any("High Income" in t for t in tables)

    def test_table_caption_extracted(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        captions = _values_of(elements, "Table_caption")
        assert len(captions) >= 1
        assert any("Education" in c for c in captions)

    def test_paragraphs_present(self, mock_folder):
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        paras = _values_of(elements, "Paragraph")
        assert len(paras) >= 4

    def test_appendix_content_included(self, mock_folder):
        """Content from appendix.tex (via \\input) must appear."""
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        all_text = " ".join(list(e.values())[0] for e in elements)
        assert "Robustness" in all_text

    def test_table_from_tables_subfolder(self, mock_folder):
        """Table content from Tables/table1.tex (via \\input) must appear."""
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        tables = _values_of(elements, "Table")
        assert any("Middle Income" in t for t in tables)

    def test_order_is_document_order(self, mock_folder):
        """Title → Abstract → Intro → … → Conclusion → Appendix."""
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        kinds = _kinds(elements)
        assert kinds[0] == "Title"
        # Abstract appears before any Headline
        first_abstract = next(i for i, k in enumerate(kinds) if k == "Abstract")
        first_headline = next(i for i, k in enumerate(kinds) if k == "Headline")
        assert first_abstract < first_headline

    def test_no_latex_commands_in_output(self, mock_folder):
        """Cleaned text should not contain raw LaTeX commands."""
        from pdf_to_speech.latex import parse_latex_project
        elements = parse_latex_project(mock_folder)
        for elem in elements:
            val = list(elem.values())[0]
            assert "\\" not in val, f"Backslash found in element: {val!r}"

    def test_missing_main_file_raises(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        with pytest.raises(FileNotFoundError):
            parse_latex_project(tmp_path, main_file="nonexistent.tex")


# ---------------------------------------------------------------------------
# Unit tests for _element_to_text (overleaf module)
# ---------------------------------------------------------------------------

class TestElementToText:
    def test_paragraph_returned_as_is(self):
        from pdf_to_speech.overleaf import _element_to_text
        elem = {"Paragraph": "Hello world."}
        assert _element_to_text(elem) == "Hello world."

    def test_title_returned_as_is(self):
        from pdf_to_speech.overleaf import _element_to_text
        elem = {"Title": "My Great Paper"}
        assert _element_to_text(elem) == "My Great Paper"

    def test_headline_returned_as_is(self):
        from pdf_to_speech.overleaf import _element_to_text
        elem = {"Headline": "1. Introduction"}
        assert _element_to_text(elem) == "1. Introduction"

    def test_table_gets_prefix(self):
        from pdf_to_speech.overleaf import _element_to_text
        elem = {"Table": "A   B\n1   2"}
        result = _element_to_text(elem)
        assert result is not None
        assert "Table data:" in result
        assert "A" in result

    def test_table_caption_returned(self):
        from pdf_to_speech.overleaf import _element_to_text
        elem = {"Table_caption": "Table 1: Main results"}
        assert _element_to_text(elem) == "Table 1: Main results"

    def test_figure_caption_returned(self):
        from pdf_to_speech.overleaf import _element_to_text
        elem = {"Figure_caption": "Distribution of returns"}
        assert _element_to_text(elem) == "Distribution of returns"

    def test_empty_paragraph_returns_none(self):
        from pdf_to_speech.overleaf import _element_to_text
        assert _element_to_text({"Paragraph": ""}) is None

    def test_empty_table_returns_none(self):
        from pdf_to_speech.overleaf import _element_to_text
        assert _element_to_text({"Table": ""}) is None
