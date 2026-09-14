"""Unit tests for V2 domain model extensions."""

from agentproof.core.models import (
    ChangeImpact,
    ChangeSummary,
    FileCategory,
    FileChange,
    FileStatus,
    ImpactRelation,
    ImpactedComponent,
    RiskFinding,
    RiskSeverity,
    SymbolChange,
    SymbolType,
    Verdict,
    VerificationReport,
)


def test_symbol_change_serialization():
    sym = SymbolChange(
        name="verify_change",
        symbol_type=SymbolType.FUNCTION,
        file_path="src/agentproof/core.py",
        change_type="MODIFIED",
        line_number=42,
    )
    d = sym.to_dict()
    assert d["name"] == "verify_change"
    assert d["symbol_type"] == "FUNCTION"
    assert d["line_number"] == 42

    restored = SymbolChange.from_dict(d)
    assert restored.name == sym.name
    assert restored.symbol_type == sym.symbol_type
    assert restored.line_number == 42


def test_file_change_v2_fields():
    fc = FileChange(
        path="src/new_path.py",
        status=FileStatus.RENAMED,
        old_path="src/old_path.py",
        is_staged=True,
        is_unstaged=False,
        staged_additions=10,
        staged_deletions=2,
        unstaged_additions=0,
        unstaged_deletions=0,
        changed_symbols=[
            SymbolChange(name="OldClass", symbol_type=SymbolType.CLASS, file_path="src/new_path.py")
        ],
    )
    d = fc.to_dict()
    assert d["old_path"] == "src/old_path.py"
    assert d["is_staged"] is True
    assert len(d["changed_symbols"]) == 1

    restored = FileChange.from_dict(d)
    assert restored.old_path == "src/old_path.py"
    assert restored.is_staged is True
    assert restored.changed_symbols[0].name == "OldClass"


def test_change_impact_serialization():
    impact = ChangeImpact(
        changed_modules=["user_service"],
        impacted_source_files=[
            ImpactedComponent(
                file_path="src/api.py",
                relation=ImpactRelation.CALLER,
                impacted_by="user_service",
                description="Calls user service",
            )
        ],
        impacted_test_files=[
            ImpactedComponent(
                file_path="tests/test_user.py",
                relation=ImpactRelation.TEST_FOR_MODULE,
                impacted_by="user_service",
            )
        ],
        total_impact_score="MEDIUM",
        untested_impacts=["src/api.py"],
    )
    d = impact.to_dict()
    assert d["total_impact_score"] == "MEDIUM"
    assert len(d["impacted_source_files"]) == 1

    restored = ChangeImpact.from_dict(d)
    assert restored.total_impact_score == "MEDIUM"
    assert restored.impacted_source_files[0].file_path == "src/api.py"


def test_verification_report_v2_serialization():
    report = VerificationReport(
        schema_version="1.1.0",
        target_dir="/tmp/repo",
        impact=ChangeImpact(total_impact_score="LOW"),
        verdict=Verdict.VERIFIED,
    )
    d = report.to_dict()
    assert d["schema_version"] == "1.1.0"
    assert d["impact"]["total_impact_score"] == "LOW"
    assert "findings" in d

    restored = VerificationReport.from_dict(d)
    assert restored.schema_version == "1.1.0"
    assert restored.impact is not None
    assert restored.impact.total_impact_score == "LOW"
