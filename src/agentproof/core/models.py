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
    BLOCKED = "BLOCKED"
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
    old_path: Optional[str] = None
    is_staged: bool = False
    is_unstaged: bool = False
    staged_additions: int = 0
    staged_deletions: int = 0
    unstaged_additions: int = 0
    unstaged_deletions: int = 0
    changed_symbols: List[SymbolChange] = field(default_factory=list)
    language: Optional[str] = None
    analysis_level: Optional[str] = None

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
            "language": self.language,
            "analysis_level": self.analysis_level,
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
            language=data.get("language"),
            analysis_level=data.get("analysis_level"),
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
    impacted_by: str
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
    total_impact_score: str = "LOW"
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


# =============================================================================
# V3: Task Context Models
# =============================================================================

@dataclass
class TaskContext:
    """Structured representation of intended task context."""
    raw_text: str
    normalized_keywords: List[str] = field(default_factory=list)
    referenced_paths: List[str] = field(default_factory=list)
    referenced_symbols: List[str] = field(default_factory=list)
    expected_domains: List[str] = field(default_factory=list)
    inferred_scope: str = "UNKNOWN"  # NARROW, BROAD, UNKNOWN
    confidence: str = "MEDIUM"  # LOW, MEDIUM, HIGH

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_text": self.raw_text,
            "normalized_keywords": self.normalized_keywords,
            "referenced_paths": self.referenced_paths,
            "referenced_symbols": self.referenced_symbols,
            "expected_domains": self.expected_domains,
            "inferred_scope": self.inferred_scope,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TaskContext:
        return cls(
            raw_text=data.get("raw_text", ""),
            normalized_keywords=data.get("normalized_keywords", []),
            referenced_paths=data.get("referenced_paths", []),
            referenced_symbols=data.get("referenced_symbols", []),
            expected_domains=data.get("expected_domains", []),
            inferred_scope=data.get("inferred_scope", "UNKNOWN"),
            confidence=data.get("confidence", "MEDIUM"),
        )


# =============================================================================
# V3: Agent Drift Models
# =============================================================================

class DriftLevel(str, Enum):
    """Level of scope drift detected between task and actual change."""
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


@dataclass
class DriftFinding:
    """Detailed drift finding for an unexpected file modification."""
    file_path: str
    drift_level: DriftLevel
    what_was_detected: str
    why_it_was_considered_drift: str
    supporting_evidence: List[str] = field(default_factory=list)
    severity: RiskSeverity = RiskSeverity.WARNING
    confidence: str = "HIGH"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "drift_level": self.drift_level.value,
            "what_was_detected": self.what_was_detected,
            "why_it_was_considered_drift": self.why_it_was_considered_drift,
            "supporting_evidence": self.supporting_evidence,
            "severity": self.severity.value,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DriftFinding:
        return cls(
            file_path=data["file_path"],
            drift_level=DriftLevel(data.get("drift_level", DriftLevel.LOW.value)),
            what_was_detected=data.get("what_was_detected", ""),
            why_it_was_considered_drift=data.get("why_it_was_considered_drift", ""),
            supporting_evidence=data.get("supporting_evidence", []),
            severity=RiskSeverity(data.get("severity", RiskSeverity.WARNING.value)),
            confidence=data.get("confidence", "HIGH"),
        )


@dataclass
class DriftReport:
    """Aggregated report of scope drift analysis."""
    task_context: Optional[TaskContext] = None
    drift_level: DriftLevel = DriftLevel.NONE
    confidence: str = "HIGH"
    aligned_files: List[str] = field(default_factory=list)
    unexpected_files: List[str] = field(default_factory=list)
    findings: List[DriftFinding] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_context": self.task_context.to_dict() if self.task_context else None,
            "drift_level": self.drift_level.value,
            "confidence": self.confidence,
            "aligned_files": self.aligned_files,
            "unexpected_files": self.unexpected_files,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> DriftReport:
        task_data = data.get("task_context")
        return cls(
            task_context=TaskContext.from_dict(task_data) if task_data else None,
            drift_level=DriftLevel(data.get("drift_level", DriftLevel.NONE.value)),
            confidence=data.get("confidence", "HIGH"),
            aligned_files=data.get("aligned_files", []),
            unexpected_files=data.get("unexpected_files", []),
            findings=[DriftFinding.from_dict(f) for f in data.get("findings", [])],
            summary=data.get("summary", ""),
        )


# =============================================================================
# V3: Missing Work Models
# =============================================================================

class MissingWorkCategory(str, Enum):
    """Category of missing engineering work."""
    TESTS = "TESTS"
    DOCUMENTATION = "DOCUMENTATION"
    MIGRATION = "MIGRATION"
    ERROR_HANDLING = "ERROR_HANDLING"
    SECURITY = "SECURITY"
    CONFIGURATION = "CONFIGURATION"
    DEPENDENCY = "DEPENDENCY"
    CLI = "CLI"


@dataclass
class MissingWorkFinding:
    """Specific evidence-backed finding for necessary work omitted from change."""
    code: str
    category: MissingWorkCategory
    title: str
    what_was_detected: str
    why_it_matters: str
    evidence: List[str] = field(default_factory=list)
    affected_files: List[str] = field(default_factory=list)
    severity: RiskSeverity = RiskSeverity.WARNING

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "category": self.category.value,
            "title": self.title,
            "what_was_detected": self.what_was_detected,
            "why_it_matters": self.why_it_matters,
            "evidence": self.evidence,
            "affected_files": self.affected_files,
            "severity": self.severity.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissingWorkFinding:
        return cls(
            code=data["code"],
            category=MissingWorkCategory(data.get("category", MissingWorkCategory.TESTS.value)),
            title=data.get("title", ""),
            what_was_detected=data.get("what_was_detected", ""),
            why_it_matters=data.get("why_it_matters", ""),
            evidence=data.get("evidence", []),
            affected_files=data.get("affected_files", []),
            severity=RiskSeverity(data.get("severity", RiskSeverity.WARNING.value)),
        )


@dataclass
class MissingWorkReport:
    """Aggregated report of missing work analysis."""
    findings_count: int = 0
    findings: List[MissingWorkFinding] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "findings_count": self.findings_count,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MissingWorkReport:
        return cls(
            findings_count=data.get("findings_count", 0),
            findings=[MissingWorkFinding.from_dict(f) for f in data.get("findings", [])],
            summary=data.get("summary", ""),
        )


# =============================================================================
# V5: Adversarial Verification Models
# =============================================================================

class AttackCategory(str, Enum):
    """Classification of adversarial test case."""
    EMPTY_INPUT = "EMPTY_INPUT"
    NULL_OR_NONE_INPUT = "NULL_OR_NONE_INPUT"
    BOUNDARY_VALUE = "BOUNDARY_VALUE"
    MINIMUM_VALUE = "MINIMUM_VALUE"
    MAXIMUM_VALUE = "MAXIMUM_VALUE"
    INVALID_FORMAT = "INVALID_FORMAT"
    MALFORMED_INPUT = "MALFORMED_INPUT"
    DUPLICATE_INPUT = "DUPLICATE_INPUT"
    MISSING_REQUIRED_VALUE = "MISSING_REQUIRED_VALUE"
    UNEXPECTED_TYPE = "UNEXPECTED_TYPE"
    ERROR_PATH = "ERROR_PATH"
    PERMISSION_OR_AUTH_EDGE_CASE = "PERMISSION_OR_AUTH_EDGE_CASE"


class AttackResultStatus(str, Enum):
    """Observation outcome of an adversarial test execution."""
    PASS = "PASS"
    FAIL = "FAIL"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"
    UNAVAILABLE = "UNAVAILABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class AttackCase:
    """A typed adversarial test case targeting changed behavior."""
    id: str
    category: AttackCategory
    target_file: str = ""
    target_symbol: str = ""
    rationale: str = ""
    test_input: Any = None
    expected_behavior: str = ""
    execution_code: str = ""
    status: AttackResultStatus = AttackResultStatus.NOT_APPLICABLE
    observed_behavior: str = ""
    duration_ms: int = 0
    stdout: str = ""
    stderr: str = ""
    evidence_id: Optional[str] = None
    integrity_hash: Optional[str] = None
    exit_code: Optional[int] = None
    timeout_seconds: int = 5
    timestamp: str = ""

    def __init__(
        self,
        id: str,
        category: AttackCategory,
        target_file: str = "",
        target_symbol: str = "",
        rationale: str = "",
        test_input: Any = None,
        expected_behavior: str = "",
        execution_code: str = "",
        status: AttackResultStatus = AttackResultStatus.NOT_APPLICABLE,
        observed_behavior: str = "",
        duration_ms: int = 0,
        stdout: str = "",
        stderr: str = "",
        evidence_id: Optional[str] = None,
        integrity_hash: Optional[str] = None,
        exit_code: Optional[int] = None,
        timeout_seconds: int = 5,
        execution_snippet: Optional[str] = None,
        result: Optional[AttackResultStatus] = None,
        timestamp: str = "",
        **kwargs: Any,
    ):
        self.id = id
        self.category = category if isinstance(category, AttackCategory) else AttackCategory(category)
        self.target_file = target_file
        self.target_symbol = target_symbol
        self.rationale = rationale
        self.test_input = test_input
        self.expected_behavior = expected_behavior
        self.execution_code = execution_snippet if execution_snippet is not None else execution_code
        self.status = result if result is not None else status
        self.observed_behavior = observed_behavior
        self.duration_ms = duration_ms
        self.stdout = stdout
        self.stderr = stderr
        self.evidence_id = evidence_id
        self.integrity_hash = integrity_hash
        self.exit_code = exit_code
        self.timeout_seconds = timeout_seconds
        self.timestamp = timestamp

    @property
    def result(self) -> AttackResultStatus:
        return self.status

    @result.setter
    def result(self, val: AttackResultStatus) -> None:
        self.status = val

    @property
    def execution_snippet(self) -> str:
        return self.execution_code

    @execution_snippet.setter
    def execution_snippet(self, val: str) -> None:
        self.execution_code = val

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category.value,
            "target_file": self.target_file,
            "target_symbol": self.target_symbol,
            "rationale": self.rationale,
            "test_input": self.test_input,
            "expected_behavior": self.expected_behavior,
            "execution_code": self.execution_code,
            "execution_snippet": self.execution_code,
            "status": self.status.value,
            "result": self.status.value,
            "observed_behavior": self.observed_behavior,
            "duration_ms": self.duration_ms,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "evidence_id": self.evidence_id,
            "integrity_hash": self.integrity_hash,
            "exit_code": self.exit_code,
            "timeout_seconds": self.timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AttackCase:
        raw_status = data.get("result") or data.get("status") or AttackResultStatus.NOT_APPLICABLE.value
        return cls(
            id=data["id"],
            category=AttackCategory(data["category"]),
            target_file=data.get("target_file", ""),
            target_symbol=data.get("target_symbol", ""),
            rationale=data.get("rationale", ""),
            test_input=data.get("test_input"),
            expected_behavior=data.get("expected_behavior", ""),
            execution_code=data.get("execution_code") or data.get("execution_snippet", ""),
            status=AttackResultStatus(raw_status),
            observed_behavior=data.get("observed_behavior", ""),
            duration_ms=data.get("duration_ms", 0),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            evidence_id=data.get("evidence_id"),
            integrity_hash=data.get("integrity_hash"),
            exit_code=data.get("exit_code"),
            timeout_seconds=data.get("timeout_seconds", 5),
        )


@dataclass
class AdversarialFinding:
    """An evidence-based finding created when an adversarial attack exposes a defect."""
    finding_id: str
    category: AttackCategory
    severity: RiskSeverity
    target_file: str = ""
    target_symbol: str = ""
    description: str = ""
    expected_behavior: str = ""
    observed_behavior: str = ""
    attack_case_id: str = ""
    evidence: List[str] = field(default_factory=list)
    target: str = ""
    attack_case: Optional[AttackCase] = None

    def __init__(
        self,
        finding_id: str = "",
        category: AttackCategory = AttackCategory.ERROR_PATH,
        severity: RiskSeverity = RiskSeverity.WARNING,
        target_file: str = "",
        target_symbol: str = "",
        description: str = "",
        expected_behavior: str = "",
        observed_behavior: str = "",
        attack_case_id: str = "",
        evidence: Optional[List[str]] = None,
        target: str = "",
        attack_case: Optional[AttackCase] = None,
        **kwargs: Any,
    ):
        self.finding_id = finding_id or f"finding:adversarial:{attack_case_id}"
        self.category = category if isinstance(category, AttackCategory) else AttackCategory(category)
        self.severity = severity if isinstance(severity, RiskSeverity) else RiskSeverity(severity)
        self.target_file = target_file
        self.target_symbol = target_symbol
        self.target = target or target_symbol or target_file
        self.description = description
        self.expected_behavior = expected_behavior
        self.observed_behavior = observed_behavior
        self.attack_case_id = attack_case_id or (attack_case.id if attack_case else "")
        self.evidence = evidence or []
        self.attack_case = attack_case

    def to_dict(self) -> Dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "target_file": self.target_file,
            "target_symbol": self.target_symbol,
            "target": self.target or self.target_symbol or self.target_file,
            "description": self.description,
            "expected_behavior": self.expected_behavior,
            "observed_behavior": self.observed_behavior,
            "attack_case_id": self.attack_case_id,
            "evidence": self.evidence,
            "attack_case": self.attack_case.to_dict() if self.attack_case else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AdversarialFinding:
        case_data = data.get("attack_case")
        return cls(
            finding_id=data.get("finding_id", ""),
            category=AttackCategory(data["category"]),
            severity=RiskSeverity(data.get("severity", RiskSeverity.WARNING.value)),
            target_file=data.get("target_file", ""),
            target_symbol=data.get("target_symbol", ""),
            target=data.get("target", ""),
            description=data.get("description", ""),
            expected_behavior=data.get("expected_behavior", ""),
            observed_behavior=data.get("observed_behavior", ""),
            attack_case_id=data.get("attack_case_id", ""),
            evidence=data.get("evidence", []),
            attack_case=AttackCase.from_dict(case_data) if case_data else None,
        )


@dataclass
class AdversarialReport:
    """Aggregated report of adversarial test generation and execution."""
    cases_generated: int = 0
    cases_passed: int = 0
    cases_failed: int = 0
    cases_timed_out: int = 0
    cases_not_applicable: int = 0
    cases: List[AttackCase] = field(default_factory=list)
    findings: List[AdversarialFinding] = field(default_factory=list)
    summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cases_generated": self.cases_generated,
            "cases_passed": self.cases_passed,
            "cases_failed": self.cases_failed,
            "cases_timed_out": self.cases_timed_out,
            "cases_not_applicable": self.cases_not_applicable,
            "cases": [c.to_dict() for c in self.cases],
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AdversarialReport:
        return cls(
            cases_generated=data.get("cases_generated", 0),
            cases_passed=data.get("cases_passed", 0),
            cases_failed=data.get("cases_failed", 0),
            cases_timed_out=data.get("cases_timed_out", 0),
            cases_not_applicable=data.get("cases_not_applicable", 0),
            cases=[AttackCase.from_dict(c) for c in data.get("cases", [])],
            findings=[AdversarialFinding.from_dict(f) for f in data.get("findings", [])],
            summary=data.get("summary", ""),
        )


# =============================================================================
# Check, Warning, and Verification Report Models
# =============================================================================

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


RiskFinding = RiskWarning


@dataclass
class VerificationReport:
    """Complete, structured verification report for a software change (Schema v1.2.0 / v1.3.0)."""
    schema_version: str = "1.2.0"
    target_dir: str = ""
    git_branch: Optional[str] = None
    git_commit: Optional[str] = None
    task_context: Optional[TaskContext] = None
    change_summary: ChangeSummary = field(default_factory=ChangeSummary)
    impact: Optional[ChangeImpact] = None
    drift: Optional[DriftReport] = None
    missing_work: Optional[MissingWorkReport] = None
    adversarial: Optional[AdversarialReport] = None
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
            "task_context": self.task_context.to_dict() if self.task_context else None,
            "verdict": self.verdict.value,
            "reasoning": self.reasoning,
            "change_summary": self.change_summary.to_dict(),
            "impact": self.impact.to_dict() if self.impact else None,
            "drift": self.drift.to_dict() if self.drift else None,
            "missing_work": self.missing_work.to_dict() if self.missing_work else None,
            "adversarial": self.adversarial.to_dict() if self.adversarial else None,
            "checks": [c.to_dict() for c in self.checks],
            "warnings": [w.to_dict() for w in self.warnings],
            "findings": [w.to_dict() for w in self.warnings],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> VerificationReport:
        impact_data = data.get("impact")
        drift_data = data.get("drift")
        missing_data = data.get("missing_work")
        task_data = data.get("task_context")
        adv_data = data.get("adversarial")
        return cls(
            schema_version=data.get("schema_version", "1.2.0"),
            target_dir=data.get("target_dir", ""),
            git_branch=data.get("git_branch"),
            git_commit=data.get("git_commit"),
            task_context=TaskContext.from_dict(task_data) if task_data else None,
            timestamp=data.get("timestamp", ""),
            verdict=Verdict(data.get("verdict", Verdict.INCONCLUSIVE.value)),
            reasoning=data.get("reasoning", ""),
            change_summary=ChangeSummary.from_dict(data.get("change_summary", {})),
            impact=ChangeImpact.from_dict(impact_data) if impact_data else None,
            drift=DriftReport.from_dict(drift_data) if drift_data else None,
            missing_work=MissingWorkReport.from_dict(missing_data) if missing_data else None,
            adversarial=AdversarialReport.from_dict(adv_data) if adv_data else None,
            checks=[CheckResult.from_dict(c) for c in data.get("checks", [])],
            warnings=[RiskWarning.from_dict(w) for w in data.get("warnings", data.get("findings", []))],
        )

