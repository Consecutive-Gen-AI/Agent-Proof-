"""Deterministic detection of repository validation tools (tests, lint, typecheck)."""

from __future__ import annotations

import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from agentproof.core.models import CheckCategory


@dataclass
class CheckDefinition:
    """Represents a discovered validation tool check."""
    name: str
    category: CheckCategory
    command: List[str]
    is_available: bool = True
    reason_if_unavailable: Optional[str] = None


class ToolDetector:
    """Discovers tests, linters, and type-checkers appropriate for the repository."""

    def __init__(self, root_dir: str | Path) -> None:
        self.root_dir = Path(root_dir).resolve()

    def _has_file(self, rel_path: str) -> bool:
        return (self.root_dir / rel_path).is_file()

    def _has_dir(self, rel_path: str) -> bool:
        return (self.root_dir / rel_path).is_dir()

    def _which(self, cmd: str) -> Optional[str]:
        return shutil.which(cmd)

    def _has_python_module(self, module_name: str) -> bool:
        """Check if python module can be resolved in current interpreter."""
        try:
            import importlib.util
            return importlib.util.find_spec(module_name) is not None
        except Exception:
            return False

    def detect_checks(self) -> List[CheckDefinition]:
        """Detect all applicable checks for this repository."""
        checks: List[CheckDefinition] = []

        # 1. Python ecosystem
        checks.extend(self._detect_python_checks())

        # 2. Node / TypeScript ecosystem
        checks.extend(self._detect_node_checks())

        # 3. Rust ecosystem
        checks.extend(self._detect_rust_checks())

        # 4. Go ecosystem
        checks.extend(self._detect_go_checks())

        return checks

    def _detect_python_checks(self) -> List[CheckDefinition]:
        checks: List[CheckDefinition] = []
        is_python_repo = (
            self._has_file("pyproject.toml")
            or self._has_file("setup.py")
            or self._has_file("setup.cfg")
            or self._has_file("requirements.txt")
            or self._has_dir("tests")
        )
        if not is_python_repo:
            return checks

        py_exe = sys.executable

        # A. Python Tests
        has_tests_dir = self._has_dir("tests") or self._has_dir("test")
        has_pytest_config = False
        if self._has_file("pyproject.toml"):
            try:
                with open(self.root_dir / "pyproject.toml", "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "pytest" in content:
                        has_pytest_config = True
            except Exception:
                pass

        if has_tests_dir or has_pytest_config:
            # Check for pytest first
            if self._has_python_module("pytest") or self._which("pytest"):
                checks.append(
                    CheckDefinition(
                        name="pytest",
                        category=CheckCategory.TEST,
                        command=[py_exe, "-m", "pytest", "-q"],
                        is_available=True,
                    )
                )
            elif has_tests_dir:
                # Fallback to standard library unittest
                checks.append(
                    CheckDefinition(
                        name="unittest",
                        category=CheckCategory.TEST,
                        command=[py_exe, "-m", "unittest", "discover", "-s", "tests" if self._has_dir("tests") else "test"],
                        is_available=True,
                    )
                )
            else:
                checks.append(
                    CheckDefinition(
                        name="pytest",
                        category=CheckCategory.TEST,
                        command=[],
                        is_available=False,
                        reason_if_unavailable="pytest is configured in pyproject.toml but not installed in environment.",
                    )
                )

        # B. Python Linters
        if self._which("ruff") or self._has_python_module("ruff"):
            checks.append(
                CheckDefinition(
                    name="ruff",
                    category=CheckCategory.LINT,
                    command=[py_exe, "-m", "ruff", "check", "."],
                    is_available=True,
                )
            )
        elif self._which("flake8") or self._has_python_module("flake8"):
            if self._has_file(".flake8") or self._has_file("setup.cfg"):
                checks.append(
                    CheckDefinition(
                        name="flake8",
                        category=CheckCategory.LINT,
                        command=[py_exe, "-m", "flake8"],
                        is_available=True,
                    )
                )

        # C. Python Type Checker
        if self._has_file("mypy.ini") or (self._has_file("pyproject.toml") and "tool.mypy" in (self.root_dir / "pyproject.toml").read_text(encoding="utf-8", errors="ignore")):
            if self._which("mypy") or self._has_python_module("mypy"):
                target = "src" if self._has_dir("src") else "."
                checks.append(
                    CheckDefinition(
                        name="mypy",
                        category=CheckCategory.TYPECHECK,
                        command=[py_exe, "-m", "mypy", target],
                        is_available=True,
                    )
                )
            else:
                checks.append(
                    CheckDefinition(
                        name="mypy",
                        category=CheckCategory.TYPECHECK,
                        command=[],
                        is_available=False,
                        reason_if_unavailable="mypy configuration found but mypy is not installed.",
                    )
                )

        return checks

    def _detect_node_checks(self) -> List[CheckDefinition]:
        checks: List[CheckDefinition] = []
        pkg_json = self.root_dir / "package.json"
        if not pkg_json.is_file():
            return checks

        npm_bin = self._which("npm")
        scripts: dict = {}
        try:
            with open(pkg_json, "r", encoding="utf-8") as f:
                data = json.load(f)
                scripts = data.get("scripts", {})
        except Exception:
            return checks

        # Tests
        if "test" in scripts and "no test specified" not in scripts["test"].lower():
            if npm_bin:
                checks.append(
                    CheckDefinition(
                        name="npm-test",
                        category=CheckCategory.TEST,
                        command=[npm_bin, "test"],
                        is_available=True,
                    )
                )
            else:
                checks.append(
                    CheckDefinition(
                        name="npm-test",
                        category=CheckCategory.TEST,
                        command=[],
                        is_available=False,
                        reason_if_unavailable="package.json contains test script but npm is not on PATH.",
                    )
                )

        # Lint
        if "lint" in scripts:
            if npm_bin:
                checks.append(
                    CheckDefinition(
                        name="npm-lint",
                        category=CheckCategory.LINT,
                        command=[npm_bin, "run", "lint"],
                        is_available=True,
                    )
                )

        # Typecheck
        if self._has_file("tsconfig.json"):
            npx_bin = self._which("npx")
            if npx_bin:
                checks.append(
                    CheckDefinition(
                        name="tsc",
                        category=CheckCategory.TYPECHECK,
                        command=[npx_bin, "tsc", "--noEmit"],
                        is_available=True,
                    )
                )

        return checks

    def _detect_rust_checks(self) -> List[CheckDefinition]:
        checks: List[CheckDefinition] = []
        if not self._has_file("Cargo.toml"):
            return checks

        cargo_bin = self._which("cargo")
        if cargo_bin:
            checks.append(
                CheckDefinition(
                    name="cargo-test",
                    category=CheckCategory.TEST,
                    command=[cargo_bin, "test"],
                    is_available=True,
                )
            )
            checks.append(
                CheckDefinition(
                    name="cargo-clippy",
                    category=CheckCategory.LINT,
                    command=[cargo_bin, "clippy", "--", "-D", "warnings"],
                    is_available=True,
                )
            )
        else:
            checks.append(
                CheckDefinition(
                    name="cargo-test",
                    category=CheckCategory.TEST,
                    command=[],
                    is_available=False,
                    reason_if_unavailable="Cargo.toml found but cargo is not on PATH.",
                )
            )
        return checks

    def _detect_go_checks(self) -> List[CheckDefinition]:
        checks: List[CheckDefinition] = []
        if not self._has_file("go.mod"):
            return checks

        go_bin = self._which("go")
        if go_bin:
            checks.append(
                CheckDefinition(
                    name="go-test",
                    category=CheckCategory.TEST,
                    command=[go_bin, "test", "./..."],
                    is_available=True,
                )
            )
            checks.append(
                CheckDefinition(
                    name="go-vet",
                    category=CheckCategory.LINT,
                    command=[go_bin, "vet", "./..."],
                    is_available=True,
                )
            )
        else:
            checks.append(
                CheckDefinition(
                    name="go-test",
                    category=CheckCategory.TEST,
                    command=[],
                    is_available=False,
                    reason_if_unavailable="go.mod found but go is not on PATH.",
                )
            )
        return checks
