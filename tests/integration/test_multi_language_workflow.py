"""Integration tests for AgentProof V6 Multi-Language Code Understanding and Agent Integration."""

import json
import os
import subprocess
import sys
from pathlib import Path
import pytest


@pytest.fixture
def git_v6_multi_repo(tmp_path: Path) -> Path:
    """Fixture to create and initialize a clean Git repository with Go, TypeScript, and Python code."""
    repo_dir = tmp_path / "v6_multi_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "V6 User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "v6@example.com"], cwd=repo_dir, check=True, capture_output=True)

    # Initial Go file
    pkg_dir = repo_dir / "pkg" / "auth"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "token.go").write_text(
        "package auth\n\n"
        "func GenerateToken(userID string) string {\n"
        "    return \"token-\" + userID\n"
        "}\n",
        encoding="utf-8",
    )

    # Initial TypeScript file
    ts_dir = repo_dir / "src" / "api"
    ts_dir.mkdir(parents=True)
    (ts_dir / "client.ts").write_text(
        "export interface User {\n"
        "    id: string;\n"
        "    name: string;\n"
        "}\n\n"
        "export function getUser(id: string): User {\n"
        "    return { id, name: 'User ' + id };\n"
        "}\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial multi-language commit"], cwd=repo_dir, check=True, capture_output=True)

    return repo_dir


def test_v6_multi_language_symbol_extraction(git_v6_multi_repo: Path):
    """Verify that multi-language changes extract Go and TypeScript symbols correctly."""
    # Modify Go file
    token_go = git_v6_multi_repo / "pkg" / "auth" / "token.go"
    token_go.write_text(
        "package auth\n\n"
        "func GenerateToken(userID string) string {\n"
        "    return \"token-\" + userID\n"
        "}\n\n"
        "func ValidateJWT(tokenStr string) bool {\n"
        "    return len(tokenStr) > 10\n"
        "}\n",
        encoding="utf-8",
    )

    # Modify TypeScript file
    client_ts = git_v6_multi_repo / "src" / "api" / "client.ts"
    client_ts.write_text(
        "export interface User {\n"
        "    id: string;\n"
        "    name: string;\n"
        "}\n\n"
        "export function getUser(id: string): User {\n"
        "    return { id, name: 'User ' + id };\n"
        "}\n\n"
        "export function updateSession(sessionToken: string): boolean {\n"
        "    return sessionToken.length > 0;\n"
        "}\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v6_multi_repo),
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)

    files = data["change_summary"]["files"]
    file_map = {f["path"]: f for f in files}

    # Verify Go symbol extraction
    go_path = "pkg/auth/token.go"
    assert go_path in file_map
    assert file_map[go_path]["language"] == "go"
    assert file_map[go_path]["analysis_level"] in ("FULL_SEMANTIC", "STRUCTURAL_AST", "BASIC_HEURISTIC")
    go_symbols = [s["name"] for s in file_map[go_path]["changed_symbols"]]
    assert "ValidateJWT" in go_symbols

    # Verify TypeScript symbol extraction
    ts_path = "src/api/client.ts"
    assert ts_path in file_map
    assert file_map[ts_path]["language"] == "typescript"
    assert file_map[ts_path]["analysis_level"] in ("FULL_SEMANTIC", "STRUCTURAL_AST", "BASIC_HEURISTIC")
    ts_symbols = [s["name"] for s in file_map[ts_path]["changed_symbols"]]
    assert "updateSession" in ts_symbols


def test_v6_agent_mode_markdown_and_json(git_v6_multi_repo: Path):
    """Verify CLI --agent format in both markdown (default) and --json."""
    # Modify Go file
    token_go = git_v6_multi_repo / "pkg" / "auth" / "token.go"
    token_go.write_text(
        "package auth\n\n"
        "func ValidateJWT(tokenStr string) bool {\n"
        "    return len(tokenStr) > 10\n"
        "}\n",
        encoding="utf-8",
    )

    # 1. Test markdown output with --agent
    cmd_md = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v6_multi_repo),
        "--agent",
    ]
    proc_md = subprocess.run(cmd_md, capture_output=True, text=True)
    # INCONCLUSIVE with missing security tests correctly requires action (exit code 1)
    assert proc_md.returncode == 1
    assert "# AgentProof Verification: INCONCLUSIVE" in proc_md.stdout
    assert "**Status**: ACTION REQUIRED" in proc_md.stdout
    assert "## Blockers to Fix" in proc_md.stdout

    # 2. Test json output with --agent --json
    cmd_json = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v6_multi_repo),
        "--agent",
        "--json",
    ]
    proc_json = subprocess.run(cmd_json, capture_output=True, text=True)
    assert proc_json.returncode == 1
    feedback_dict = json.loads(proc_json.stdout)
    assert feedback_dict["verdict"] == "INCONCLUSIVE"
    assert feedback_dict["is_verified"] is False
    assert len(feedback_dict["blockers"]) > 0


def test_v6_agent_input_context_ingestion(git_v6_multi_repo: Path, tmp_path: Path):
    """Verify context ingestion via --agent-input JSON file."""
    # Write agent input JSON
    agent_input_path = tmp_path / "agent_context.json"
    agent_input_path.write_text(
        json.dumps({
            "agent": "claude-code",
            "model": "claude-3-7-sonnet",
            "task": "Add ValidateJWT function to pkg/auth/token.go",
            "intended_files": ["pkg/auth/token.go"],
        }),
        encoding="utf-8",
    )

    # Modify Go file
    token_go = git_v6_multi_repo / "pkg" / "auth" / "token.go"
    token_go.write_text(
        "package auth\n\n"
        "func ValidateJWT(tokenStr string) bool {\n"
        "    return len(tokenStr) > 10\n"
        "}\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable, "-m", "agentproof.cli.main", "verify",
        "-d", str(git_v6_multi_repo),
        "--agent-input", str(agent_input_path),
        "--json",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    assert proc.returncode == 0
    data = json.loads(proc.stdout)

    assert data["task_context"] is not None
    assert "ValidateJWT" in data["task_context"]["raw_text"]
    assert "pkg/auth/token.go" in data["task_context"]["referenced_paths"]
