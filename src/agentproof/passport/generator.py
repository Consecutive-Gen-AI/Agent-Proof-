"""Generator that creates a machine-readable ProofPassport from a VerificationReport and ProofGraph."""

from __future__ import annotations

import datetime
from typing import List, Optional

from agentproof.core.models import VerificationReport
from agentproof.graph.builder import ProofGraphBuilder
from agentproof.graph.integrity import compute_integrity_hash
from agentproof.graph.models import NodeType, ProofGraph
from agentproof.passport.models import (
    PassportChangeSummary,
    PassportCheckItem,
    PassportDriftSummary,
    PassportEvidenceRef,
    PassportFindingItem,
    PassportImpactSummary,
    PassportMetadata,
    PassportMissingWorkSummary,
    PassportRepository,
    PassportTask,
    PassportVerdict,
    ProofPassport,
)


class PassportGenerator:
    """Generates a verifiable, versioned ProofPassport."""

    def __init__(self, report: VerificationReport, graph: Optional[ProofGraph] = None):
        self.report = report
        self.graph = graph or ProofGraphBuilder(report).build()

    def generate(self) -> ProofPassport:
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

        # 1. Repository Info
        repo = PassportRepository(
            target_dir=self.report.target_dir,
            branch=self.report.git_branch,
            commit=self.report.git_commit,
        )

        # 2. Task Info
        task: Optional[PassportTask] = None
        if self.report.task_context:
            task = PassportTask(
                description=self.report.task_context.raw_text,
                scope=self.report.task_context.inferred_scope,
                domains=self.report.task_context.expected_domains,
            )


        # 3. Change Summary
        total_symbols = sum(len(fc.changed_symbols) for fc in self.report.change_summary.files)
        change = PassportChangeSummary(
            files_count=len(self.report.change_summary.files),
            symbols_count=total_symbols,
            additions=self.report.change_summary.total_additions,
            deletions=self.report.change_summary.total_deletions,
        )

        # 4. Impact Summary
        total_callers = len(self.report.impact.impacted_source_files) if self.report.impact else 0
        total_tests = len(self.report.impact.impacted_test_files) if self.report.impact else 0
        impact = PassportImpactSummary(
            rating=self.report.impact.total_impact_score if self.report.impact else "LOW",
            impacted_callers_count=total_callers,
            related_tests_count=total_tests,
        )


        # 5. Drift Summary
        drift = PassportDriftSummary(
            level=self.report.drift.drift_level.value if self.report.drift else "NONE",
            unexpected_files_count=len(self.report.drift.unexpected_files) if self.report.drift else 0,
            confidence=self.report.drift.confidence if self.report.drift else "high",
        )

        # 6. Missing Work Summary
        missing_work = PassportMissingWorkSummary(
            gaps_count=len(self.report.missing_work.findings) if self.report.missing_work else 0,
            categories=[f.category.value for f in self.report.missing_work.findings] if self.report.missing_work else [],
        )

        # 7. Checks
        checks: List[PassportCheckItem] = []
        for c in self.report.checks:
            checks.append(PassportCheckItem(
                name=c.name,
                category=c.category.value,
                status=c.status.value,
                exit_code=c.exit_code,
                duration_ms=c.duration_ms,
                output_summary=c.output_summary,
            ))

        # 8. Findings (Unified from Risk Warnings, Drift, and Missing Work)
        findings: List[PassportFindingItem] = []
        for w in self.report.warnings:
            findings.append(PassportFindingItem(
                category="RISK",
                code=w.code,
                severity=w.severity.value,
                summary=w.what_was_detected,
            ))
        if self.report.drift:
            for df in self.report.drift.findings:
                findings.append(PassportFindingItem(
                    category="DRIFT",
                    code="SCOPE_DRIFT",
                    severity=df.severity.value,
                    summary=f"{df.file_path}: {df.why_it_was_considered_drift}",
                ))
        if self.report.missing_work:
            for mw in self.report.missing_work.findings:
                findings.append(PassportFindingItem(
                    category="MISSING_WORK",
                    code=mw.category.value,
                    severity=mw.severity.value,
                    summary=mw.what_was_detected,
                ))


        # 9. Evidence References (from graph evidence nodes)
        evidence_refs: List[PassportEvidenceRef] = []
        evidence_nodes = self.graph.find_nodes_by_type(NodeType.EVIDENCE)
        for ev in evidence_nodes:
            evidence_refs.append(PassportEvidenceRef(
                evidence_id=ev.id,
                source_check=ev.properties.get("check_name", ev.label),
                status=ev.properties.get("status", "UNKNOWN"),
                integrity_hash=ev.integrity_hash,
            ))

        # 10. Verdict
        verdict = PassportVerdict(
            status=self.report.verdict.value,
            reasoning=self.report.reasoning,
        )

        # 11. Deterministic Passport ID
        id_payload = f"{repo.commit}:{self.report.verdict.value}:{now_iso}"
        passport_id = f"pass-{compute_integrity_hash(id_payload)[:16]}"

        # 12. Preliminary metadata without hash
        metadata = PassportMetadata(
            schema_version="1.0.0",
            generated_at=now_iso,
            graph_node_count=len(self.graph.nodes),
            graph_edge_count=len(self.graph.edges),
            passport_integrity_hash="",
        )

        passport = ProofPassport(
            passport_id=passport_id,
            repository=repo,
            task=task,
            change=change,
            impact=impact,
            drift=drift,
            missing_work=missing_work,
            checks=checks,
            findings=findings,
            evidence=evidence_refs,
            verdict=verdict,
            metadata=metadata,
        )

        # 13. Compute and seal passport integrity hash
        passport_dict = passport.to_dict()
        passport_dict["metadata"]["passport_integrity_hash"] = ""
        passport.metadata.passport_integrity_hash = compute_integrity_hash(passport_dict)

        return passport
