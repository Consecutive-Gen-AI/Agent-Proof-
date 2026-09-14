"""Git repository operations and change extraction."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from agentproof.core.models import ChangeSummary, FileChange, FileStatus
from agentproof.git.symbols import SymbolExtractor


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
        self._symbol_extractor = SymbolExtractor()

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
            if full_path.stat().st_size > 5 * 1024 * 1024:
                return 0
            with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def get_status_files_details(self) -> Dict[str, Tuple[FileStatus, Optional[str], bool, bool]]:
        """
        Parse git status --porcelain=v1 -u.
        Returns mapping of:
          norm_path -> (FileStatus, old_path_if_renamed, is_staged, is_unstaged)
        """
        proc = self._run_git(["status", "--porcelain=v1", "-u"], check=True)
        files: Dict[str, Tuple[FileStatus, Optional[str], bool, bool]] = {}

        for line in proc.stdout.splitlines():
            if len(line) < 4:
                continue
            index_status = line[0]
            worktree_status = line[1]
            path_part = line[3:].strip()
            old_path: Optional[str] = None

            if " -> " in path_part:
                parts = path_part.split(" -> ")
                old_path = parts[0].strip('"').replace("\\", "/")
                path_part = parts[1].strip()

            if path_part.startswith('"') and path_part.endswith('"'):
                path_part = path_part[1:-1]

            norm_path = path_part.replace("\\", "/")

            is_staged = index_status not in (" ", "?")
            is_unstaged = worktree_status not in (" ", "?")

            if index_status == "?" and worktree_status == "?":
                status = FileStatus.UNTRACKED
                is_staged = False
                is_unstaged = True
            elif index_status == "A" or worktree_status == "A":
                status = FileStatus.ADDED
            elif index_status == "D" or worktree_status == "D":
                status = FileStatus.DELETED
            elif index_status == "R" or worktree_status == "R":
                status = FileStatus.RENAMED
            else:
                status = FileStatus.MODIFIED

            files[norm_path] = (status, old_path, is_staged, is_unstaged)

        return files

    def get_status_files(self) -> Dict[str, FileStatus]:
        """Backward-compatible mapping of path -> FileStatus."""
        details = self.get_status_files_details()
        return {p: status for p, (status, _, _, _) in details.items()}

    def get_numstat(self, staged_only: bool = False) -> Dict[str, Tuple[int, int]]:
        """Extract added and deleted line counts per file using numstat."""
        numstat: Dict[str, Tuple[int, int]] = {}
        if not self.has_commits():
            if staged_only:
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

    def get_staged_and_unstaged_numstat(self) -> Tuple[Dict[str, Tuple[int, int]], Dict[str, Tuple[int, int]]]:
        """Return separate (staged_numstat, unstaged_numstat) dictionaries."""
        staged_dict: Dict[str, Tuple[int, int]] = {}
        unstaged_dict: Dict[str, Tuple[int, int]] = {}

        if self.has_commits():
            p_staged = self._run_git(["diff", "--cached", "--numstat"], check=False)
            if p_staged.returncode == 0:
                self._parse_numstat_output(p_staged.stdout, staged_dict)

            p_unstaged = self._run_git(["diff", "--numstat"], check=False)
            if p_unstaged.returncode == 0:
                self._parse_numstat_output(p_unstaged.stdout, unstaged_dict)
        else:
            p_staged = self._run_git(["diff", "--cached", "--numstat", "4b825dc642cb6eb9a060e54bf8d69288fbee4904"], check=False)
            if p_staged.returncode == 0:
                self._parse_numstat_output(p_staged.stdout, staged_dict)

        return staged_dict, unstaged_dict

    def _parse_numstat_output(self, output: str, result_dict: Dict[str, Tuple[int, int]]) -> None:
        """Helper to parse git diff --numstat lines."""
        for line in output.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                added_str, deleted_str, path_part = parts[0], parts[1], parts[2]
                if " -> " in path_part:
                    path_part = path_part.split(" -> ")[1].strip()
                norm_path = path_part.strip('"').replace("\\", "/")

                added = int(added_str) if added_str.isdigit() else 0
                deleted = int(deleted_str) if deleted_str.isdigit() else 0
                result_dict[norm_path] = (added, deleted)

    def get_file_diff_snippet(self, rel_path: str, staged_only: bool = False, max_lines: int = 60) -> Optional[str]:
        """Fetch a patch snippet for a specific file."""
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
        Perform deep change inspection of working tree / staged changes,
        including staged vs unstaged metrics and changed symbols.
        """
        details_map = self.get_status_files_details()
        staged_numstat, unstaged_numstat = self.get_staged_and_unstaged_numstat()
        combined_numstat = self.get_numstat(staged_only=staged_only)

        files_list: List[FileChange] = []
        total_adds = 0
        total_dels = 0
        staged_files_count = 0
        unstaged_files_count = 0
        staged_adds = 0
        staged_dels = 0
        unstaged_adds = 0
        unstaged_dels = 0
        file_types: Dict[str, int] = {}

        for path, (status, old_path, is_staged, is_unstaged) in sorted(details_map.items()):
            if staged_only and not is_staged:
                continue

            s_adds, s_dels = staged_numstat.get(path, (0, 0))
            u_adds, u_dels = unstaged_numstat.get(path, (0, 0))

            if status == FileStatus.UNTRACKED:
                if staged_only:
                    continue
                adds = self._count_file_lines(path)
                dels = 0
                u_adds = adds
                u_dels = 0
            else:
                c_adds, c_dels = combined_numstat.get(path, (s_adds + u_adds, s_dels + u_dels))
                adds = c_adds
                dels = c_dels

            total_adds += adds
            total_dels += dels

            if is_staged:
                staged_files_count += 1
                staged_adds += s_adds
                staged_dels += s_dels

            if is_unstaged:
                unstaged_files_count += 1
                unstaged_adds += u_adds
                unstaged_dels += u_dels

            ext = os.path.splitext(path)[1].lower() or "(no extension)"
            file_types[ext] = file_types.get(ext, 0) + 1

            snippet = self.get_file_diff_snippet(path, staged_only=staged_only)

            # Extract changed symbols
            changed_symbols = []
            if snippet:
                changed_symbols.extend(self._symbol_extractor.extract_from_diff_text(snippet, path))

            # AST enrichment for supported source files (Python, JS, TS, Go, Rust, Java)
            file_lang = None
            analysis_level = None
            if status != FileStatus.DELETED:
                full_p = self.root_dir / path
                struct = self._symbol_extractor.engine.parse_file(full_p, path)
                if struct:
                    from agentproof.structure.models import SupportedLanguage
                    if struct.language != SupportedLanguage.UNSUPPORTED:
                        file_lang = struct.language.value
                    analysis_level = struct.analysis_level.value

                changed_lines = self._symbol_extractor.parse_changed_line_numbers(snippet or "") if snippet else set()
                ast_symbols = self._symbol_extractor.extract_from_source_file(full_p, path, changed_lines)
                # Combine unique symbol names
                existing_names = {s.name for s in changed_symbols}
                for sym in ast_symbols:
                    if sym.name not in existing_names:
                        changed_symbols.append(sym)
                        existing_names.add(sym.name)

            file_change = FileChange(
                path=path,
                status=status,
                additions=adds,
                deletions=dels,
                patch_snippet=snippet,
                old_path=old_path,
                is_staged=is_staged,
                is_unstaged=is_unstaged,
                staged_additions=s_adds,
                staged_deletions=s_dels,
                unstaged_additions=u_adds,
                unstaged_deletions=u_dels,
                changed_symbols=changed_symbols,
                language=file_lang,
                analysis_level=analysis_level,
            )
            files_list.append(file_change)

        return ChangeSummary(
            total_files=len(files_list),
            total_additions=total_adds,
            total_deletions=total_dels,
            staged_files_count=staged_files_count,
            unstaged_files_count=unstaged_files_count,
            staged_additions=staged_adds,
            staged_deletions=staged_dels,
            unstaged_additions=unstaged_adds,
            unstaged_deletions=unstaged_dels,
            file_types=file_types,
            categories_count={},
            files=files_list,
        )
