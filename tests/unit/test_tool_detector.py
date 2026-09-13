"""Unit tests for tool detector."""

import json
from pathlib import Path
from agentproof.core.models import CheckCategory
from agentproof.detector.tools import ToolDetector


def test_detect_python_project(tmp_path: Path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    detector = ToolDetector(tmp_path)
    checks = detector.detect_checks()

    # Should detect python test runner
    test_checks = [c for c in checks if c.category == CheckCategory.TEST]
    assert len(test_checks) >= 1
    assert test_checks[0].name in ("pytest", "unittest")


def test_detect_node_project(tmp_path: Path):
    pkg_json = tmp_path / "package.json"
    pkg_json.write_text(
        json.dumps({
            "name": "sample-node-app",
            "scripts": {
                "test": "jest",
                "lint": "eslint ."
            }
        }),
        encoding="utf-8"
    )

    detector = ToolDetector(tmp_path)
    checks = detector.detect_checks()

    names = [c.name for c in checks]
    assert "npm-test" in names
    assert "npm-lint" in names


def test_empty_dir_detects_nothing(tmp_path: Path):
    detector = ToolDetector(tmp_path)
    checks = detector.detect_checks()
    assert len(checks) == 0
