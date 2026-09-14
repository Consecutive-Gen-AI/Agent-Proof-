"""Integration tests for AgentProof V5 Adversarial Verification workflows."""

import json
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def git_v5_repo(tmp_path: Path) -> Path:
    """Fixture to create and initialize a clean Git repository with basic config."""
    repo_dir = tmp_path / "v5_test_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "V5 User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "v5@example.com"], cwd=repo_dir, check=True, capture_output=True)

    # Initial commit
    readme = repo_dir / "README.md"
    readme.write_text("# V5 Test Repo\n", encoding="utf-8")
    pyproject = repo_dir / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\ntestpaths = ['tests']\npythonpath = ['src']\n", encoding="utf-8")
    src = repo_dir / "src"
    src.mkdir()
    (src / "calculator.py").write_text(
        "def safe_divide(a, b):\n"
        "    if b is None or b == 0:\n"
        "        raise ValueError('Cannot divide by zero or None')\n"
        "    return a / b\n",
        encoding="utf-8"
    )
    tests = repo_dir / "tests"
    tests.mkdir()
    (tests / "test_calc.py").write_text(
        "from calculator import safe_divide\n"
        "def test_calc(): assert safe_divide(10, 2) == 5\n",
        encoding="utf-8"
    )

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_dir, check=True, capture_output=True)

    return repo_dir


def test_adversarial_clean_execution_json(git_v5_repo: Path):
    # Modify calculator with robust input handling
    (git_v5_repo / "src" / "calculator.py").write_text(
        "def safe_divide(a, b):\n"
        "    if b is None or b == 0:\n"
        "        raise ValueError('Cannot divide by zero or None')\n"
        "    return a / b\n"
        "\ndef square(x):\n"
        "    if x is None:\n"
        "        raise TypeError('x cannot be None')\n"
        "    return x * x\n",
        encoding="utf-8"
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v5_repo),
        "--adversarial",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)

    assert data["schema_version"] == "1.3.0"
    assert "adversarial" in data
    adv = data["adversarial"]
    assert adv["cases_generated"] > 0
    assert adv["cases_passed"] > 0
    assert adv["cases_failed"] == 0
    assert data["verdict"] in ("VERIFIED", "VERIFIED_WITH_WARNINGS")


def test_adversarial_catches_flaw_and_blocks_verdict(git_v5_repo: Path):
    # Introduce a function that fails under boundary or None
    (git_v5_repo / "src" / "calculator.py").write_text(
        "def safe_divide(a, b):\n"
        "    return a / b\n"  # Removed zero/None check!
        "\ndef discount(price, rate):\n"
        "    # Author forgot to validate negative price\n"
        "    return price * (1 - rate)\n",
        encoding="utf-8"
    )

    # Unit tests might still pass for basic case 10/2:
    (git_v5_repo / "tests" / "test_calc.py").write_text(
        "from calculator import safe_divide, discount\n"
        "def test_calc():\n"
        "    assert safe_divide(10, 2) == 5\n"
        "    assert discount(100, 0.1) == 90\n",
        encoding="utf-8"
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v5_repo),
        "--adversarial",
        "--no-color",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    output = proc.stdout

    # Must be non-zero exit because verdict is BLOCKED
    assert proc.returncode == 1
    assert "ADVERSARIAL VERIFICATION" in output
    assert "FINAL VERDICT: BLOCKED" in output
    assert "Verification BLOCKED by" in output


def test_adversarial_passport_integration(git_v5_repo: Path):
    # Test passport with --adversarial
    (git_v5_repo / "src" / "calculator.py").write_text(
        "def safe_divide(a, b):\n"
        "    if b is None or b == 0: raise ValueError('Zero')\n"
        "    return a / b\n",
        encoding="utf-8"
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "passport",
        "-d", str(git_v5_repo),
        "--adversarial",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["metadata"]["schema_version"] == "1.0.0"
    assert data["verdict"]["status"] in ("VERIFIED", "VERIFIED_WITH_WARNINGS")
