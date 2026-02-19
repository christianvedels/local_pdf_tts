"""LaTeX project parser: extract ordered content elements for TTS.

Public API
----------
parse_latex_project(folder, main_file="main.tex") -> list[Element]
    Parse a LaTeX project folder and return an ordered list of dicts
    describing each content element (title, headline, paragraph, table, …).

Element = dict[str, str]
    A single-key dict such as {"Title": "…"}, {"Headline": "1. Introduction"},
    {"Paragraph": "…"}, {"Table": "…"}, {"Table_caption": "…"},
    {"Figure_caption": "…"}, {"Abstract": "…"}.
"""

from __future__ import annotations

import re
from pathlib import Path

# A single content element, e.g. {"Headline": "1. Introduction"}
Element = dict[str, str]


# ---------------------------------------------------------------------------
# Step 1 – text preprocessing
# ---------------------------------------------------------------------------

def _strip_comments(text: str) -> str:
    """Remove LaTeX ``% …`` comments, but not ``\\%``."""
    return re.sub(r"(?<!\\)%[^\n]*", "", text)


def _expand_includes(text: str, base_dir: Path) -> str:
    """Recursively expand ``\\input{}`` and ``\\include{}`` commands."""

    def _replace(m: re.Match) -> str:
        fname = m.group(1).strip()
        if not fname.endswith(".tex"):
            fname += ".tex"
        fpath = base_dir / fname
        if fpath.exists():
            content = fpath.read_text(encoding="utf-8", errors="replace")
            content = _strip_comments(content)
            return _expand_includes(content, fpath.parent)
        return ""  # file not found – skip silently

    text = re.sub(r"\\input\s*\{([^}]+)\}", _replace, text)
    text = re.sub(r"\\include\s*\{([^}]+)\}", _replace, text)
    return text


# ---------------------------------------------------------------------------
# Step 2 – low-level brace/bracket helpers
# ---------------------------------------------------------------------------

def _extract_braced(text: str, pos: int) -> tuple[str, int]:
    """Extract the content of balanced braces starting at *pos*.

    *pos* must point at ``{``.  Returns ``(content, pos_after_closing_brace)``.
    If the opening brace is absent or unmatched, returns ``("", pos)``.
    """
    if pos >= len(text) or text[pos] != "{":
        return "", pos
    depth = 0
    i = pos
    while i < len(text):
        ch = text[i]
        if ch == "\\":
            i += 2  # skip escaped character
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[pos + 1 : i], i + 1
        i += 1
    # Unmatched brace – return everything to end
    return text[pos + 1 :], len(text)


def _skip_optional_arg(text: str, pos: int) -> int:
    """Skip a ``[…]`` optional argument at *pos* (after any whitespace).

    Returns the new position after the ``]``, or *pos* unchanged if no
    optional argument is present.
    """
    i = pos
    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i < len(text) and text[i] == "[":
        while i < len(text) and text[i] != "]":
            i += 1
        return i + 1 if i < len(text) else pos
    return pos


# ---------------------------------------------------------------------------
# Step 3 – environment extraction
# ---------------------------------------------------------------------------

def _find_env_end(text: str, content_start: int, env_name: str) -> tuple[str, int]:
    """Locate the matching ``\\end{env_name}`` for the content starting at
    *content_start* (i.e. the position *after* ``\\begin{env_name}``).

    Handles nested occurrences of the same environment name.

    Returns ``(env_content, pos_after_end_command)``.
    """
    esc = re.escape(env_name)
    begin_re = re.compile(r"\\begin\s*\{" + esc + r"\*?\}")
    end_re = re.compile(r"\\end\s*\{" + esc + r"\*?\}")

    depth = 1
    scan = content_start
    while depth > 0:
        nb = begin_re.search(text, scan)
        ne = end_re.search(text, scan)

        if ne is None:
            # No matching end found – consume everything
            return text[content_start:], len(text)

        if nb is not None and nb.start() < ne.start():
            depth += 1
            scan = nb.end()
        else:
            depth -= 1
            if depth == 0:
                return text[content_start : ne.start()], ne.end()
            scan = ne.end()

    return text[content_start:], len(text)  # unreachable, but satisfies type checker


# ---------------------------------------------------------------------------
# Step 4 – LaTeX → plain text cleaning
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Strip LaTeX markup from *text* and return readable plain text."""
    # --- display math ---
    text = re.sub(
        r"\\begin\{(?:equation|align|eqnarray|gather|multline|displaymath)\*?\}"
        r".*?"
        r"\\end\{(?:equation|align|eqnarray|gather|multline|displaymath)\*?\}",
        " formula ",
        text,
        flags=re.DOTALL,
    )
    text = re.sub(r"\$\$.*?\$\$", " formula ", text, flags=re.DOTALL)
    # --- inline math ---
    text = re.sub(r"\$[^$\n]{0,200}\$", "formula", text)

    # --- spacing / layout commands (strip before FMT so they don't merge
    #     with adjacent command names, e.g. \noindent\textbf → \noindenttext) ---
    text = re.sub(
        r"\\(?:noindent|bigskip|medskip|smallskip|vfill|hfill)\b", " ", text
    )
    text = re.sub(r"\\(?:vspace|hspace)\*?\{[^}]*\}", " ", text)
    text = re.sub(r"\\(?:newline|linebreak)\b\*?", " ", text)
    text = re.sub(r"\\\\(?:\[[^\]]*\])?", " ", text)
    text = re.sub(
        r"\\(?:newpage|clearpage|cleardoublepage|maketitle|tableofcontents"
        r"|bibliographystyle|bibliography)\b(?:\{[^}]*\})?",
        "",
        text,
    )

    # --- commands whose content should be dropped ---
    text = re.sub(r"\\(?:cite[a-z]*|ref|eqref|label|pageref)\{[^}]*\}", "", text)
    text = re.sub(
        r"\\footnote\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}", "", text
    )
    text = re.sub(
        r"\\includegraphics\s*(?:\[[^\]]*\])?\{[^}]*\}", "", text
    )

    # --- hyperlinks ---
    text = re.sub(r"\\url\{([^}]*)\}", r"\1", text)
    text = re.sub(r"\\href\{[^}]*\}\{([^{}]*)\}", r"\1", text)

    # --- formatting commands – keep inner text (multiple passes for nesting) ---
    _FMT_CMDS = (
        "textbf|textit|emph|texttt|textrm|textsc|textup|textsf|textmd|text"
    )
    for _ in range(4):
        text = re.sub(r"\\(?:" + _FMT_CMDS + r")\{([^{}]*)\}", r"\1", text)

    # --- tilde non-breaking space ---
    text = text.replace("~", " ")

    # --- remaining commands with a single braced argument – keep content ---
    for _ in range(4):
        text = re.sub(r"\\[a-zA-Z]+\*?\{([^{}]*)\}", r"\1", text)

    # --- remaining commands (no content) ---
    text = re.sub(r"\\[a-zA-Z]+\*?", " ", text)

    # --- escaped special characters ---
    text = re.sub(r"\\([%$&#_{}|<>])", r"\1", text)

    # --- stray braces ---
    text = re.sub(r"[{}]", "", text)

    # --- typographic dashes ---
    text = text.replace("---", "\u2014").replace("--", "\u2013")

    # --- normalise whitespace ---
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Step 5 – table parsing helpers
# ---------------------------------------------------------------------------

def _tabular_to_text(tabular_content: str) -> str:
    """Convert tabular body (rows separated by ``\\\\``) to readable text."""
    # Remove decorative rules
    content = re.sub(r"\\(?:toprule|midrule|bottomrule|hline)\b", "", tabular_content)
    rows = content.split("\\\\")
    lines: list[str] = []
    for row in rows:
        cells = [_clean_text(c).strip() for c in row.split("&")]
        cells = [c for c in cells if c]
        if cells:
            lines.append("   ".join(cells))
    return "\n".join(lines)


def _parse_table_env(text: str, elements: list[Element]) -> None:
    """Parse the body of a ``table``/``table*`` environment and append elements."""
    # -- captions --
    captions: list[str] = []
    for m in re.finditer(r"\\caption\s*(?:\[[^\]]*\])?\s*\{", text):
        content, _ = _extract_braced(text, m.end() - 1)
        cap = _clean_text(content).strip()
        if cap:
            captions.append(cap)

    # -- tabular content --
    tab_m = re.search(r"\\begin\s*\{(tabular[x*]?)\}", text)
    table_text = ""
    if tab_m:
        env_name = tab_m.group(1)
        after_begin = tab_m.end()
        # Skip optional position argument [pos]
        after_begin = _skip_optional_arg(text, after_begin)
        # Skip the mandatory column-spec argument
        _, after_spec = _extract_braced(text, after_begin)
        tabular_content, _ = _find_env_end(text, after_spec, env_name)
        table_text = _tabular_to_text(tabular_content)

    if table_text:
        elements.append({"Table": table_text})

    for cap in captions:
        elements.append({"Table_caption": cap})

    # -- notes / text after the tabular environment --
    after_tab_m = re.search(r"\\end\{tabular[x*]?\}", text)
    if after_tab_m:
        notes_raw = text[after_tab_m.end() :]
        # Strip \end{table...} marker
        notes_raw = re.sub(r"\\end\s*\{table\*?\}", "", notes_raw)
        notes = _clean_text(notes_raw).strip()
        if notes and len(notes) > 5:
            elements.append({"Table_caption": notes})


def _parse_figure_env(text: str, elements: list[Element]) -> None:
    """Parse the body of a ``figure``/``figure*`` environment and append elements."""
    for m in re.finditer(r"\\caption\s*(?:\[[^\]]*\])?\s*\{", text):
        content, _ = _extract_braced(text, m.end() - 1)
        cap = _clean_text(content).strip()
        if cap:
            elements.append({"Figure_caption": cap})


# ---------------------------------------------------------------------------
# Step 6 – main body parser
# ---------------------------------------------------------------------------

# Pattern that matches the "interesting" LaTeX tokens we act on.
_TOKEN = re.compile(
    r"\\((?:sub)*section)\s*\*?|"   # group 1: section command name
    r"\\appendix\b|"                 # appendix switch
    r"\\begin\s*\{(\w+\*?)\}|"      # group 2: \begin{env}
    r"\\maketitle\b",                # maketitle (skip)
    re.IGNORECASE,
)

# Environments we handle by diving into their content
_TRANSPARENT_ENVS = frozenset(
    [
        "document",
        "center",
        "flushleft",
        "flushright",
        "quote",
        "quotation",
        "verse",
        "minipage",
        "framed",
        "mdframed",
        "tcolorbox",
        "columns",
        "column",
        "frame",  # beamer
    ]
)

# Environments we skip entirely (no spoken content)
_SKIP_ENVS = frozenset(
    [
        "tikzpicture",
        "pgfpicture",
        "lstlisting",
        "verbatim",
        "verbatim*",
        "algorithm",
        "algorithmic",
        "comment",
        "filecontents",
        "thebibliography",
        "equation",
        "equation*",
        "align",
        "align*",
        "eqnarray",
        "eqnarray*",
        "gather",
        "gather*",
        "multline",
        "multline*",
        "displaymath",
        "array",
        "pmatrix",
        "bmatrix",
    ]
)


def _flush_text(buf: list[str], elements: list[Element]) -> None:
    """Emit any accumulated text in *buf* as ``Paragraph`` elements."""
    if not buf:
        return
    raw = " ".join(buf)
    buf.clear()
    # Split on blank lines to produce separate paragraph elements
    for chunk in re.split(r"\n{2,}", raw):
        cleaned = _clean_text(chunk)
        if cleaned and len(cleaned) > 10:
            elements.append({"Paragraph": cleaned})


def _heading_label(level: int, counters: list[int], in_appendix: bool) -> str:
    """Format a section label such as ``"1."`` or ``"A.1"``."""
    if not in_appendix:
        if level == 0:
            return f"{counters[0]}."
        elif level == 1:
            return f"{counters[0]}.{counters[1]}"
        else:
            return f"{counters[0]}.{counters[1]}.{counters[2]}"
    else:
        letter = chr(ord("A") + counters[0] - 1)
        if level == 0:
            return f"{letter}."
        elif level == 1:
            return f"{letter}.{counters[1]}"
        else:
            return f"{letter}.{counters[1]}.{counters[2]}"


def _parse_body(
    text: str,
    elements: list[Element],
    counters: list[int],
    in_appendix: bool,
) -> None:
    """Recursively parse LaTeX body text and append elements to *elements*.

    Parameters
    ----------
    text:
        The LaTeX source to parse (already stripped of comments and with
        includes expanded).
    elements:
        Output list – elements are appended in document order.
    counters:
        Mutable ``[section, subsection, subsubsection]`` counters shared
        across recursive calls so that numbering is global.
    in_appendix:
        When ``True``, section letters (A, B, …) are used instead of numbers.
    """
    pos = 0
    n = len(text)
    text_buf: list[str] = []

    while pos < n:
        m = _TOKEN.search(text, pos)

        if m is None:
            # No more tokens – collect remaining text
            text_buf.append(text[pos:])
            break

        # --- text before this token ---
        text_buf.append(text[pos : m.start()])

        token = m.group(0)

        # ── \\maketitle ───────────────────────────────────────────────────
        if token == r"\maketitle":
            pos = m.end()
            continue

        # ── \\appendix ───────────────────────────────────────────────────
        if token == r"\appendix":
            in_appendix = True
            counters[0] = 0
            counters[1] = 0
            counters[2] = 0
            pos = m.end()
            continue

        # ── section commands ─────────────────────────────────────────────
        if m.group(1) is not None:
            cmd = m.group(1).lower()  # "section", "subsection", "subsubsection"
            level = cmd.count("sub")  # 0, 1, or 2
            _flush_text(text_buf, elements)
            # Advance past any optional [short-title] argument
            after_cmd = _skip_optional_arg(text, m.end())
            # Extract the heading text
            heading_raw, after_heading = _extract_braced(text, after_cmd)
            heading = _clean_text(heading_raw).strip()
            # Update counters
            counters[level] += 1
            for i in range(level + 1, 3):
                counters[i] = 0
            label = _heading_label(level, counters, in_appendix)
            elements.append({"Headline": f"{label} {heading}"})
            pos = after_heading
            continue

        # ── \\begin{env} ──────────────────────────────────────────────────
        env_name_raw = m.group(2)
        if env_name_raw is None:
            pos = m.end()
            continue

        env_name = env_name_raw.rstrip("*")  # normalise starred variants
        # Skip optional position argument [h!] etc.
        after_begin = _skip_optional_arg(text, m.end())
        # Extract the environment content up to matching \end{...}
        env_content, after_env = _find_env_end(text, after_begin, env_name)

        if env_name == "abstract":
            _flush_text(text_buf, elements)
            cleaned = _clean_text(env_content)
            if cleaned:
                elements.append({"Abstract": cleaned})

        elif env_name in ("table", "table*"):
            _flush_text(text_buf, elements)
            _parse_table_env(env_content, elements)

        elif env_name in ("figure", "figure*"):
            _flush_text(text_buf, elements)
            _parse_figure_env(env_content, elements)

        elif env_name in ("itemize", "enumerate", "description"):
            # Treat each \item as a mini-paragraph
            _flush_text(text_buf, elements)
            items_text = re.sub(r"\\item\s*", "\n\n", env_content)
            _parse_body(items_text, elements, counters, in_appendix)

        elif env_name in _TRANSPARENT_ENVS:
            # Descend into these without special treatment
            _parse_body(env_content, elements, counters, in_appendix)

        elif env_name in _SKIP_ENVS:
            pass  # discard content

        else:
            # Unknown environment – treat like transparent
            _parse_body(env_content, elements, counters, in_appendix)

        pos = after_env

    _flush_text(text_buf, elements)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_latex_project(
    folder: str | Path,
    main_file: str = "main.tex",
) -> list[Element]:
    """Parse a LaTeX project folder and return an ordered list of content elements.

    Each element is a single-key ``dict`` describing one piece of content:

    * ``{"Title": "…"}``           — from ``\\title{…}``
    * ``{"Abstract": "…"}``        — from ``\\begin{abstract}``
    * ``{"Headline": "1. …"}``     — from ``\\section``, ``\\subsection``, …
    * ``{"Paragraph": "…"}``       — body prose
    * ``{"Table": "…"}``           — tabular data rendered as aligned text
    * ``{"Table_caption": "…"}``   — from ``\\caption`` inside a table
    * ``{"Figure_caption": "…"}``  — from ``\\caption`` inside a figure

    Parameters
    ----------
    folder:
        Path to the project root directory.
    main_file:
        Name of the root ``.tex`` file (default ``"main.tex"``).

    Returns
    -------
    list[Element]
        Elements in document order.
    """
    folder = Path(folder)
    main_path = folder / main_file
    if not main_path.exists():
        raise FileNotFoundError(f"Main file not found: {main_path}")

    # 1. Load, strip comments, expand includes
    raw = main_path.read_text(encoding="utf-8", errors="replace")
    raw = _strip_comments(raw)
    raw = _expand_includes(raw, folder)

    # 2. Extract title from preamble (before \begin{document})
    doc_begin = re.search(r"\\begin\s*\{document\}", raw)
    preamble = raw[: doc_begin.start()] if doc_begin else raw
    title: str | None = None
    tm = re.search(r"\\title\s*\{", preamble)
    if tm:
        title_raw, _ = _extract_braced(preamble, tm.end() - 1)
        title = _clean_text(title_raw).strip() or None

    # 3. Isolate document body
    if doc_begin is None:
        body = raw
    else:
        doc_end = re.search(r"\\end\s*\{document\}", raw)
        body = raw[doc_begin.end() : (doc_end.start() if doc_end else None)]

    # 4. Parse
    elements: list[Element] = []
    if title:
        elements.append({"Title": title})

    counters = [0, 0, 0]  # section / subsection / subsubsection
    _parse_body(body, elements, counters, in_appendix=False)

    return elements
