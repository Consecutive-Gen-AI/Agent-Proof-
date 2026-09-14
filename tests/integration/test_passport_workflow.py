"""Integration tests for AgentProof V4 CLI commands: passport and graph."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def git_v4_repo(tmp_path: Path) -> Path:
    """Create a temporary initialized git repository with committed files."""
    repo = tmp_path / "repo_v4"
    repo.mkdir()

    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)

    # Initial file
    (repo / "main.py").write_text("def hello():\n    return 'world'\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)

    return repo


def test_cli_passport_terminal(git_v4_repo: Path):
    # Make a change
    (git_v4_repo / "main.py").write_text("def hello():\n    return 'agentproof'\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "passport", "-d", str(git_v4_repo)]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0
    assert "AGENTPROOF PASSPORT" in proc.stdout
    assert "Repository:" in proc.stdout
    assert "CHANGE" in proc.stdout
    assert "1 files" in proc.stdout
    assert "VERDICT" in proc.stdout
    assert "traceable through the Proof Graph" in proc.stdout


def test_cli_passport_json(git_v4_repo: Path):
    (git_v4_repo / "main.py").write_text("def hello():\n    return 'json_passport'\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "passport", "-d", str(git_v4_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["metadata"]["schema_version"] == "1.0.0"
    assert data["passport_id"].startswith("pass-")
    assert data["change"]["files_count"] == 1
    assert "verdict" in data
    assert "status" in data["verdict"]
    assert len(data["metadata"]["passport_integrity_hash"]) == 64


def test_cli_passport_with_task_flag(git_v4_repo: Path):
    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "passport",
        "-d", str(git_v4_repo),
        "--task", "Update greeting return string",
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["task"] is not None
    assert "Update greeting return string" in data["task"]["description"]


def test_cli_graph_terminal(git_v4_repo: Path):
    (git_v4_repo / "main.py").write_text("def hello():\n    return 'graph_test'\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "graph", "-d", str(git_v4_repo)]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0
    assert "AGENTPROOF PROOF GRAPH" in proc.stdout
    assert "Nodes" in proc.stdout
    assert "Relationships" in proc.stdout
    assert "Verdict Traceability:" in proc.stdout
    assert "Graph Integrity:" in proc.stdout


def test_cli_graph_json(git_v4_repo: Path):
    (git_v4_repo / "main.py").write_text("def hello():\n    return 'graph_json'\n", encoding="utf-8")

    cmd = [sys.executable, "-m", "agentproof.cli.main", "graph", "-d", str(git_v4_repo), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 0
    data = json.loads(proc.stdout)
    assert data["schema_version"] == "1.0.0"
    assert data["node_count"] > 0
    assert data["edge_count"] > 0
    assert isinstance(data["nodes"], list)
    assert isinstance(data["edges"], list)


def test_cli_passport_non_git_repo(tmp_path: Path):
    non_git = tmp_path / "not_git_repo"
    non_git.mkdir()

    cmd = [sys.executable, "-m", "agentproof.cli.main", "passport", "-d", str(non_git)]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 2
    assert "not inside a Git repository" in proc.stderr


def test_cli_graph_non_git_repo_json(tmp_path: Path):
    non_git = tmp_path / "not_git_repo"
    non_git.mkdir()

    cmd = [sys.executable, "-m", "agentproof.cli.main", "graph", "-d", str(non_git), "--json"]
    proc = subprocess.run(cmd, capture_output=True, text=True)

    assert proc.returncode == 2
    data = json.loads(proc.stdout)
    assert data["error"] == "NOT_A_GIT_REPOSITORY"
