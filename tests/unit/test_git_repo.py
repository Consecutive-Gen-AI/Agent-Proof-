"""Unit tests for Git repository operations."""

import pytest
from pathlib import Path
from agentproof.core.models import FileStatus
from agentproof.git.repo import GitRepo, NotAGitRepositoryError


def test_not_a_git_repo_raises_error(tmp_path: Path):
    non_git_dir = tmp_path / "empty_dir"
    non_git_dir.mkdir()
    with pytest.raises(NotAGitRepositoryError):
        GitRepo(non_git_dir)


def test_parse_numstat_output():
    # Instantiate with current workspace which is a git repo
    repo = GitRepo(".")
    res = {}
    sample_output = (
        "10\t2\tsrc/main.py\n"
        "-\t-\tassets/image.png\n"
        "5\t0\t\"path with spaces/file.txt\"\n"
        "1\t1\told_name.py -> new_name.py\n"
    )
    repo._parse_numstat_output(sample_output, res)
    assert res["src/main.py"] == (10, 2)
    assert res["assets/image.png"] == (0, 0)
    assert res["path with spaces/file.txt"] == (5, 0)
    assert res["new_name.py"] == (1, 1)


def test_git_repo_current_directory():
    repo = GitRepo(".")
    assert repo.root_dir.is_dir()
    branch = repo.get_current_branch()
    assert branch in ("main", "master") or branch is None
