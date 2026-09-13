"""Integration tests for AgentProof V3 drift and missing work verification workflows."""

import json
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def git_v3_repo(tmp_path: Path) -> Path:
    """Fixture to create and initialize a clean Git repository with basic config."""
    repo_dir = tmp_path / "v3_test_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "V3 User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "v3@example.com"], cwd=repo_dir, check=True, capture_output=True)

    # Initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# V3 Test Repo\n", encoding="utf-8")
    pyproject = repo_dir / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\npythonpath = ['src']\n", encoding="utf-8")
    src = repo_dir / "src"
    src.mkdir()
    (src / "math_lib.py").write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
    tests = repo_dir / "tests"
    tests.mkdir()
    (tests / "test_math.py").write_text("from math_lib import add\ndef test_add(): assert add(1, 2) == 3\n", encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    return repo_dir


def test_v3_aligned_task_drift_none(git_v3_repo: Path):
    # Modify math_lib
    (git_v3_repo / "src" / "math_lib.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef multiply(a, b):\n    return a * b\n",
        encoding="utf-8"
    )
    (git_v3_repo / "tests" / "test_math.py").write_text(
        "from math_lib import add, multiply\ndef test_add(): assert add(1, 2) == 3\ndef test_mul(): assert multiply(2, 3) == 6\n",
        encoding="utf-8"
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v3_repo),
        "--task", "Add multiply function to math_lib",
        "--no-color",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    output = proc.stdout

    # Verify all 8 sections in terminal output
    assert "1. CHANGE (Repository Facts)" in output
    assert "2. IMPACT (Change Impact Analysis)" in output
    assert "3. DRIFT (Task-to-Change Drift Analysis)" in output
    assert "4. MISSING WORK (Omission & Gap Detection)" in output
    assert "5. CHECKS (Validation Execution)" in output
    assert "6. RISKS & FINDINGS" in output
    assert "7. EVIDENCE (Facts & Provenance)" in output
    assert "FINAL VERDICT:" in output

    assert "[NONE]" in output


def test_v3_unrelated_task_drift_high(git_v3_repo: Path):
    # Modify math_lib when task is about authentication
    (git_v3_repo / "src" / "math_lib.py").write_text(
        "def add(a, b):\n    return a + b\n\ndef power(a, b):\n    return a ** b\n",
        encoding="utf-8"
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v3_repo),
        "--task", "Fix authentication token expiration",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(proc.stdout)

    assert data["schema_version"] == "1.2.0"
    drift = data["drift"]
    assert drift["drift_level"] in ("MEDIUM", "HIGH")
    assert any("math_lib.py" in f for f in drift["unexpected_files"])


def test_v3_task_file_input(git_v3_repo: Path, tmp_path: Path):
    task_file = tmp_path / "task.txt"
    task_file.write_text("Update math_lib calculation logic\n", encoding="utf-8")

    (git_v3_repo / "src" / "math_lib.py").write_text(
        "def add(a, b):\n    return a + b + 0\n",
        encoding="utf-8"
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v3_repo),
        "--task-file", str(task_file),
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(proc.stdout)
    assert data["task_context"]["raw_text"] == "Update math_lib calculation logic"
    assert data["drift"]["drift_level"] == "NONE"


def test_v3_missing_database_migration_integration(git_v3_repo: Path):
    # Add a model without migration
    models_dir = git_v3_repo / "src" / "models"
    models_dir.mkdir()
    (models_dir / "account.py").write_text("class Account:\n    Table('accounts')\n", encoding="utf-8")

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v3_repo),
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(proc.stdout)

    missing = data["missing_work"]
    assert missing["findings_count"] >= 1
    codes = [f["code"] for f in missing["findings"]]
    assert "MISSING_DATABASE_MIGRATION" in codes
