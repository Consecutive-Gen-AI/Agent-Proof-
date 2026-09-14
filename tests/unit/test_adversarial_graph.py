"""Unit tests for Proof Graph integration of adversarial verification."""

from agentproof.adversarial.models import (
    AdversarialFinding,
    AdversarialReport,
    AttackCase,
    AttackCategory,
    AttackResultStatus,
)
from agentproof.core.models import (
    ChangeSummary,
    CheckResult,
    CheckStatus,
    FileCategory,
    FileChange,
    FileStatus,
    RiskSeverity,
    SymbolChange,
    SymbolType,
    Verdict,
    VerificationReport,
)
from agentproof.graph.builder import ProofGraphBuilder
from agentproof.graph.models import NodeType, RelationType


def test_adversarial_nodes_and_relationships():
    # Construct a report with one passing attack and one failing attack
    case_pass = AttackCase(
        id="adv_pass_1",
        category=AttackCategory.EMPTY_INPUT,
        target_file="src/auth.py",
        target_symbol="verify_token",
        rationale="Empty token must be rejected",
        execution_snippet="pass",
        expected_behavior="Rejected",
        result=AttackResultStatus.PASS,
        exit_code=0,
    )
    case_fail = AttackCase(
        id="adv_fail_1",
        category=AttackCategory.BOUNDARY_VALUE,
        target_file="src/auth.py",
        target_symbol="verify_token",
        rationale="Negative expiration time accepted",
        execution_snippet="fail",
        expected_behavior="Rejected",
        result=AttackResultStatus.FAIL,
        exit_code=1,
        observed_behavior="Negative expiration time accepted",
    )
    finding = AdversarialFinding(
        attack_case_id="adv_fail_1",
        category=AttackCategory.BOUNDARY_VALUE,
        severity=RiskSeverity.HIGH,
        target="verify_token",
        description="Boundary check failed",
        expected_behavior="Rejected",
        observed_behavior="Negative expiration time accepted",
        attack_case=case_fail,
    )

    adv_report = AdversarialReport(
        cases_generated=2,
        cases_passed=1,
        cases_failed=1,
        cases=[case_pass, case_fail],
        findings=[finding],
    )

    report = VerificationReport(
        schema_version="1.3.0",
        target_dir="/tmp/repo",
        change_summary=ChangeSummary(
            files=[
                FileChange(
                    path="src/auth.py",
                    status=FileStatus.MODIFIED,
                    category=FileCategory.SOURCE,
                    changed_symbols=[
                        SymbolChange(
                            name="verify_token",
                            symbol_type=SymbolType.FUNCTION,
                            change_type="MODIFIED",
                        )
                    ],
                )
            ]
        ),
        adversarial=adv_report,
        verdict=Verdict.BLOCKED,
        reasoning="Verification blocked by adversarial failure",
    )

    builder = ProofGraphBuilder(report)
    graph = builder.build()

    # 1. Check Node Types
    attack_nodes = graph.find_nodes_by_type(NodeType.ATTACK_CASE)
    assert len(attack_nodes) == 2

    finding_nodes = graph.find_nodes_by_type(NodeType.ADVERSARIAL_FINDING)
    assert len(finding_nodes) == 1
    assert finding_nodes[0].properties["severity"] == "HIGH"

    # 2. Check Relationships
    challenges_edges = [e for e in graph.edges if e.relation == RelationType.CHALLENGES]
    assert len(challenges_edges) >= 2
    assert any("symbol:src/auth.py#verify_token" in e.target_id for e in challenges_edges)

    affects_edges = [e for e in graph.edges if e.relation == RelationType.AFFECTS]
    assert any(e.source_id == "finding:adversarial:adv_fail_1" for e in affects_edges)

    # 3. Trace Verdict
    trace = graph.trace_verdict()
    assert trace["verdict"] == "VERDICT: BLOCKED"
    adv_factors = [f for f in trace["factors"] if f["factor_type"] == "ADVERSARIAL_FINDING"]
    assert len(adv_factors) == 1
    assert adv_factors[0]["factor_id"] == "finding:adversarial:adv_fail_1"
    # Verify supporting attack evidence is linked
    ev_ids = [e["evidence_id"] for e in adv_factors[0]["supporting_evidence"]]
    assert "evidence:attack:adv_fail_1" in ev_ids
