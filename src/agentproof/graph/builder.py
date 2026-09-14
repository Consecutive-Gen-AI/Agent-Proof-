"""Builder that transforms a VerificationReport into an interconnected ProofGraph."""

from __future__ import annotations

from typing import Optional

from agentproof.core.models import (
    CheckResult,
    FileChange,
    RiskWarning,
    VerificationReport,
)
from agentproof.graph.integrity import compute_integrity_hash
from agentproof.graph.models import (
    GraphEdge,
    GraphNode,
    NodeType,
    ProofGraph,
    RelationType,
)


class ProofGraphBuilder:
    """Builds a deterministic, queryable ProofGraph from a VerificationReport."""

    def __init__(self, report: VerificationReport):
        self.report = report
        self.graph = ProofGraph(
            schema_version="1.0.0",
            metadata={
                "target_dir": report.target_dir,
                "git_branch": report.git_branch,
                "git_commit": report.git_commit,
                "timestamp": report.timestamp,
            },
        )

    def build(self) -> ProofGraph:
        """Construct all nodes and relational edges."""
        # 1. Root Verdict Node
        verdict_id = "verdict:root"
        verdict_props = {
            "verdict": self.report.verdict.value,
            "reasoning": self.report.reasoning,
            "timestamp": self.report.timestamp,
        }
        self.graph.add_node(GraphNode(
            id=verdict_id,
            node_type=NodeType.VERDICT,
            label=f"VERDICT: {self.report.verdict.value}",
            properties=verdict_props,
            integrity_hash=compute_integrity_hash(verdict_props),
        ))

        # 2. Task Node (if present)
        task_id: Optional[str] = None
        if self.report.task_context and self.report.task_context.raw_text:
            task_id = "task:intent"
            task_props = self.report.task_context.to_dict()
            self.graph.add_node(GraphNode(
                id=task_id,
                node_type=NodeType.TASK,
                label=f"Task: {self.report.task_context.raw_text[:60]}",
                properties=task_props,
                integrity_hash=compute_integrity_hash(task_props),
            ))


        # 3. Overall Change Node
        change_id = "change:working_tree"
        change_props = {
            "files_count": len(self.report.change_summary.files),
            "additions": self.report.change_summary.total_additions,
            "deletions": self.report.change_summary.total_deletions,
            "staged_files": self.report.change_summary.staged_files_count,
            "unstaged_files": self.report.change_summary.unstaged_files_count,
        }

        self.graph.add_node(GraphNode(
            id=change_id,
            node_type=NodeType.CHANGE,
            label=f"Change ({len(self.report.change_summary.files)} files, +{change_props['additions']}/-{change_props['deletions']})",
            properties=change_props,
            integrity_hash=compute_integrity_hash(change_props),
        ))

        # 4. File and Symbol Nodes
        for fc in self.report.change_summary.files:
            file_id = f"file:{fc.path}"
            file_props = {
                "path": fc.path,
                "status": fc.status.value,
                "category": fc.category.value,
                "additions": fc.additions,
                "deletions": fc.deletions,
                "is_staged": fc.is_staged,
                "is_unstaged": fc.is_unstaged,
            }
            self.graph.add_node(GraphNode(
                id=file_id,
                node_type=NodeType.FILE,
                label=fc.path,
                properties=file_props,
                integrity_hash=compute_integrity_hash(file_props),
            ))
            # Edge: CHANGE contains FILE
            self.graph.add_edge(GraphEdge(
                source_id=change_id,
                target_id=file_id,
                relation=RelationType.CONTAINS,
                label=f"Contains file ({fc.status.value})",
            ))

            # If task explicitly targeted this file
            if task_id and self.report.task_context:
                if fc.path in self.report.task_context.referenced_paths:
                    self.graph.add_edge(GraphEdge(
                        source_id=task_id,
                        target_id=file_id,
                        relation=RelationType.TARGETS,
                        label="Explicitly targets file",
                    ))


            # Symbols within the file
            for sym in fc.changed_symbols:
                sym_id = f"symbol:{fc.path}#{sym.name}"
                sym_props = {
                    "name": sym.name,
                    "symbol_type": sym.symbol_type.value,
                    "file_path": fc.path,
                    "change_type": sym.change_type,
                    "line_number": sym.line_number,
                }
                self.graph.add_node(GraphNode(
                    id=sym_id,
                    node_type=NodeType.SYMBOL,
                    label=f"{sym.symbol_type.value} {sym.name}",
                    properties=sym_props,
                    integrity_hash=compute_integrity_hash(sym_props),
                ))
                # FILE contains SYMBOL
                self.graph.add_edge(GraphEdge(
                    source_id=file_id,
                    target_id=sym_id,
                    relation=RelationType.CONTAINS,
                    label="Contains symbol",
                ))
                # CHANGE modifies SYMBOL
                self.graph.add_edge(GraphEdge(
                    source_id=change_id,
                    target_id=sym_id,
                    relation=RelationType.MODIFIES,
                    label=f"{sym.change_type} symbol",
                ))

        # 5. Impact Relationships
        if self.report.impact:
            all_impacted = self.report.impact.impacted_source_files + self.report.impact.impacted_test_files
            for comp in all_impacted:
                caller_id = f"file:{comp.file_path}"
                # Ensure caller node exists
                if not self.graph.get_node(caller_id):
                    caller_props = {"path": comp.file_path, "category": "IMPACTED"}
                    self.graph.add_node(GraphNode(
                        id=caller_id,
                        node_type=NodeType.FILE,
                        label=comp.file_path,
                        properties=caller_props,
                        integrity_hash=compute_integrity_hash(caller_props),
                    ))
                # Link source file to impacted caller
                if comp.impacted_by:
                    src_id = f"file:{comp.impacted_by}"
                    if self.graph.get_node(src_id):
                        self.graph.add_edge(GraphEdge(
                            source_id=src_id,
                            target_id=caller_id,
                            relation=RelationType.IMPACTS,
                            label=f"Impacts dependent ({comp.relation.value})",
                            properties={"relationship": comp.relation.value, "description": comp.description},
                        ))


        # 6. Checks and Evidence Nodes
        for check in self.report.checks:
            check_id = f"check:{check.name}"
            check_props = {
                "name": check.name,
                "category": check.category.value,
                "command": check.command,
                "git_commit": check.git_commit,
            }
            self.graph.add_node(GraphNode(
                id=check_id,
                node_type=NodeType.CHECK,
                label=f"Check: {check.name}",
                properties=check_props,
                integrity_hash=compute_integrity_hash(check_props),
            ))
            self.graph.add_edge(GraphEdge(
                source_id=change_id,
                target_id=check_id,
                relation=RelationType.VALIDATED_BY,
                label=f"Validated by {check.name}",
            ))

            # Evidence node
            evidence_id = f"evidence:{check.name}"
            evidence_props = {
                "check_name": check.name,
                "status": check.status.value,
                "exit_code": check.exit_code,
                "duration_ms": check.duration_ms,
                "output_summary": check.output_summary,
                "timestamp": check.timestamp,
            }
            self.graph.add_node(GraphNode(
                id=evidence_id,
                node_type=NodeType.EVIDENCE,
                label=f"Evidence: {check.name} [{check.status.value}]",
                properties=evidence_props,
                integrity_hash=compute_integrity_hash(evidence_props),
            ))
            self.graph.add_edge(GraphEdge(
                source_id=check_id,
                target_id=evidence_id,
                relation=RelationType.PRODUCES,
                label=f"Produced evidence ({check.status.value})",
            ))

            # Evidence directly affects verdict
            self.graph.add_edge(GraphEdge(
                source_id=evidence_id,
                target_id=verdict_id,
                relation=RelationType.AFFECTS,
                label=f"Check {check.name} result: {check.status.value}",
                properties={
                    "status": check.status.value,
                    "reason": f"Execution status {check.status.value} (exit code {check.exit_code})",
                },
            ))

        # 7. Risk Findings
        for idx, warning in enumerate(self.report.warnings):
            finding_id = f"finding:risk:{warning.code}:{idx}"
            finding_props = {
                "code": warning.code,
                "severity": warning.severity.value,
                "what_was_detected": warning.what_was_detected,
                "why_it_matters": warning.why_it_matters,
                "evidence": warning.evidence,
            }
            self.graph.add_node(GraphNode(
                id=finding_id,
                node_type=NodeType.RISK_FINDING,
                label=f"Risk: {warning.code} [{warning.severity.value}]",
                properties=finding_props,
                integrity_hash=compute_integrity_hash(finding_props),
            ))
            # Link related files triggering the risk
            for rf in warning.related_files:
                rf_id = f"file:{rf}"
                if self.graph.get_node(rf_id):
                    self.graph.add_edge(GraphEdge(
                        source_id=rf_id,
                        target_id=finding_id,
                        relation=RelationType.TRIGGERS,
                        label=f"Triggers {warning.code}",
                    ))
            # Finding affects verdict
            self.graph.add_edge(GraphEdge(
                source_id=finding_id,
                target_id=verdict_id,
                relation=RelationType.AFFECTS,
                label=f"Risk warning: {warning.code}",
                properties={"severity": warning.severity.value, "reason": warning.what_was_detected},
            ))

        # 8. Drift Findings
        if self.report.drift:
            for idx, df in enumerate(self.report.drift.findings):
                drift_id = f"finding:drift:{idx}"
                drift_props = {
                    "file_path": df.file_path,
                    "drift_level": df.drift_level.value,
                    "severity": df.severity.value,
                    "what_was_detected": df.what_was_detected,
                    "why_it_was_considered_drift": df.why_it_was_considered_drift,
                    "supporting_evidence": df.supporting_evidence,
                }
                self.graph.add_node(GraphNode(
                    id=drift_id,
                    node_type=NodeType.DRIFT_FINDING,
                    label=f"Drift: {df.file_path}",
                    properties=drift_props,
                    integrity_hash=compute_integrity_hash(drift_props),
                ))
                file_id = f"file:{df.file_path}"
                if self.graph.get_node(file_id):
                    self.graph.add_edge(GraphEdge(
                        source_id=file_id,
                        target_id=drift_id,
                        relation=RelationType.TRIGGERS,
                        label="Triggers scope drift",
                    ))
                self.graph.add_edge(GraphEdge(
                    source_id=drift_id,
                    target_id=verdict_id,
                    relation=RelationType.AFFECTS,
                    label=f"Scope drift on {df.file_path}",
                    properties={"severity": df.severity.value, "reason": df.why_it_was_considered_drift},
                ))

        # 9. Missing Work Findings
        if self.report.missing_work:
            for idx, mw in enumerate(self.report.missing_work.findings):
                mw_id = f"finding:missing_work:{mw.code}:{idx}"
                mw_props = {
                    "code": mw.code,
                    "category": mw.category.value,
                    "title": mw.title,
                    "severity": mw.severity.value,
                    "what_was_detected": mw.what_was_detected,
                    "why_it_matters": mw.why_it_matters,
                    "evidence": mw.evidence,
                    "affected_files": mw.affected_files,
                }
                self.graph.add_node(GraphNode(
                    id=mw_id,
                    node_type=NodeType.MISSING_WORK,
                    label=f"Missing: {mw.category.value} ({mw.code})",
                    properties=mw_props,
                    integrity_hash=compute_integrity_hash(mw_props),
                ))
                for af in mw.affected_files:
                    af_id = f"file:{af}"
                    if self.graph.get_node(af_id):
                        self.graph.add_edge(GraphEdge(
                            source_id=af_id,
                            target_id=mw_id,
                            relation=RelationType.TRIGGERS,
                            label=f"Affected by {mw.code}",
                        ))
                self.graph.add_edge(GraphEdge(
                    source_id=mw_id,
                    target_id=verdict_id,
                    relation=RelationType.AFFECTS,
                    label=f"Missing work: {mw.code}",
                    properties={"severity": mw.severity.value, "reason": mw.what_was_detected},
                ))

        # 10. Adversarial Verification
        if self.report.adversarial:
            for case in self.report.adversarial.cases:
                attack_id = f"attack:{case.id}"
                attack_props = case.to_dict()
                self.graph.add_node(GraphNode(
                    id=attack_id,
                    node_type=NodeType.ATTACK_CASE,
                    label=f"Attack: {case.category.value} ({case.target_symbol or case.target_file})",
                    properties=attack_props,
                    integrity_hash=compute_integrity_hash(attack_props),
                ))
                self.graph.add_edge(GraphEdge(
                    source_id=change_id,
                    target_id=attack_id,
                    relation=RelationType.VALIDATED_BY,
                    label=f"Validated by adversarial case {case.id}",
                ))

                # Challenges target symbol or file
                target_node_id = None
                if case.target_symbol:
                    candidate_sym = f"symbol:{case.target_file}#{case.target_symbol}"
                    if self.graph.get_node(candidate_sym):
                        target_node_id = candidate_sym
                if not target_node_id and case.target_file:
                    candidate_file = f"file:{case.target_file}"
                    if self.graph.get_node(candidate_file):
                        target_node_id = candidate_file

                if target_node_id:
                    self.graph.add_edge(GraphEdge(
                        source_id=attack_id,
                        target_id=target_node_id,
                        relation=RelationType.CHALLENGES,
                        label=f"Challenges {case.category.value} robustness",
                    ))

                # Attack Evidence Node
                res_val = case.result.value if case.result else "NOT_RUN"
                ev_id = f"evidence:attack:{case.id}"
                ev_props = {
                    "attack_id": case.id,
                    "category": case.category.value,
                    "result": res_val,
                    "duration_ms": case.duration_ms,
                    "observed_behavior": case.observed_behavior,
                    "timestamp": case.timestamp,
                }
                self.graph.add_node(GraphNode(
                    id=ev_id,
                    node_type=NodeType.EVIDENCE,
                    label=f"Attack Evidence: {case.id} [{res_val}]",
                    properties=ev_props,
                    integrity_hash=case.integrity_hash or compute_integrity_hash(ev_props),
                ))
                self.graph.add_edge(GraphEdge(
                    source_id=attack_id,
                    target_id=ev_id,
                    relation=RelationType.PRODUCES,
                    label=f"Produced attack evidence ({res_val})",
                ))

                # If passed, support verdict
                if res_val == "PASS":
                    self.graph.add_edge(GraphEdge(
                        source_id=ev_id,
                        target_id=verdict_id,
                        relation=RelationType.SUPPORTS,
                        label=f"Adversarial check passed: {case.category.value}",
                        properties={
                            "status": "PASS",
                            "reason": f"Attack case {case.id} satisfied expected behavior",
                        },
                    ))

            # Adversarial Findings
            for finding in self.report.adversarial.findings:
                af_id = f"finding:adversarial:{finding.attack_case_id}"
                af_props = finding.to_dict()
                self.graph.add_node(GraphNode(
                    id=af_id,
                    node_type=NodeType.ADVERSARIAL_FINDING,
                    label=f"Adversarial Finding: {finding.category.value} [{finding.severity.value}]",
                    properties=af_props,
                    integrity_hash=compute_integrity_hash(af_props),
                ))

                # Link from attack evidence to finding
                ev_id = f"evidence:attack:{finding.attack_case_id}"
                if self.graph.get_node(ev_id):
                    self.graph.add_edge(GraphEdge(
                        source_id=ev_id,
                        target_id=af_id,
                        relation=RelationType.TRIGGERS,
                        label="Triggers adversarial finding",
                    ))

                # Finding affects verdict
                self.graph.add_edge(GraphEdge(
                    source_id=af_id,
                    target_id=verdict_id,
                    relation=RelationType.AFFECTS,
                    label=f"Adversarial failure: {finding.category.value}",
                    properties={"severity": finding.severity.value, "reason": finding.description},
                ))

        # Store graph overall integrity
        canonical_nodes_and_edges = [n.to_dict() for n in self.graph.nodes.values()] + [e.to_dict() for e in self.graph.edges]
        self.graph.metadata["graph_integrity_hash"] = compute_integrity_hash(canonical_nodes_and_edges)

        return self.graph
