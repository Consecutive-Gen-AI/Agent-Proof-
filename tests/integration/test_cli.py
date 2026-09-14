"""Integration tests for the AgentProof CLI interface."""

import json
import subprocess
import sys
from pathlib import Path


from agentproof import __version__


def test_cli_version():
    cmd = [sys.executable, "-m", "agentproof.cli.main", "--version"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert f"agentproof {__version__}" in proc.stdout.strip()


def test_cli_help():
    cmd = [sys.executable, "-m", "agentproof.cli.main", "--help"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "AgentProof" in proc.stdout
    assert "verify" in proc.stdout


def test_cli_non_git_repo_terminal(tmp_path: Path):
    non_git = tmp_path / "not_git"
    non_git.mkdir()
    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(non_git)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 2
    assert "not inside a Git repository" in proc.stderr


def test_cli_non_git_repo_json(tmp_path: Path):
    non_git = tmp_path / "not_git"
    non_git.mkdir()
    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "-d", str(non_git), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    assert data["error"] == "NOT_A_GIT_REPOSITORY"


def test_cli_verify_help_shows_task_flags():
    cmd = [sys.executable, "-m", "agentproof.cli.main", "verify", "--help"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "--task" in proc.stdout
    assert "--task-file" in proc.stdout
    assert "--adversarial" in proc.stdout


def test_cli_inspect_help_and_subcommand():
    cmd = [sys.executable, "-m", "agentproof.cli.main", "inspect", "--help"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    assert "inspect" in proc.stdout.lower()

