"""Unit tests for AgentProof Evidence Graph (ProofGraph)."""

from agentproof.core.models import (
    ChangeImpact,
    ChangeSummary,
    CheckCategory,
    CheckResult,
    CheckStatus,
    FileCategory,
    FileChange,
    FileStatus,
    ImpactRelation,
    ImpactedComponent,
    RiskSeverity,
    RiskWarning,
    SymbolChange,
    SymbolType,
    TaskContext,
    Verdict,
    VerificationReport,
)
from agentproof.graph.builder import ProofGraphBuilder
from agentproof.graph.integrity import compute_integrity_hash
from agentproof.graph.models import (
    GraphEdge,
    GraphNode,
    NodeType,
    ProofGraph,
    RelationType,
)


def test_graph_node_and_edge_creation():
    graph = ProofGraph(schema_version="1.0.0")

    node1 = GraphNode(
        id="check:pytest",
        node_type=NodeType.CHECK,
        label="Pytest Test Suite",
        properties={"category": "TEST"},
        integrity_hash="abc123hash",
    )
    node2 = GraphNode(
        id="evidence:pytest",
        node_type=NodeType.EVIDENCE,
        label="Pytest Result",
        properties={"status": "PASS", "exit_code": 0},
    )
    graph.add_node(node1)
    graph.add_node(node2)

    edge = GraphEdge(
        source_id="check:pytest",
        target_id="evidence:pytest",
        relation=RelationType.PRODUCES,
        label="Produced test evidence",
    )
    graph.add_edge(edge)

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1
    assert graph.get_node("check:pytest") == node1
    assert graph.get_node("evidence:pytest") == node2

    outgoing = graph.get_outgoing_edges("check:pytest")
    assert len(outgoing) == 1
    assert outgoing[0].target_id == "evidence:pytest"

    incoming = graph.get_incoming_edges("evidence:pytest")
    assert len(incoming) == 1
    assert incoming[0].source_id == "check:pytest"


def test_graph_duplicate_edge_prevention():
    graph = ProofGraph()
    n1 = GraphNode(id="n1", node_type=NodeType.FILE, label="file1.py")
    n2 = GraphNode(id="n2", node_type=NodeType.SYMBOL, label="func")
    graph.add_node(n1)
    graph.add_node(n2)

    e1 = GraphEdge(source_id="n1", target_id="n2", relation=RelationType.CONTAINS)
    e2 = GraphEdge(source_id="n1", target_id="n2", relation=RelationType.CONTAINS)
    graph.add_edge(e1)
    graph.add_edge(e2)

    assert len(graph.edges) == 1


def test_graph_serialization_round_trip():
    graph = ProofGraph(schema_version="1.0.0", metadata={"commit": "12345678"})
    graph.add_node(GraphNode(id="v:root", node_type=NodeType.VERDICT, label="VERIFIED"))
    graph.add_node(GraphNode(id="c:pytest", node_type=NodeType.CHECK, label="pytest"))
    graph.add_edge(GraphEdge(source_id="c:pytest", target_id="v:root", relation=RelationType.AFFECTS))

    json_str = graph.to_json()
    deserialized = ProofGraph.from_json(json_str)

    assert deserialized.schema_version == "1.0.0"
    assert deserialized.metadata["commit"] == "12345678"
    assert len(deserialized.nodes) == 2
    assert len(deserialized.edges) == 1
    assert deserialized.get_node("v:root").node_type == NodeType.VERDICT
    assert deserialized.edges[0].relation == RelationType.AFFECTS


def test_graph_builder_from_verification_report():
    file_change = FileChange(
        path="auth/token.py",
        status=FileStatus.MODIFIED,
        additions=20,
        deletions=5,
        category=FileCategory.SOURCE,
        changed_symbols=[
            SymbolChange(name="verify_token", symbol_type=SymbolType.FUNCTION, file_path="auth/token.py", change_type="MODIFIED")
        ],
    )
    change_summary = ChangeSummary(
        total_files=1,
        total_additions=20,
        total_deletions=5,
        files=[file_change],
    )
    check = CheckResult(
        name="pytest",
        category=CheckCategory.TEST,
        command=["pytest"],
        status=CheckStatus.PASS,
        exit_code=0,
        duration_ms=120,
        output_summary="1 passed",
    )

    warning = RiskWarning(
        code="SECURITY_SENSITIVE_MODIFIED",
        severity=RiskSeverity.WARNING,
        message="Security sensitive file modified",
        what_was_detected="Modified auth/token.py",
        why_it_matters="Authentication logic affects authorization",
        related_files=["auth/token.py"],
    )
    report = VerificationReport(
        schema_version="1.2.0",
        target_dir="/test/repo",
        git_commit="abcdef01",
        change_summary=change_summary,
        checks=[check],
        warnings=[warning],
        verdict=Verdict.VERIFIED_WITH_WARNINGS,
        reasoning="Tests passed with 1 security warning.",
        timestamp="2026-09-13T12:00:00Z",
    )

    builder = ProofGraphBuilder(report)
    graph = builder.build()

    # Check key nodes exist
    assert graph.get_node("verdict:root") is not None
    assert graph.get_node("verdict:root").node_type == NodeType.VERDICT
    assert graph.get_node("file:auth/token.py") is not None
    assert graph.get_node("symbol:auth/token.py#verify_token") is not None
    assert graph.get_node("check:pytest") is not None
    assert graph.get_node("evidence:pytest") is not None
    assert graph.get_node("finding:risk:SECURITY_SENSITIVE_MODIFIED:0") is not None

    # Check relationships
    outgoing_file = graph.get_outgoing_edges("file:auth/token.py")
    # File contains symbol, and file triggers security warning
    relations = [e.relation for e in outgoing_file]
    assert RelationType.CONTAINS in relations
    assert RelationType.TRIGGERS in relations

    # Trace verdict
    trace = graph.trace_verdict()
    assert trace["verdict"] == "VERDICT: VERIFIED_WITH_WARNINGS"
    assert len(trace["factors"]) >= 2  # evidence:pytest and risk finding
