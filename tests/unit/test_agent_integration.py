"""Unit tests for the agent-agnostic integration layer (context ingestion and feedback protocol)."""

import json
import os
from pathlib import Path

from agentproof.core.models import (
    CheckCategory,
    CheckResult,
    CheckStatus,
    Verdict,
    VerificationReport,
)
from agentproof.integration.context import AgentContext, AgentContextIngestion
from agentproof.integration.protocol import AgentFeedback


def test_agent_context_from_env(monkeypatch):
    monkeypatch.setenv("AGENTPROOF_TASK", "Fix token expiration bug")
    monkeypatch.setenv("AGENTPROOF_AGENT_NAME", "claude-code")
    monkeypatch.setenv("AGENTPROOF_MODEL", "claude-3-7-sonnet")
    monkeypatch.setenv("AGENTPROOF_SESSION_ID", "sess-12345")
    monkeypatch.setenv("AGENTPROOF_INTENDED_FILES", "auth/token.py,auth/session.py")

    ctx = AgentContextIngestion.from_env()
    assert ctx is not None
    assert ctx.task_intent == "Fix token expiration bug"
    assert ctx.agent_name == "claude-code"
    assert ctx.model == "claude-3-7-sonnet"
    assert ctx.session_id == "sess-12345"
    assert ctx.intended_files == ["auth/token.py", "auth/session.py"]

    task_ctx = ctx.to_task_context()
    assert task_ctx.raw_text == "Fix token expiration bug"
    assert task_ctx.referenced_paths == ["auth/token.py", "auth/session.py"]


def test_agent_context_from_json_file(tmp_path: Path):
    json_path = tmp_path / "agent_input.json"
    doc = {
        "agent": "cursor",
        "model": "gpt-4o",
        "task": "Refactor database query interface",
        "intended_files": ["db/query.py"],
    }
    json_path.write_text(json.dumps(doc), encoding="utf-8")

    ctx = AgentContextIngestion.from_file_or_stdin(str(json_path))
    assert ctx.agent_name == "cursor"
    assert ctx.task_intent == "Refactor database query interface"
    assert ctx.intended_files == ["db/query.py"]


def test_agent_feedback_formatting():
    # Construct a mock VerificationReport
    report = VerificationReport(
        timestamp="2026-09-14T00:00:00Z",
        target_dir="/app",
        git_branch="main",
        git_commit="abcdef",
        verdict=Verdict.FAILED,
        reasoning="1 validation check(s) failed: pytest (exit 1).",
        checks=[
            CheckResult(
                name="pytest",
                category=CheckCategory.TEST,
                command=["pytest"],
                status=CheckStatus.FAIL,
                exit_code=1,
                duration_ms=1200,
                stderr="assert 1 == 2",
            )
        ],
    )

    feedback = AgentFeedback.from_report(report)
    assert not feedback.is_verified
    assert feedback.exit_code == 1
    assert any("pytest" in b for b in feedback.blockers)

    md = feedback.to_markdown()
    assert "# AgentProof Verification: FAILED" in md
    assert "**Status**: ACTION REQUIRED" in md
    assert "## Blockers to Fix" in md
    assert "pytest" in md

    # Check JSON serialization
    d = feedback.to_dict()
    assert d["verdict"] == "FAILED"
    assert not d["is_verified"]
    assert d["exit_code"] == 1
