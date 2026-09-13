"""Unit tests for symbol extraction from diffs and AST."""

from pathlib import Path
from agentproof.core.models import SymbolType
from agentproof.git.symbols import SymbolExtractor


def test_extract_from_diff_text():
    extractor = SymbolExtractor()
    diff_text = (
        "@@ -10,5 +10,12 @@ def calculate_total(items):\n"
        "+    return sum(items)\n"
        "@@ -45,3 +52,8 @@ class OrderProcessor:\n"
        "+    pass\n"
    )
    symbols = extractor.extract_from_diff_text(diff_text, "services/orders.py")
    assert len(symbols) == 2
    assert symbols[0].name == "calculate_total"
    assert symbols[0].symbol_type == SymbolType.FUNCTION
    assert symbols[1].name == "OrderProcessor"
    assert symbols[1].symbol_type == SymbolType.CLASS


def test_extract_from_python_file(tmp_path: Path):
    extractor = SymbolExtractor()
    py_file = tmp_path / "sample.py"
    py_file.write_text(
        "def helper():\n"
        "    return 42\n\n"
        "class Calculator:\n"
        "    def add(self, a, b):\n"
        "        return a + b\n",
        encoding="utf-8"
    )

    # If changed_lines touches line 2 (inside helper)
    symbols = extractor.extract_from_python_file(py_file, "sample.py", {2})
    names = [s.name for s in symbols]
    assert "helper" in names
    assert "Calculator" not in names

    # If changed_lines touches line 5 (inside Calculator)
    symbols = extractor.extract_from_python_file(py_file, "sample.py", {5})
    names = [s.name for s in symbols]
    assert "Calculator" in names
    assert "helper" not in names


def test_parse_changed_line_numbers():
    extractor = SymbolExtractor()
    patch = (
        "@@ -10,3 +10,4 @@\n"
        " line1\n"
        "+line2\n"
        "-line3\n"
        " line4\n"
    )
    lines = extractor.parse_changed_line_numbers(patch)
    assert 11 in lines or 10 in lines
