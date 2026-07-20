"""
Rich Diff Renderable
====================

Implements a unified/split diff renderable for the Rich terminal library.

Usage::

    from rich.diff import Diff

    console = Console()
    console.print(Diff(old_text, new_text))
    console.print(Diff(old_text, new_text, view="split"))
    console.print(Diff.from_paths("old.py", "new.py", syntax="python"))

Author: chengfengyi-falcon
License: MIT
"""

from __future__ import annotations

import difflib
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Union

from rich.console import Console, ConsoleOptions, RenderResult
from rich.measure import Measurement
from rich.padding import Padding
from rich.panel import Panel
from rich.segment import Segment
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text, TextType


# ── Default diff styles ────────────────────────────────────────────

ADDED_STYLE = Style(bgcolor="dark_green", color="white")
REMOVED_STYLE = Style(bgcolor="dark_red", color="white")
HEADER_STYLE = Style(bold=True, color="cyan")
HUNK_STYLE = Style(bold=True, color="yellow")
LINE_NO_STYLE = Style(color="grey50", dim=True)
GUTTER_STYLE = Style(color="grey50")


class Diff:
    """Render a unified or split diff of two texts with Rich styling.

    Args:
        a: Original text.
        b: Modified text.
        view: ``"unified"`` (default) or ``"split"``.
        syntax: Optional pygments lexer name for syntax highlighting of
            each line's content.
        context_lines: Number of context lines in unified view (default 3).
        title_a: Label for the left / old side.
        title_b: Label for the right / new side.
        show_line_numbers: Show line numbers (unified view only).
    """

    def __init__(
        self,
        a: str,
        b: str,
        *,
        view: str = "unified",
        syntax: Optional[str] = None,
        context_lines: int = 3,
        title_a: Optional[str] = None,
        title_b: Optional[str] = None,
        show_line_numbers: bool = True,
    ) -> None:
        self.a = a
        self.b = b
        self.view = view
        self.syntax = syntax
        self.context_lines = context_lines
        self.title_a = title_a or "--- a"
        self.title_b = title_b or "+++ b"
        self.show_line_numbers = show_line_numbers

        # Pre-compute diff hunks for efficient rendering
        self._hunks: List[List[Tuple[str, str]]] = []
        self._compute_diff()

    # ── Constructors ──────────────────────────────────────────────

    @classmethod
    def from_paths(
        cls,
        path_a: Union[str, Path],
        path_b: Union[str, Path],
        *,
        view: str = "unified",
        syntax: Optional[str] = None,
        context_lines: int = 3,
    ) -> "Diff":
        """Create a Diff from two file paths.

        Args:
            path_a: Path to original file.
            path_b: Path to modified file.
            view: ``"unified"`` or ``"split"``.
            syntax: Optional pygments lexer name. Auto-detected from
                file extension if not provided.
            context_lines: Context lines for unified view.
        """
        path_a = Path(path_a)
        path_b = Path(path_b)

        a_text = path_a.read_text(encoding="utf-8", errors="replace")
        b_text = path_b.read_text(encoding="utf-8", errors="replace")

        if syntax is None:
            # Try to detect from either path's extension
            ext = path_b.suffix or path_a.suffix
            syntax = _guess_lexer(ext)

        return cls(
            a_text,
            b_text,
            view=view,
            syntax=syntax,
            context_lines=context_lines,
            title_a=str(path_a),
            title_b=str(path_b),
        )

    # ── Diff computation ───────────────────────────────────────────

    def _compute_diff(self) -> None:
        """Compute diff hunks using difflib.SequenceMatcher."""
        a_lines = self.a.splitlines(keepends=True)
        b_lines = self.b.splitlines(keepends=True)

        matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
        opcodes = matcher.get_grouped_opcodes(n=self.context_lines)

        for group in opcodes:
            hunk: List[Tuple[str, str]] = []
            has_changes = False
            for tag, i1, i2, j1, j2 in group:
                if tag != "equal":
                    has_changes = True
                for idx in range(i1, i2):
                    line = a_lines[idx]
                    hunk.append((tag if tag != "equal" else " ", line))
                for idx in range(j1, j2):
                    line = b_lines[idx]
                    if tag == "replace":
                        # Show old as removed, new as added
                        pass  # handled in unified_diff below
                    elif tag == "delete":
                        hunk.append(("-", a_lines[idx]))
                    elif tag == "insert":
                        hunk.append(("+", b_lines[idx]))
            if has_changes:
                self._hunks.append(hunk)

        # Build proper unified view hunks
        self._unified_lines: List[Tuple[str, str, Optional[int], Optional[int]]] = []
        self._compute_unified(a_lines, b_lines)

    def _compute_unified(
        self, a_lines: List[str], b_lines: List[str]
    ) -> None:
        """Compute unified-diff style line list with line numbers."""
        matcher = difflib.SequenceMatcher(None, a_lines, b_lines)

        for group in matcher.get_grouped_opcodes(n=self.context_lines):
            # Determine hunk header line range
            i1_start = group[0][1] + 1
            i2_end = group[-1][2]
            j1_start = group[0][3] + 1
            j2_end = group[-1][4]
            old_count = i2_end - i1_start + 1
            new_count = j2_end - j1_start + 1

            # Hunk header
            self._unified_lines.append(
                ("@", f"@@ -{i1_start},{old_count} +{j1_start},{new_count} @@", None, None)
            )

            for tag, i1, i2, j1, j2 in group:
                if tag == "equal":
                    for idx in range(i1, i2):
                        line = a_lines[idx].rstrip("\n\r")
                        self._unified_lines.append((" ", line, idx + 1, j1 + (idx - i1) + 1))
                elif tag == "replace":
                    for idx in range(i1, i2):
                        line = a_lines[idx].rstrip("\n\r")
                        self._unified_lines.append(("-", line, idx + 1, None))
                    for idx in range(j1, j2):
                        line = b_lines[idx].rstrip("\n\r")
                        self._unified_lines.append(("+", line, None, idx + 1))
                elif tag == "delete":
                    for idx in range(i1, i2):
                        line = a_lines[idx].rstrip("\n\r")
                        self._unified_lines.append(("-", line, idx + 1, None))
                elif tag == "insert":
                    for idx in range(j1, j2):
                        line = b_lines[idx].rstrip("\n\r")
                        self._unified_lines.append(("+", line, None, idx + 1))

        # Handle empty case
        if not self._unified_lines:
            for idx, line in enumerate(a_lines):
                self._unified_lines.append((" ", line.rstrip("\n\r"), idx + 1, idx + 1))

    # ── Rendering ──────────────────────────────────────────────────

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        if self.view == "split":
            yield from self._render_split(console, options)
        else:
            yield from self._render_unified(console, options)

    def __rich_measure__(
        self, console: Console, options: ConsoleOptions
    ) -> Measurement:
        # Diff fills available width
        return Measurement(options.max_width, options.max_width)

    # ── Unified view ──────────────────────────────────────────────

    def _render_unified(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Render as unified diff."""
        # Header
        yield Text(self.title_a, style=HEADER_STYLE)
        yield Segment.line()
        yield Text(self.title_b, style=HEADER_STYLE)
        yield Segment.line()
        yield Segment.line()

        # Build styled lines
        for prefix, line, old_no, new_no in self._unified_lines:
            segments: List[Segment] = []

            # Prefix symbol
            if prefix == "@":
                style = HUNK_STYLE
            elif prefix == "-":
                style = REMOVED_STYLE
            elif prefix == "+":
                style = ADDED_STYLE
            else:
                style = Style()

            # Line numbers
            if self.show_line_numbers:
                old_str = f"{old_no:>5} " if old_no is not None else "      "
                new_str = f"{new_no:>5} " if new_no is not None else "      "
                segments.append(Segment(old_str, LINE_NO_STYLE))
                segments.append(Segment(new_str, LINE_NO_STYLE))

            segments.append(Segment(f"{prefix} ", Style(bold=True)))

            # Syntax-highlighted content
            if self.syntax and line.strip():
                try:
                    highlighted = _highlight_line(line, self.syntax, console, options)
                    styled_segments = Segment.apply_style(highlighted, style)
                    segments.extend(styled_segments)
                except Exception:
                    segments.append(Segment(line, style))
            else:
                segments.append(Segment(line, style))

            segments.append(Segment.line())
            yield from segments

    # ── Split view ─────────────────────────────────────────────────

    def _render_split(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Render as side-by-side split diff."""
        a_lines = self.a.splitlines()
        b_lines = self.b.splitlines()

        # Build aligned row pairs: (left_tag, left_idx, right_tag, right_idx)
        pairs: List[Tuple[str, Optional[int], str, Optional[int]]] = []
        sm = difflib.SequenceMatcher(None, a_lines, b_lines)

        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                for k in range(i2 - i1):
                    pairs.append((" ", i1 + k, " ", j1 + k))
            elif tag == "replace":
                for k in range(max(i2 - i1, j2 - j1)):
                    l_idx = i1 + k if k < (i2 - i1) else None
                    r_idx = j1 + k if k < (j2 - j1) else None
                    pairs.append(("-" if l_idx is not None else "~", l_idx,
                                  "+" if r_idx is not None else "~", r_idx))
            elif tag == "delete":
                for k in range(i1, i2):
                    pairs.append(("-", k, "~", None))
            elif tag == "insert":
                for k in range(j1, j2):
                    pairs.append(("~", None, "+", k))

        half_width = max(20, (options.max_width - 5) // 2) if options.max_width else 80

        table = Table(
            show_header=True,
            header_style=HEADER_STYLE,
            box=None,
            padding=(0, 0, 0, 0),
            show_edge=False,
            expand=True,
            collapse_padding=True,
        )
        table.add_column(self.title_a, width=half_width, no_wrap=False, overflow="fold")
        table.add_column("", width=1, style=Style.null())
        table.add_column(self.title_b, width=half_width, no_wrap=False, overflow="fold")

        for l_tag, old_idx, r_tag, new_idx in pairs:
            left = self._make_cell(l_tag, old_idx, a_lines, half_width)
            right = self._make_cell(r_tag, new_idx, b_lines, half_width)
            table.add_row(left, "", right)

        yield table

    @staticmethod
    def _make_cell(
        tag: str,
        line_idx: Optional[int],
        lines: List[str],
        width: int,
    ) -> Text:
        """Build one cell of the split view."""
        if tag == "~" or line_idx is None:
            return Text("")

        if tag == "-":
            style = REMOVED_STYLE
        elif tag == "+":
            style = ADDED_STYLE
        else:
            style = Style()

        content = lines[line_idx] if line_idx < len(lines) else ""
        if len(content) > width:
            content = content[: width - 1] + "…"

        text = Text(content, style=style, no_wrap=True)
        return text


# ── Helpers ────────────────────────────────────────────────────────

# Map common extensions to pygments lexers
_EXT_LEXER_MAP = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".jsx": "javascript",
    ".tsx": "typescript",
    ".html": "html",
    ".css": "css",
    ".scss": "scss",
    ".json": "json",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".md": "markdown",
    ".rst": "rst",
    ".toml": "toml",
    ".ini": "ini",
    ".cfg": "ini",
    ".sh": "bash",
    ".bash": "bash",
    ".zsh": "bash",
    ".sql": "sql",
    ".xml": "xml",
    ".java": "java",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".hpp": "cpp",
    ".rs": "rust",
    ".go": "go",
    ".rb": "ruby",
    ".R": "r",
    ".tex": "latex",
    ".diff": "diff",
    ".patch": "diff",
}


def _guess_lexer(ext: str) -> Optional[str]:
    """Guess a pygments lexer name from a file extension."""
    ext = ext.lower()
    if ext in _EXT_LEXER_MAP:
        return _EXT_LEXER_MAP[ext]
    # Try without leading dot
    if not ext.startswith(".") and f".{ext}" in _EXT_LEXER_MAP:
        return _EXT_LEXER_MAP[f".{ext}"]
    return None


def _highlight_line(
    line: str, lexer: str, console: Console, options: ConsoleOptions
) -> List[Segment]:
    """Highlight a single line of code and return Segments."""
    syntax = Syntax(line, lexer, theme="monokai", word_wrap=False)
    segments = list(console.render(syntax, options))
    # Remove trailing newline segment
    if segments and segments[-1].text == "\n":
        segments.pop()
    return segments
