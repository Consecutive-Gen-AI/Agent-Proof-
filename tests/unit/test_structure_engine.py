"""Unit tests for the StructureEngine and ProjectStructure multi-language indexing."""

from pathlib import Path

from agentproof.structure.engine import StructureEngine
from agentproof.structure.models import SupportedLanguage


def test_engine_analyze_file_and_caching(tmp_path: Path):
    src = tmp_path / "math.py"
    src.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")

    engine = StructureEngine()
    fs1 = engine.analyze_file(src, "math.py")
    assert fs1.language == SupportedLanguage.PYTHON
    assert len(fs1.symbols) == 1
    assert fs1.symbols[0].name == "add"

    # Second call should hit the content-hash cache
    fs2 = engine.analyze_file(src, "math.py")
    assert fs2 is fs1


def test_engine_overlapping_symbols(tmp_path: Path):
    src = tmp_path / "service.go"
    src.write_text(
        "package service\n"
        "\n"
        "func Start() error {\n"
        "    return nil\n"
        "}\n"
        "\n"
        "func Stop() error {\n"
        "    return nil\n"
        "}\n",
        encoding="utf-8",
    )

    engine = StructureEngine()
    # Changed line 3 is inside Start()
    start_syms = engine.get_overlapping_symbols(src, "service.go", {3})
    assert len(start_syms) == 1
    assert start_syms[0].name == "Start"

    # Changed line 8 is inside Stop()
    stop_syms = engine.get_overlapping_symbols(src, "service.go", {8})
    assert len(stop_syms) == 1
    assert stop_syms[0].name == "Stop"


def test_engine_project_structure_cross_file_relationships(tmp_path: Path):
    # Setup a small multi-language repository
    pkg_dir = tmp_path / "src"
    pkg_dir.mkdir()

    calc_ts = pkg_dir / "calculator.ts"
    calc_ts.write_text(
        "export function multiply(x: number, y: number): number {\n"
        "    return x * y;\n"
        "}\n",
        encoding="utf-8",
    )

    app_ts = pkg_dir / "app.ts"
    app_ts.write_text(
        "import { multiply } from './calculator';\n"
        "\n"
        "function run() {\n"
        "    return multiply(2, 3);\n"
        "}\n",
        encoding="utf-8",
    )

    engine = StructureEngine()
    project = engine.analyze_project(tmp_path)

    assert "src/calculator.ts" in project.files or "src\\calculator.ts" in project.files
    mult_syms = project.get_symbols_by_name("multiply")
    assert len(mult_syms) >= 1
    assert mult_syms[0].name == "multiply"

    # Verify caller discovery
    callers = project.find_callers_of("multiply")
    assert len(callers) >= 1
    assert any("app.ts" in c[0] for c in callers)
