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


class SymbolType(str, Enum):
    """Type of code symbol changed."""
    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"
    CONSTANT = "CONSTANT"
    VARIABLE = "VARIABLE"
    TYPE = "TYPE"


@dataclass
class SymbolChange:
    """Represents a code symbol (function, class, method) modified in a file."""
    name: str
    symbol_type: SymbolType = SymbolType.FUNCTION
    file_path: str = ""
    change_type: str = "MODIFIED"  # ADDED, MODIFIED, DELETED
    line_number: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "symbol_type": self.symbol_type.value,
            "file_path": self.file_path,
            "change_type": self.change_type,
            "line_number": self.line_number,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SymbolChange:
        return cls(
            name=data["name"],
            symbol_type=SymbolType(data.get("symbol_type", SymbolType.FUNCTION.value)),
            file_path=data.get("file_path", ""),
            change_type=data.get("change_type", "MODIFIED"),
            line_number=data.get("line_number"),
        )


@dataclass
class FileChange:
    """Represents a single file change in the repository."""
    path: str
    status: FileStatus
    additions: int = 0
    deletions: int = 0
    category: FileCategory = FileCategory.OTHER
    patch_snippet: Optional[str] = None
    old_path: Optional[str] = None  # For renamed files
    is_staged: bool = False
    is_unstaged: bool = False
    staged_additions: int = 0
    staged_deletions: int = 0
    unstaged_additions: int = 0
    unstaged_deletions: int = 0
    changed_symbols: List[SymbolChange] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status.value,
            "additions": self.additions,
            "deletions": self.deletions,
            "category": self.category.value,
            "patch_snippet": self.patch_snippet,
            "old_path": self.old_path,
            "is_staged": self.is_staged,
            "is_unstaged": self.is_unstaged,
            "staged_additions": self.staged_additions,
            "staged_deletions": self.staged_deletions,
            "unstaged_additions": self.unstaged_additions,
            "unstaged_deletions": self.unstaged_deletions,
            "changed_symbols": [s.to_dict() for s in self.changed_symbols],
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
            old_path=data.get("old_path"),
            is_staged=data.get("is_staged", False),
            is_unstaged=data.get("is_unstaged", False),
            staged_additions=data.get("staged_additions", 0),
            staged_deletions=data.get("staged_deletions", 0),
            unstaged_additions=data.get("unstaged_additions", 0),
            unstaged_deletions=data.get("unstaged_deletions", 0),
            changed_symbols=[SymbolChange.from_dict(s) for s in data.get("changed_symbols", [])],
        )


@dataclass
class ChangeSummary:
    """Aggregated statistics of changes in the working tree / commit."""
    total_files: int = 0
    total_additions: int = 0
    total_deletions: int = 0
    staged_files_count: int = 0
    unstaged_files_count: int = 0
    staged_additions: int = 0
    staged_deletions: int = 0
    unstaged_additions: int = 0
    unstaged_deletions: int = 0
    file_types: Dict[str, int] = field(default_factory=dict)
    categories_count: Dict[str, int] = field(default_factory=dict)
    files: List[FileChange] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_files": self.total_files,
            "total_additions": self.total_additions,
            "total_deletions": self.total_deletions,
            "staged_files_count": self.staged_files_count,
            "unstaged_files_count": self.unstaged_files_count,
            "staged_additions": self.staged_additions,
            "staged_deletions": self.staged_deletions,
            "unstaged_additions": self.unstaged_additions,
            "unstaged_deletions": self.unstaged_deletions,
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
            staged_files_count=data.get("staged_files_count", 0),
            unstaged_files_count=data.get("unstaged_files_count", 0),
            staged_additions=data.get("staged_additions", 0),
            staged_deletions=data.get("staged_deletions", 0),
            unstaged_additions=data.get("unstaged_additions", 0),
            unstaged_deletions=data.get("unstaged_deletions", 0),
            file_types=data.get("file_types", {}),
            categories_count=data.get("categories_count", {}),
            files=[FileChange.from_dict(f) for f in data.get("files", [])],
        )


class ImpactRelation(str, Enum):
    """Nature of relationship between changed file and impacted file."""
    DIRECT_IMPORT = "DIRECT_IMPORT"
    TEST_FOR_MODULE = "TEST_FOR_MODULE"
    CALLER = "CALLER"
    SHARED_DEPENDENCY = "SHARED_DEPENDENCY"
    CONFIGURATION = "CONFIGURATION"


@dataclass
class ImpactedComponent:
    """A file or component identified as potentially affected by changes."""
    file_path: str
    relation: ImpactRelation
    impacted_by: str  # Which changed file or symbol caused this impact
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "relation": self.relation.value,
            "impacted_by": self.impacted_by,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ImpactedComponent:
        return cls(
            file_path=data["file_path"],
            relation=ImpactRelation(data["relation"]),
            impacted_by=data.get("impacted_by", ""),
            description=data.get("description", ""),
        )


@dataclass
class ChangeImpact:
    """Results of deterministic change impact analysis."""
    changed_modules: List[str] = field(default_factory=list)
    impacted_source_files: List[ImpactedComponent] = field(default_factory=list)
    impacted_test_files: List[ImpactedComponent] = field(default_factory=list)
    impacted_configs: List[str] = field(default_factory=list)
    total_impact_score: str = "LOW"  # LOW, MEDIUM, HIGH
    untested_impacts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "changed_modules": self.changed_modules,
            "impacted_source_files": [i.to_dict() for i in self.impacted_source_files],
            "impacted_test_files": [i.to_dict() for i in self.impacted_test_files],
            "impacted_configs": self.impacted_configs,
            "total_impact_score": self.total_impact_score,
            "untested_impacts": self.untested_impacts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ChangeImpact:
        return cls(
            changed_modules=data.get("changed_modules", []),
            impacted_source_files=[ImpactedComponent.from_dict(i) for i in data.get("impacted_source_files", [])],
            impacted_test_files=[ImpactedComponent.from_dict(i) for i in data.get("impacted_test_files", [])],
            impacted_configs=data.get("impacted_configs", []),
            total_impact_score=data.get("total_impact_score", "LOW"),
            untested_impacts=data.get("untested_impacts", []),
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
    git_commit: Optional[str] = None
    output_summary: str = ""

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
            "git_commit": self.git_commit,
            "output_summary": self.output_summary,
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
            git_commit=data.get("git_commit"),
            output_summary=data.get("output_summary", ""),
        )


@dataclass
class RiskWarning:
    """Warning or risk signal detected during change analysis."""
    code: str
    severity: RiskSeverity
    message: str
    related_files: List[str] = field(default_factory=list)
    what_was_detected: str = ""
    why_it_matters: str = ""
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "related_files": self.related_files,
            "what_was_detected": self.what_was_detected or self.message,
            "why_it_matters": self.why_it_matters,
            "evidence": self.evidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> RiskWarning:
        return cls(
            code=data["code"],
            severity=RiskSeverity(data["severity"]),
            message=data["message"],
            related_files=data.get("related_files", []),
            what_was_detected=data.get("what_was_detected", data["message"]),
            why_it_matters=data.get("why_it_matters", ""),
            evidence=data.get("evidence", []),
        )


# Alias RiskFinding to RiskWarning for rich V2 finding capability
RiskFinding = RiskWarning


@dataclass
class VerificationReport:
    """Complete, structured verification report for a software change."""
    schema_version: str = "1.1.0"
    target_dir: str = ""
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    change_summary: ChangeSummary = field(default_factory=ChangeSummary)
    impact: Optional[ChangeImpact] = None
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
            "impact": self.impact.to_dict() if self.impact else None,
            "checks": [c.to_dict() for c in self.checks],
            "warnings": [w.to_dict() for w in self.warnings],
            "findings": [w.to_dict() for w in self.warnings],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerificationReport:
        impact_data = data.get("impact")
        return cls(
            schema_version=data.get("schema_version", "1.1.0"),
            target_dir=data.get("target_dir", ""),
            git_branch=data.get("git_branch"),
            git_commit=data.get("git_commit"),
            timestamp=data.get("timestamp", ""),
            verdict=Verdict(data.get("verdict", Verdict.INCONCLUSIVE.value)),
            reasoning=data.get("reasoning", ""),
            change_summary=ChangeSummary.from_dict(data.get("change_summary", {})),
            impact=ChangeImpact.from_dict(impact_data) if impact_data else None,
            checks=[CheckResult.from_dict(c) for c in data.get("checks", [])],
            warnings=[RiskWarning.from_dict(w) for w in data.get("warnings", data.get("findings", []))],
        )
