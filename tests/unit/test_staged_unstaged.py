"""Unit tests for staged vs unstaged Git analysis."""

import subprocess
from pathlib import Path
from agentproof.core.models import FileStatus
from agentproof.git.repo import GitRepo


def test_staged_vs_unstaged_inspection(tmp_path: Path):
    repo_dir = tmp_path / "staged_test_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)

    # Initial commit
    (repo_dir / "base.txt").write_text("initial\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True, capture_output=True)

    # Create one staged file
    staged_file = repo_dir / "staged.txt"
    staged_file.write_text("staged content\n", encoding="utf-8")
    subprocess.run(["git", "add", "staged.txt"], cwd=repo_dir, check=True, capture_output=True)

    # Create one unstaged file
    unstaged_file = repo_dir / "unstaged.txt"
    unstaged_file.write_text("unstaged content\n", encoding="utf-8")

    repo = GitRepo(repo_dir)
    details = repo.get_status_files_details()

    assert "staged.txt" in details
    assert "unstaged.txt" in details

    status_s, old_s, is_stg_s, is_uns_s = details["staged.txt"]
    assert status_s == FileStatus.ADDED
    assert is_stg_s is True
    assert is_uns_s is False

    status_u, old_u, is_stg_u, is_uns_u = details["unstaged.txt"]
    assert status_u == FileStatus.UNTRACKED
    assert is_stg_u is False
    assert is_uns_u is True

    # Summary inspection
    summary = repo.inspect_changes()
    assert summary.staged_files_count >= 1
    assert summary.unstaged_files_count >= 1


def test_rename_tracking(tmp_path: Path):
    repo_dir = tmp_path / "rename_repo"
    repo_dir.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir, check=True, capture_output=True)

    orig_file = repo_dir / "old_name.txt"
    orig_file.write_text("content to be renamed\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo_dir, check=True, capture_output=True)

    # Rename file via git
    subprocess.run(["git", "mv", "old_name.txt", "new_name.txt"], cwd=repo_dir, check=True, capture_output=True)

    repo = GitRepo(repo_dir)
    details = repo.get_status_files_details()

    assert "new_name.txt" in details
    status, old_path, is_staged, _ = details["new_name.txt"]
    assert status == FileStatus.RENAMED
    assert old_path == "old_name.txt"
    assert is_staged is True
