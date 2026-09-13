"""Domain models and data structures for AgentProof verification."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class CheckStatus(str, Enum):
    """Execution status of a verification check."""
    PASS = "PASS"
    FAIL = "FAIL"
    SKIPPED = "SKIPPED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class CheckCategory(str, Enum):
    """Category of verification tool/check."""
    TEST = "TEST"
    LINT = "LINT"
    TYPECHECK = "TYPECHECK"
    BUILD = "BUILD"
    SECURITY = "SECURITY"


class FileStatus(str, Enum):
    """Git status of a changed file."""
    ADDED = "ADDED"
    MODIFIED = "MODIFIED"
    DELETED = "DELETED"
    RENAMED = "RENAMED"
    UNTRACKED = "UNTRACKED"


class FileCategory(str, Enum):
    """Semantic category of a changed file."""
    SOURCE = "SOURCE"
    TEST = "TEST"
    DEPENDENCY = "DEPENDENCY"
    CONFIGURATION = "CONFIGURATION"
    DOCUMENTATION = "DOCUMENTATION"
    SECURITY_SENSITIVE = "SECURITY_SENSITIVE"
    OTHER = "OTHER"


class RiskSeverity(str, Enum):
    """Severity of a detected verification risk or warning."""
    INFO = "INFO"
    WARNING = "WARNING"
    HIGH = "HIGH"


class Verdict(str, Enum):
    """Overall verification verdict."""
    VERIFIED = "VERIFIED"
    VERIFIED_WITH_WARNINGS = "VERIFIED_WITH_WARNINGS"
    FAILED = "FAILED"
    ERROR = "ERROR"
    INCONCLUSIVE = "INCONCLUSIVE"


@dataclass
class FileChange:
    """Represents a single file change in the repository."""
    path: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    category: FileCategory = FileCategory.OTHER
    patch_snippet: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status.value,
            "additions": self.additions,
            "deletions": self.deletions,
            "category": self.category.value,
            "patch_snippet": self.patch_snippet,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileChange:
        return cls(
            path=data["path"],
            status=FileStatus(data["status"]),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
            category=FileCategory(data.get("category", FileCategory.OTHER.value)),
            patch_snippet=data.get("patch_snippet"),
        )


@dataclass
class ChangeSummary:
    """Aggregated statistics of changes in the working tree / commit."""
    total_files: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    file_types: Dict[str, int] = field(default_factory=dict)
    categories_count: Dict[str, int] = field(default_factory=dict)
    files: List[FileChange] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "file_types": self.file_types,
            "categories_count": self.categories_count,
            "files": [f.to_dict() for f in self.files],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChangeSummary:
        return cls(
            total_files=data.get("total_files", 0),
            total_additions=data.get("total_additions", 0),
            total_deletions=data.get("total_deletions", 0),
            file_types=data.get("file_types", {}),
            categories_count=data.get("categories_count", {}),
            files=[FileChange.from_dict(f) for f in data.get("files", [])],
        )


@dataclass
class CheckResult:
    """Result of an individual verification check."""
    name: str
    category: CheckCategory
    command: List[str]
    status: CheckStatus
    exit_code: Optional[int]
    duration_ms: int
    stdout: str = ""
    stderr: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category.value,
            "command": self.command,
            "status": self.status.value,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CheckResult:
        return cls(
            name=data["name"],
            category=CheckCategory(data["category"]),
            command=data.get("command", []),
            status=CheckStatus(data["status"]),
            exit_code=data.get("exit_code"),
            duration_ms=data.get("duration_ms", 0),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            timestamp=data.get("timestamp", ""),
        )


@dataclass
class RiskWarning:
    """Warning or risk signal detected during change analysis."""
    code: str
    severity: RiskSeverity
    message: str
    related_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "related_files": self.related_files,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RiskWarning:
        return cls(
            code=data["code"],
            severity=RiskSeverity(data["severity"]),
            message=data["message"],
            related_files=data.get("related_files", []),
        )


@dataclass
class VerificationReport:
    """Complete, structured verification report for a software change."""
    schema_version: str = "1.0.0"
    target_dir: str = ""
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    change_summary: ChangeSummary = field(default_factory=ChangeSummary)
    checks: List[CheckResult] = field(default_factory=list)
    warnings: List[RiskWarning] = field(default_factory=list)
    verdict: Verdict = Verdict.INCONCLUSIVE
    reasoning: str = ""
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "target_dir": self.target_dir,
            "git_branch": self.git_branch,
            "git_commit": self.git_commit,
            "timestamp": self.timestamp,
            "verdict": self.verdict.value,
            "reasoning": self.reasoning,
            "change_summary": self.change_summary.to_dict(),
            "checks": [c.to_dict() for c in self.checks],
            "warnings": [w.to_dict() for w in self.warnings],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerificationReport:
        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            target_dir=data.get("target_dir", ""),
            git_branch=data.get("git_branch"),
            git_commit=data.get("git_commit"),
            timestamp=data.get("timestamp", ""),
            verdict=Verdict(data.get("verdict", Verdict.INCONCLUSIVE.value)),
            reasoning=data.get("reasoning", ""),
            change_summary=ChangeSummary.from_dict(data.get("change_summary", {})),
            checks=[CheckResult.from_dict(c) for c in data.get("checks", [])],
            warnings=[RiskWarning.from_dict(w) for w in data.get("warnings", [])],
        )
