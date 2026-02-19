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


# ---------------------------------------------------------------------------
# Unit tests for _skip_optional_arg
# ---------------------------------------------------------------------------

class TestSkipOptionalArg:
    def test_no_optional_arg(self):
        from pdf_to_speech.latex import _skip_optional_arg
        text = "{content}"
        assert _skip_optional_arg(text, 0) == 0

    def test_skips_bracket_arg(self):
        from pdf_to_speech.latex import _skip_optional_arg
        text = "[h!]{content}"
        result = _skip_optional_arg(text, 0)
        assert result == 4  # after ']'

    def test_skips_whitespace_then_bracket(self):
        from pdf_to_speech.latex import _skip_optional_arg
        text = "  [ht]{content}"
        result = _skip_optional_arg(text, 0)
        assert text[result] == "{"

    def test_empty_bracket(self):
        from pdf_to_speech.latex import _skip_optional_arg
        text = "[]{content}"
        result = _skip_optional_arg(text, 0)
        assert result == 2  # after ']'


# ---------------------------------------------------------------------------
# Unit tests for _find_env_end
# ---------------------------------------------------------------------------

class TestFindEnvEnd:
    def test_simple_env(self):
        from pdf_to_speech.latex import _find_env_end
        text = "body text\\end{quote}"
        content, after = _find_env_end(text, 0, "quote")
        assert content == "body text"
        assert after == len(text)

    def test_nested_env(self):
        from pdf_to_speech.latex import _find_env_end
        text = "outer\\begin{quote}inner\\end{quote}more\\end{quote}"
        content, after = _find_env_end(text, 0, "quote")
        assert "inner" in content
        assert after == len(text)

    def test_no_end_returns_all(self):
        from pdf_to_speech.latex import _find_env_end
        text = "some text with no end"
        content, after = _find_env_end(text, 0, "figure")
        assert content == text
        assert after == len(text)

    def test_content_starts_at_offset(self):
        from pdf_to_speech.latex import _find_env_end
        text = "SKIP THIS  body\\end{abstract}"
        content, _ = _find_env_end(text, 10, "abstract")
        assert content == " body"


# ---------------------------------------------------------------------------
# Unit tests for _tabular_to_text
# ---------------------------------------------------------------------------

class TestTabularToText:
    def test_simple_two_column(self):
        from pdf_to_speech.latex import _tabular_to_text
        content = "A & B \\\\ 1 & 2 \\\\ 3 & 4"
        result = _tabular_to_text(content)
        assert "A" in result
        assert "B" in result
        assert "1" in result
        assert "2" in result

    def test_strips_toprule_midrule_bottomrule(self):
        from pdf_to_speech.latex import _tabular_to_text
        content = "\\toprule\nA & B \\\\\n\\midrule\n1 & 2 \\\\\n\\bottomrule"
        result = _tabular_to_text(content)
        assert "toprule" not in result
        assert "midrule" not in result
        assert "bottomrule" not in result

    def test_empty_rows_skipped(self):
        from pdf_to_speech.latex import _tabular_to_text
        content = "\\\\ A & B \\\\"
        result = _tabular_to_text(content)
        lines = [l for l in result.splitlines() if l.strip()]
        assert all("A" in l for l in lines)

    def test_cells_joined_with_spaces(self):
        from pdf_to_speech.latex import _tabular_to_text
        content = "Col1 & Col2 & Col3 \\\\"
        result = _tabular_to_text(content)
        assert "Col1" in result
        assert "Col2" in result
        assert "Col3" in result


# ---------------------------------------------------------------------------
# Unit tests for _parse_table_env
# ---------------------------------------------------------------------------

class TestParseTableEnv:
    def test_extracts_caption(self):
        from pdf_to_speech.latex import _parse_table_env
        text = (
            "\\centering\n"
            "\\caption{My Caption}\n"
            "\\begin{tabular}{lc}\n"
            "A & B \\\\\n"
            "1 & 2 \\\\\n"
            "\\end{tabular}\n"
        )
        elements: list[dict] = []
        _parse_table_env(text, elements)
        kinds = [list(e.keys())[0] for e in elements]
        assert "Table_caption" in kinds
        captions = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Table_caption"]
        assert any("My Caption" in c for c in captions)

    def test_extracts_table_data(self):
        from pdf_to_speech.latex import _parse_table_env
        text = (
            "\\begin{tabular}{lc}\n"
            "Header1 & Header2 \\\\\n"
            "Val1 & Val2 \\\\\n"
            "\\end{tabular}\n"
        )
        elements: list[dict] = []
        _parse_table_env(text, elements)
        tables = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Table"]
        assert len(tables) == 1
        assert "Header1" in tables[0]
        assert "Val1" in tables[0]

    def test_no_tabular_produces_no_table(self):
        from pdf_to_speech.latex import _parse_table_env
        text = "\\caption{Only a caption here}"
        elements: list[dict] = []
        _parse_table_env(text, elements)
        tables = [e for e in elements if list(e.keys())[0] == "Table"]
        assert len(tables) == 0

    def test_notes_after_tabular_become_caption(self):
        from pdf_to_speech.latex import _parse_table_env
        text = (
            "\\begin{tabular}{l}\n"
            "A \\\\\n"
            "\\end{tabular}\n"
            "\\textit{Notes:} Important note about the table.\n"
        )
        elements: list[dict] = []
        _parse_table_env(text, elements)
        captions = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Table_caption"]
        assert any("Important note" in c for c in captions)


# ---------------------------------------------------------------------------
# Unit tests for _parse_figure_env
# ---------------------------------------------------------------------------

class TestParseFigureEnv:
    def test_extracts_figure_caption(self):
        from pdf_to_speech.latex import _parse_figure_env
        text = "\\includegraphics{fig.png}\n\\caption{A nice figure}"
        elements: list[dict] = []
        _parse_figure_env(text, elements)
        assert len(elements) == 1
        assert list(elements[0].keys())[0] == "Figure_caption"
        assert "A nice figure" in list(elements[0].values())[0]

    def test_no_caption_produces_no_element(self):
        from pdf_to_speech.latex import _parse_figure_env
        text = "\\includegraphics{fig.png}"
        elements: list[dict] = []
        _parse_figure_env(text, elements)
        assert elements == []

    def test_multiple_captions(self):
        from pdf_to_speech.latex import _parse_figure_env
        text = (
            "\\caption{First caption}\n"
            "\\includegraphics{b.png}\n"
            "\\caption{Second caption}\n"
        )
        elements: list[dict] = []
        _parse_figure_env(text, elements)
        assert len(elements) == 2


# ---------------------------------------------------------------------------
# Unit tests for _heading_label
# ---------------------------------------------------------------------------

class TestHeadingLabel:
    def test_section_numbered(self):
        from pdf_to_speech.latex import _heading_label
        assert _heading_label(0, [3, 0, 0], False) == "3."

    def test_subsection_numbered(self):
        from pdf_to_speech.latex import _heading_label
        assert _heading_label(1, [2, 1, 0], False) == "2.1"

    def test_subsubsection_numbered(self):
        from pdf_to_speech.latex import _heading_label
        assert _heading_label(2, [1, 2, 3], False) == "1.2.3"

    def test_appendix_section_uses_letter(self):
        from pdf_to_speech.latex import _heading_label
        assert _heading_label(0, [1, 0, 0], True) == "A."
        assert _heading_label(0, [2, 0, 0], True) == "B."

    def test_appendix_subsection(self):
        from pdf_to_speech.latex import _heading_label
        assert _heading_label(1, [2, 3, 0], True) == "B.3"

    def test_appendix_subsubsection(self):
        from pdf_to_speech.latex import _heading_label
        assert _heading_label(2, [1, 2, 4], True) == "A.2.4"


# ---------------------------------------------------------------------------
# Unit tests for _flush_text
# ---------------------------------------------------------------------------

class TestFlushText:
    def test_emits_paragraph(self):
        from pdf_to_speech.latex import _flush_text
        buf = ["This is a fairly long paragraph with enough content to pass the filter."]
        elements: list[dict] = []
        _flush_text(buf, elements)
        assert len(elements) == 1
        assert list(elements[0].keys())[0] == "Paragraph"
        assert buf == []  # buffer cleared

    def test_short_text_skipped(self):
        from pdf_to_speech.latex import _flush_text
        buf = ["Hi"]
        elements: list[dict] = []
        _flush_text(buf, elements)
        assert elements == []

    def test_empty_buf_does_nothing(self):
        from pdf_to_speech.latex import _flush_text
        elements: list[dict] = []
        _flush_text([], elements)
        assert elements == []

    def test_splits_on_blank_lines(self):
        from pdf_to_speech.latex import _flush_text
        long = "A sufficiently long paragraph to pass the length threshold here."
        buf = [f"{long}\n\n{long}"]
        elements: list[dict] = []
        _flush_text(buf, elements)
        assert len(elements) == 2


# ---------------------------------------------------------------------------
# Unit tests for _parse_body (isolated scenarios)
# ---------------------------------------------------------------------------

class TestParseBody:
    def test_section_increments_counter(self):
        from pdf_to_speech.latex import _parse_body
        text = "\\section{Introduction}\n\\section{Background}"
        elements: list[dict] = []
        _parse_body(text, elements, [0, 0, 0], False)
        headlines = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Headline"]
        assert any("1." in h for h in headlines)
        assert any("2." in h for h in headlines)

    def test_subsection_resets_on_new_section(self):
        from pdf_to_speech.latex import _parse_body
        import re
        text = (
            "\\section{S1}\n"
            "\\subsection{S1.1}\n"
            "\\section{S2}\n"
            "\\subsection{S2.1}\n"
        )
        elements: list[dict] = []
        _parse_body(text, elements, [0, 0, 0], False)
        headlines = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Headline"]
        # Both subsections should be labelled X.1 (counter resets)
        subsections = [h for h in headlines if re.match(r"\d+\.\d+", h)]
        assert subsections[0].startswith("1.1")
        assert subsections[1].startswith("2.1")

    def test_appendix_switch(self):
        from pdf_to_speech.latex import _parse_body
        text = "\\appendix\n\\section{Extra Results}"
        elements: list[dict] = []
        _parse_body(text, elements, [0, 0, 0], False)
        headlines = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Headline"]
        assert any(h.startswith("A.") for h in headlines)

    def test_abstract_env_extracted(self):
        from pdf_to_speech.latex import _parse_body
        text = "\\begin{abstract}This is a test abstract with enough text.\\end{abstract}"
        elements: list[dict] = []
        _parse_body(text, elements, [0, 0, 0], False)
        abstracts = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Abstract"]
        assert len(abstracts) == 1
        assert "test abstract" in abstracts[0]

    def test_skip_env_discarded(self):
        from pdf_to_speech.latex import _parse_body
        text = (
            "\\begin{tikzpicture}DRAW STUFF\\end{tikzpicture}\n"
            "\\section{After Figure}"
        )
        elements: list[dict] = []
        _parse_body(text, elements, [0, 0, 0], False)
        all_values = " ".join(list(e.values())[0] for e in elements)
        assert "DRAW STUFF" not in all_values
        assert "After Figure" in all_values

    def test_itemize_items_become_paragraphs(self):
        from pdf_to_speech.latex import _parse_body
        text = (
            "\\begin{itemize}\n"
            "\\item First item with enough text to be a real paragraph.\n"
            "\\item Second item with enough text to be a real paragraph.\n"
            "\\end{itemize}\n"
        )
        elements: list[dict] = []
        _parse_body(text, elements, [0, 0, 0], False)
        paras = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Paragraph"]
        assert len(paras) >= 2

    def test_maketitle_ignored(self):
        from pdf_to_speech.latex import _parse_body
        text = "\\maketitle\n\\section{Introduction}"
        elements: list[dict] = []
        _parse_body(text, elements, [0, 0, 0], False)
        all_values = " ".join(list(e.values())[0] for e in elements)
        assert "maketitle" not in all_values.lower()


# ---------------------------------------------------------------------------
# Unit tests for parse_latex_project with synthetic projects (no fixture)
# ---------------------------------------------------------------------------

class TestParseLatexProjectSynthetic:
    """Self-contained tests that build minimal projects in tmp_path."""

    def _make_project(self, tmp_path, main_content, extra_files=None):
        (tmp_path / "main.tex").write_text(main_content, encoding="utf-8")
        for name, content in (extra_files or {}).items():
            fpath = tmp_path / name
            fpath.parent.mkdir(parents=True, exist_ok=True)
            fpath.write_text(content, encoding="utf-8")
        return tmp_path

    def test_minimal_title_only(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        proj = self._make_project(tmp_path, (
            "\\documentclass{article}\n"
            "\\title{Hello World}\n"
            "\\begin{document}\n"
            "\\end{document}\n"
        ))
        elements = parse_latex_project(proj)
        assert elements[0] == {"Title": "Hello World"}

    def test_no_title_in_preamble(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        proj = self._make_project(tmp_path, (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\section{Intro}\n"
            "\\end{document}\n"
        ))
        elements = parse_latex_project(proj)
        kinds = [list(e.keys())[0] for e in elements]
        assert "Title" not in kinds

    def test_include_expands(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        proj = self._make_project(
            tmp_path,
            (
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "\\input{chapter1}\n"
                "\\end{document}\n"
            ),
            extra_files={"chapter1.tex": "\\section{Chapter One}\nBody text here with lots of words.\n"},
        )
        elements = parse_latex_project(proj)
        headlines = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Headline"]
        assert any("Chapter One" in h for h in headlines)

    def test_include_in_subdirectory(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        proj = self._make_project(
            tmp_path,
            (
                "\\documentclass{article}\n"
                "\\begin{document}\n"
                "\\input{sections/intro}\n"
                "\\end{document}\n"
            ),
            extra_files={
                "sections/intro.tex": "\\section{Introduction}\nIntroductory text goes here.\n"
            },
        )
        elements = parse_latex_project(proj)
        headlines = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Headline"]
        assert any("Introduction" in h for h in headlines)

    def test_custom_main_file_name(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        (tmp_path / "paper.tex").write_text(
            "\\documentclass{article}\n\\title{Custom}\n"
            "\\begin{document}\\end{document}\n",
            encoding="utf-8",
        )
        elements = parse_latex_project(tmp_path, main_file="paper.tex")
        assert elements[0] == {"Title": "Custom"}

    def test_figure_caption_extracted(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        proj = self._make_project(tmp_path, (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{figure}[h]\n"
            "\\includegraphics{fig.png}\n"
            "\\caption{A beautiful figure}\n"
            "\\end{figure}\n"
            "\\end{document}\n"
        ))
        elements = parse_latex_project(proj)
        captions = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Figure_caption"]
        assert len(captions) == 1
        assert "beautiful figure" in captions[0]

    def test_math_env_skipped(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        proj = self._make_project(tmp_path, (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\begin{equation}\n"
            "E = mc^2\n"
            "\\end{equation}\n"
            "\\section{Text Section}\n"
            "This section has real prose content.\n"
            "\\end{document}\n"
        ))
        elements = parse_latex_project(proj)
        all_text = " ".join(list(e.values())[0] for e in elements)
        assert "mc^2" not in all_text
        assert "Text Section" in all_text

    def test_starred_section_parsed(self, tmp_path):
        from pdf_to_speech.latex import parse_latex_project
        proj = self._make_project(tmp_path, (
            "\\documentclass{article}\n"
            "\\begin{document}\n"
            "\\section*{Unnumbered Section}\n"
            "Paragraph content here.\n"
            "\\end{document}\n"
        ))
        elements = parse_latex_project(proj)
        headlines = [list(e.values())[0] for e in elements if list(e.keys())[0] == "Headline"]
        assert any("Unnumbered Section" in h for h in headlines)
