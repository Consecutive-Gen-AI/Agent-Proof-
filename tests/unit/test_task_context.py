"""Unit tests for task context parsing and domain inference."""

from pathlib import Path
from agentproof.task.context import TaskParser


def test_task_parser_basic():
    parser = TaskParser()
    ctx = parser.parse("Fix authentication token expiration handling")
    assert "token" in ctx.normalized_keywords
    assert "expiration" in ctx.normalized_keywords
    assert "fix" not in ctx.normalized_keywords
    assert "auth" in ctx.expected_domains
    assert ctx.confidence in ("HIGH", "MEDIUM")


def test_task_parser_extracts_explicit_paths():
    parser = TaskParser()
    ctx = parser.parse("Update logic in src/auth/token_manager.py and config/settings.toml")
    assert any("auth/token_manager.py" in p for p in ctx.referenced_paths)
    assert any("config/settings.toml" in p for p in ctx.referenced_paths)
    assert ctx.inferred_scope == "NARROW"
    assert ctx.confidence == "HIGH"


def test_task_parser_extracts_symbols():
    parser = TaskParser()
    ctx = parser.parse("Refactor TokenValidator and verify_signature method")
    assert "TokenValidator" in ctx.referenced_symbols
    assert "verify_signature" in ctx.referenced_symbols


def test_task_parser_domain_inference():
    parser = TaskParser()
    ctx_db = parser.parse("Add new database table column for user entity")
    assert "database" in ctx_db.expected_domains

    ctx_cli = parser.parse("Add new CLI subcommand flag --force")
    assert "cli" in ctx_cli.expected_domains

    ctx_ui = parser.parse("Fix frontend button css theme")
    assert "ui" in ctx_ui.expected_domains


def test_task_parser_empty_input():
    parser = TaskParser()
    ctx = parser.parse("")
    assert ctx.raw_text == ""
    assert len(ctx.normalized_keywords) == 0
    assert ctx.confidence == "LOW"


def test_task_parser_file_input(tmp_path: Path):
    parser = TaskParser()
    task_file = tmp_path / "task.txt"
    task_file.write_text("Implement user password reset endpoint\n", encoding="utf-8")

    ctx = parser.parse_file(task_file)
    assert "password" in ctx.normalized_keywords
    assert "auth" in ctx.expected_domains
