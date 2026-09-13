"""Domain models for the AgentProof Proof Passport (Schema v1.0.0)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PassportRepository:
    """Identity and revision details for the verified repository."""
    target_dir: str
    branch: Optional[str] = None
    commit: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_dir": self.target_dir,
            "branch": self.branch,
            "commit": self.commit,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportRepository:
        return cls(
            target_dir=data.get("target_dir", ""),
            branch=data.get("branch"),
            commit=data.get("commit"),
        )


@dataclass
class PassportTask:
    """Summary of intended task context."""
    description: Optional[str] = None
    scope: Optional[str] = None
    domains: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "description": self.description,
            "scope": self.scope,
            "domains": self.domains,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportTask:
        return cls(
            description=data.get("description"),
            scope=data.get("scope"),
            domains=data.get("domains", []),
        )


@dataclass
class PassportChangeSummary:
    """Summary of code changes and extracted symbols."""
    files_count: int = 0
    symbols_count: int = 0
    additions: int = 0
    deletions: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files_count": self.files_count,
            "symbols_count": self.symbols_count,
            "additions": self.additions,
            "deletions": self.deletions,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportChangeSummary:
        return cls(
            files_count=data.get("files_count", 0),
            symbols_count=data.get("symbols_count", 0),
            additions=data.get("additions", 0),
            deletions=data.get("deletions", 0),
        )


@dataclass
class PassportImpactSummary:
    """Summary of blast radius and impacted dependencies."""
    rating: str = "LOW"
    impacted_callers_count: int = 0
    related_tests_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rating": self.rating,
            "impacted_callers_count": self.impacted_callers_count,
            "related_tests_count": self.related_tests_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportImpactSummary:
        return cls(
            rating=data.get("rating", "LOW"),
            impacted_callers_count=data.get("impacted_callers_count", 0),
            related_tests_count=data.get("related_tests_count", 0),
        )


@dataclass
class PassportDriftSummary:
    """Summary of task-to-change drift detection."""
    level: str = "NONE"
    unexpected_files_count: int = 0
    confidence: str = "high"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "level": self.level,
            "unexpected_files_count": self.unexpected_files_count,
            "confidence": self.confidence,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportDriftSummary:
        return cls(
            level=data.get("level", "NONE"),
            unexpected_files_count=data.get("unexpected_files_count", 0),
            confidence=data.get("confidence", "high"),
        )


@dataclass
class PassportMissingWorkSummary:
    """Summary of omissions and gaps detected."""
    gaps_count: int = 0
    categories: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gaps_count": self.gaps_count,
            "categories": self.categories,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportMissingWorkSummary:
        return cls(
            gaps_count=data.get("gaps_count", 0),
            categories=data.get("categories", []),
        )


@dataclass
class PassportCheckItem:
    """Summary of an individual verification check."""
    name: str
    category: str
    status: str
    exit_code: Optional[int] = None
    duration_ms: int = 0
    output_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status,
            "exit_code": self.exit_code,
            "duration_ms": self.duration_ms,
            "output_summary": self.output_summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportCheckItem:
        return cls(
            name=data["name"],
            category=data["category"],
            status=data["status"],
            exit_code=data.get("exit_code"),
            duration_ms=data.get("duration_ms", 0),
            output_summary=data.get("output_summary", ""),
        )


@dataclass
class PassportFindingItem:
    """Summary of an individual finding (risk, drift, or omission)."""
    category: str  # "RISK", "DRIFT", "MISSING_WORK"
    code: str
    severity: str
    summary: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "code": self.code,
            "severity": self.severity,
            "summary": self.summary,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportFindingItem:
        return cls(
            category=data["category"],
            code=data["code"],
            severity=data["severity"],
            summary=data["summary"],
        )


@dataclass
class PassportEvidenceRef:
    """Reference to evidence collected during verification."""
    evidence_id: str
    source_check: str
    status: str
    integrity_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "source_check": self.source_check,
            "status": self.status,
            "integrity_hash": self.integrity_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportEvidenceRef:
        return cls(
            evidence_id=data["evidence_id"],
            source_check=data["source_check"],
            status=data["status"],
            integrity_hash=data.get("integrity_hash"),
        )


@dataclass
class PassportVerdict:
    """Final verification verdict and rationale."""
    status: str
    reasoning: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "reasoning": self.reasoning,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportVerdict:
        return cls(
            status=data["status"],
            reasoning=data["reasoning"],
        )


@dataclass
class PassportMetadata:
    """Metadata and provenance digest for the passport."""
    schema_version: str = "1.0.0"
    generated_at: str = ""
    graph_node_count: int = 0
    graph_edge_count: int = 0
    passport_integrity_hash: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "graph_node_count": self.graph_node_count,
            "graph_edge_count": self.graph_edge_count,
            "passport_integrity_hash": self.passport_integrity_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PassportMetadata:
        return cls(
            schema_version=data.get("schema_version", "1.0.0"),
            generated_at=data.get("generated_at", ""),
            graph_node_count=data.get("graph_node_count", 0),
            graph_edge_count=data.get("graph_edge_count", 0),
            passport_integrity_hash=data.get("passport_integrity_hash", ""),
        )


@dataclass
class ProofPassport:
    """
    Machine-readable Proof Passport summarizing the verification state of a software change.
    Generated deterministically from a VerificationReport and its associated ProofGraph.
    """
    passport_id: str
    repository: PassportRepository
    change: PassportChangeSummary
    impact: PassportImpactSummary
    drift: PassportDriftSummary
    missing_work: PassportMissingWorkSummary
    checks: List[PassportCheckItem]
    findings: List[PassportFindingItem]
    evidence: List[PassportEvidenceRef]
    verdict: PassportVerdict
    metadata: PassportMetadata
    task: Optional[PassportTask] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passport_id": self.passport_id,
            "repository": self.repository.to_dict(),
            "task": self.task.to_dict() if self.task else None,
            "change": self.change.to_dict(),
            "impact": self.impact.to_dict(),
            "drift": self.drift.to_dict(),
            "missing_work": self.missing_work.to_dict(),
            "checks": [c.to_dict() for c in self.checks],
            "findings": [f.to_dict() for f in self.findings],
            "evidence": [e.to_dict() for e in self.evidence],
            "verdict": self.verdict.to_dict(),
            "metadata": self.metadata.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProofPassport:
        task_data = data.get("task")
        return cls(
            passport_id=data["passport_id"],
            repository=PassportRepository.from_dict(data.get("repository", {})),
            task=PassportTask.from_dict(task_data) if task_data else None,
            change=PassportChangeSummary.from_dict(data.get("change", {})),
            impact=PassportImpactSummary.from_dict(data.get("impact", {})),
            drift=PassportDriftSummary.from_dict(data.get("drift", {})),
            missing_work=PassportMissingWorkSummary.from_dict(data.get("missing_work", {})),
            checks=[PassportCheckItem.from_dict(c) for c in data.get("checks", [])],
            findings=[PassportFindingItem.from_dict(f) for f in data.get("findings", [])],
            evidence=[PassportEvidenceRef.from_dict(e) for e in data.get("evidence", [])],
            verdict=PassportVerdict.from_dict(data.get("verdict", {"status": "INCONCLUSIVE", "reasoning": ""})),
            metadata=PassportMetadata.from_dict(data.get("metadata", {})),
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> ProofPassport:
        return cls.from_dict(json.loads(json_str))
