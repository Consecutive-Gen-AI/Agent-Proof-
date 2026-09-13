"""Git repository operations and change extraction."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from agentproof.core.models import ChangeSummary, FileChange, FileStatus


class GitError(Exception):
    """Raised when a Git command fails."""
    pass


class NotAGitRepositoryError(GitError):
    """Raised when target directory is not inside a Git repository."""
    pass


class GitRepo:
    """Provides safe, read-only inspection of a Git repository."""

    def __init__(self, target_dir: str | Path = ".") -> None:
        self.target_dir = Path(target_dir).resolve()
        self._git_bin = shutil.which("git")
        if not self._git_bin:
            raise GitError("git executable not found on system PATH.")
        self.root_dir = self._find_root()

    def _run_git(self, args: List[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        """Execute git command safely using argument vectors."""
        cmd = [self._git_bin] + args
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.root_dir if hasattr(self, "root_dir") else self.target_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=30,
            )
        except Exception as e:
            raise GitError(f"Failed to execute git command {cmd}: {e}") from e

        if check and result.returncode != 0:
            stderr = result.stderr.strip()
            raise GitError(f"Git command failed ({result.returncode}): {stderr}")
        return result

    def _find_root(self) -> Path:
        """Find the top-level directory of the Git working tree."""
        proc = self._run_git(["rev-parse", "--show-toplevel"], check=False)
        if proc.returncode != 0:
            raise NotAGitRepositoryError(
                f"Directory '{self.target_dir}' is not inside a Git repository."
            )
        return Path(proc.stdout.strip()).resolve()

    def get_current_branch(self) -> Optional[str]:
        """Get the current branch name or None if detached."""
        proc = self._run_git(["rev-parse", "--abbrev-ref", "HEAD"], check=False)
        if proc.returncode == 0:
            branch = proc.stdout.strip()
            return branch if branch != "HEAD" else None
        return None

    def get_head_commit(self) -> Optional[str]:
        """Get the full SHA of HEAD, or None if repo has no commits."""
        proc = self._run_git(["rev-parse", "HEAD"], check=False)
        if proc.returncode == 0:
            return proc.stdout.strip()
        return None

    def has_commits(self) -> bool:
        """Check if repository has at least one commit."""
        return self.get_head_commit() is not None

    def _count_file_lines(self, rel_path: str) -> int:
        """Safely count lines in a file, capped to avoid reading huge binaries."""
        full_path = self.root_dir / rel_path
        if not full_path.is_file():
            return 0
        try:
            # Skip files larger than 5MB
            if full_path.stat().st_size > 5 * 1024 * 1024:
                return 0
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def get_status_files(self) -> Dict[str, FileStatus]:
        """
        Parse git status --porcelain=v1 -u to find all altered or untracked files.
        Returns a mapping of normalized relative path -> FileStatus.
        """
        proc = self._run_git(["status", "--porcelain=v1", "-u"], check=True)
        files: Dict[str, FileStatus] = {}

        for line in proc.stdout.splitlines():
            if len(line) < 4:
                continue
            index_status = line[0]
            worktree_status = line[1]
            path_part = line[3:].strip()

            # Handle renames: "orig -> new"
            if " -> " in path_part:
                path_part = path_part.split(" -> ")[1].strip()

            # Strip surrounding quotes if git quoted non-ascii or spaces
            if path_part.startswith('"') and path_part.endswith('"'):
                path_part = path_part[1:-1]

            norm_path = path_part.replace("\\", "/")

            if index_status == "?" and worktree_status == "?":
                files[norm_path] = FileStatus.UNTRACKED
            elif index_status == "A" or worktree_status == "A":
                files[norm_path] = FileStatus.ADDED
            elif index_status == "D" or worktree_status == "D":
                files[norm_path] = FileStatus.DELETED
            elif index_status == "R" or worktree_status == "R":
                files[norm_path] = FileStatus.RENAMED
            else:
                files[norm_path] = FileStatus.MODIFIED

        return files

    def get_numstat(self, staged_only: bool = False) -> Dict[str, Tuple[int, int]]:
        """
        Extract added and deleted line counts per file using numstat.
        Returns mapping of relative path -> (additions, deletions).
        """
        numstat: Dict[str, Tuple[int, int]] = {}
        if not self.has_commits():
            # If no commits yet, numstat vs HEAD doesn't work.
            # Staged files can be queried vs empty tree if indexed
            if staged_only:
                # 4b825dc642cb6eb9a060e54bf8d69288fbee4904 is the empty tree SHA in git
                args = ["diff", "--cached", "--numstat", "4b825dc642cb6eb9a060e54bf8d69288fbee4904"]
                proc = self._run_git(args, check=False)
                if proc.returncode == 0:
                    self._parse_numstat_output(proc.stdout, numstat)
            return numstat

        if staged_only:
            args = ["diff", "--cached", "--numstat"]
        else:
            args = ["diff", "HEAD", "--numstat"]

        proc = self._run_git(args, check=False)
        if proc.returncode == 0:
            self._parse_numstat_output(proc.stdout, numstat)
        return numstat

    def _parse_numstat_output(self, output: str, result_dict: Dict[str, Tuple[int, int]]) -> None:
        """Helper to parse git diff --numstat lines."""
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                added_str, deleted_str, path_part = parts[0], parts[1], parts[2]
                if " -> " in path_part:
                    path_part = path_part.split(" -> ")[1].strip()
                norm_path = path_part.strip('"').replace("\\", "/")

                # Handle binary files which report '-'
                added = int(added_str) if added_str.isdigit() else 0
                deleted = int(deleted_str) if deleted_str.isdigit() else 0
                result_dict[norm_path] = (added, deleted)

    def get_file_diff_snippet(self, rel_path: str, staged_only: bool = False, max_lines: int = 40) -> Optional[str]:
        """Fetch a truncated patch snippet for a specific file."""
        if not self.has_commits():
            return None
        args = ["diff"]
        if staged_only:
            args.append("--cached")
        else:
            args.append("HEAD")
        args.extend(["--", rel_path])

        proc = self._run_git(args, check=False)
        if proc.returncode == 0 and proc.stdout.strip():
            lines = proc.stdout.splitlines()
            if len(lines) > max_lines:
                return "\n".join(lines[:max_lines]) + f"\n... [{len(lines) - max_lines} more lines truncated]"
            return "\n".join(lines)
        return None

    def inspect_changes(self, staged_only: bool = False) -> ChangeSummary:
        """
        Perform complete change inspection of working tree / staged changes.
        Returns a ChangeSummary populated with all FileChange entries.
        """
        status_map = self.get_status_files()
        numstat_map = self.get_numstat(staged_only=staged_only)

        files_list: List[FileChange] = []
        total_adds = 0
        total_dels = 0
        file_types: Dict[str, int] = {}

        for path, status in sorted(status_map.items()):
            adds, dels = numstat_map.get(path, (0, 0))

            # If untracked file, count lines directly
            if status == FileStatus.UNTRACKED:
                if staged_only:
                    continue  # Untracked files are not staged
                adds = self._count_file_lines(path)
                dels = 0

            total_adds += adds
            total_dels += dels

            # Track file extension
            ext = os.path.splitext(path)[1].lower() or "(no extension)"
            file_types[ext] = file_types.get(ext, 0) + 1

            snippet = self.get_file_diff_snippet(path, staged_only=staged_only)

            file_change = FileChange(
                path=path,
                status=status,
                additions=adds,
                deletions=dels,
                patch_snippet=snippet,
            )
            files_list.append(file_change)

        return ChangeSummary(
            total_files=len(files_list),
            total_additions=total_adds,
            total_deletions=total_dels,
            file_types=file_types,
            categories_count={},
            files=files_list,
        )
