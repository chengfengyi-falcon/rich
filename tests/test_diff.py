"""
Tests for the Rich Diff renderable.
"""

import pytest
from rich.console import Console
from rich.measure import Measurement

# When installed in Rich: from rich.diff import Diff
# For standalone testing, import from the module directly
import sys
sys.path.insert(0, ".")
from rich_diff import Diff, _guess_lexer, _highlight_line


SAMPLE_A = """def hello():
    print("world")
    return True

def unused_function():
    pass
"""

SAMPLE_B = """def hello():
    print("universe")
    return True

def new_function():
    print("added")
"""


class TestDiffBasics:
    """Core Diff functionality."""

    def test_creates_diff_object(self):
        d = Diff("a\nb\n", "a\nc\n")
        assert d.a == "a\nb\n"
        assert d.b == "a\nc\n"
        assert d.view == "unified"

    def test_default_view_is_unified(self):
        d = Diff("old", "new")
        assert d.view == "unified"

    def test_split_view(self):
        d = Diff("old", "new", view="split")
        assert d.view == "split"

    def test_identical_texts(self):
        d = Diff("hello\nworld\n", "hello\nworld\n")
        assert len(d._unified_lines) >= 0  # Should not crash

    def test_empty_texts(self):
        d = Diff("", "")
        assert len(d._unified_lines) >= 0  # Should not crash

    def test_context_lines(self):
        d = Diff(SAMPLE_A, SAMPLE_B, context_lines=5)
        assert d.context_lines == 5


class TestDiffRendering:
    """Rendering tests."""

    def test_renders_unified(self):
        console = Console(force_terminal=True, width=80)
        d = Diff(SAMPLE_A, SAMPLE_B)
        result = list(d.__rich_console__(console, console.options))
        assert len(result) > 0

    def test_renders_split(self):
        console = Console(force_terminal=True, width=120)
        d = Diff(SAMPLE_A, SAMPLE_B, view="split")
        result = list(d.__rich_console__(console, console.options))
        assert len(result) > 0

    def test_renders_with_syntax(self):
        console = Console(force_terminal=True, width=80)
        d = Diff(SAMPLE_A, SAMPLE_B, syntax="python")
        result = list(d.__rich_console__(console, console.options))
        assert len(result) > 0

    def test_renders_without_line_numbers(self):
        console = Console(force_terminal=True, width=80)
        d = Diff(SAMPLE_A, SAMPLE_B, show_line_numbers=False)
        result = list(d.__rich_console__(console, console.options))
        assert len(result) > 0

    def test_unicode_text(self):
        console = Console(force_terminal=True, width=80)
        d = Diff("你好世界\n", "你好宇宙\n")
        result = list(d.__rich_console__(console, console.options))
        assert len(result) > 0


class TestDiffMeasure:
    """Measurement tests."""

    def test_measure_fills_width(self):
        console = Console(force_terminal=True, width=80)
        d = Diff("a\n", "b\n")
        m = d.__rich_measure__(console, console.options)
        assert isinstance(m, Measurement)
        assert m.maximum == 80

    def test_measure_respects_width(self):
        console = Console(force_terminal=True, width=120)
        d = Diff("a\n", "b\n")
        m = d.__rich_measure__(console, console.options)
        assert m.maximum == 120


class TestGuessLexer:
    """Lexer auto-detection."""

    def test_python(self):
        assert _guess_lexer(".py") == "python"

    def test_javascript(self):
        assert _guess_lexer(".js") == "javascript"

    def test_json(self):
        assert _guess_lexer(".json") == "json"

    def test_markdown(self):
        assert _guess_lexer(".md") == "markdown"

    def test_unknown(self):
        assert _guess_lexer(".xyz") is None

    def test_empty(self):
        assert _guess_lexer("") is None


class TestDiffEdgeCases:
    """Edge case handling."""

    def test_single_line_addition(self):
        d = Diff("line1\n", "line1\nline2\n")
        assert len(d._unified_lines) > 0

    def test_single_line_deletion(self):
        d = Diff("line1\nline2\n", "line1\n")
        assert len(d._unified_lines) > 0

    def test_single_line_change(self):
        d = Diff("old line\n", "new line\n")
        assert len(d._unified_lines) > 0

    def test_long_lines(self):
        long_a = "x" * 500 + "\n"
        long_b = "y" * 500 + "\n"
        d = Diff(long_a, long_b)
        result_lines = d._unified_lines
        assert len(result_lines) > 0

    def test_whitespace_only_change(self):
        d = Diff("hello world\n", "hello  world\n")
        assert len(d._unified_lines) > 0

    def test_blank_lines(self):
        d = Diff("a\n\nc\n", "a\nb\nc\n")
        assert len(d._unified_lines) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
