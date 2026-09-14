"""Unit tests for deterministic adversarial attack generation."""

from pathlib import Path
from agentproof.adversarial.generator import AttackGenerator
from agentproof.adversarial.models import AttackCategory
from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileChange,
    FileStatus,
    SymbolChange,
    SymbolType,
    TaskContext,
)


def test_generate_attacks_numeric_boundaries(tmp_path: Path):
    src_file = tmp_path / "pricing.py"
    src_file.write_text(
        "def calculate_discount(price, rate):\n"
        "    if price < 0 or rate < 0 or rate > 1:\n"
        "        raise ValueError('Invalid price or rate')\n"
        "    return price * (1 - rate)\n",
        encoding="utf-8",
    )

    change_summary = ChangeSummary(
        files=[
            FileChange(
                path="pricing.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=4,
                deletions=0,
                changed_symbols=[
                    SymbolChange(
                        name="calculate_discount",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=1,
                    )
                ],
            )
        ]
    )

    generator = AttackGenerator(repo_root=tmp_path)
    attacks = generator.generate_attacks(change_summary)

    categories = [a.category for a in attacks]
    assert AttackCategory.BOUNDARY_VALUE in categories or AttackCategory.MINIMUM_VALUE in categories
    assert any(a.target_symbol == "calculate_discount" for a in attacks)
    for a in attacks:
        assert a.rationale
        assert a.execution_snippet
        assert a.expected_behavior


def test_generate_attacks_null_and_empty(tmp_path: Path):
    src_file = tmp_path / "parser.py"
    src_file.write_text(
        "def parse_header(line, delim):\n"
        "    if line is None or delim is None:\n"
        "        raise TypeError('Inputs cannot be None')\n"
        "    return line.split(delim)\n",
        encoding="utf-8",
    )

    change_summary = ChangeSummary(
        files=[
            FileChange(
                path="parser.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=4,
                deletions=0,
                changed_symbols=[
                    SymbolChange(
                        name="parse_header",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=1,
                    )
                ],
            )
        ]
    )

    generator = AttackGenerator(repo_root=tmp_path)
    attacks = generator.generate_attacks(change_summary)

    categories = [a.category for a in attacks]
    assert AttackCategory.NULL_OR_NONE_INPUT in categories
    assert AttackCategory.EMPTY_INPUT in categories


def test_generate_attacks_auth_and_security(tmp_path: Path):
    src_file = tmp_path / "auth.py"
    src_file.write_text(
        "def verify_token(token, role):\n"
        "    if not token or role != 'admin':\n"
        "        return False\n"
        "    return True\n",
        encoding="utf-8",
    )

    change_summary = ChangeSummary(
        files=[
            FileChange(
                path="auth.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=4,
                deletions=0,
                changed_symbols=[
                    SymbolChange(
                        name="verify_token",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=1,
                    )
                ],
            )
        ]
    )

    generator = AttackGenerator(repo_root=tmp_path)
    attacks = generator.generate_attacks(change_summary)

    categories = [a.category for a in attacks]
    assert AttackCategory.PERMISSION_OR_AUTH_EDGE_CASE in categories
    assert AttackCategory.MALFORMED_INPUT in categories


def test_generate_attacks_error_path(tmp_path: Path):
    src_file = tmp_path / "payment.py"
    src_file.write_text(
        "def process_payment(account_id, amount):\n"
        "    if amount <= 0:\n"
        "        raise ValueError('Amount must be positive')\n"
        "    return f'Charged {amount} to {account_id}'\n",
        encoding="utf-8",
    )

    change_summary = ChangeSummary(
        files=[
            FileChange(
                path="payment.py",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=4,
                deletions=0,
                changed_symbols=[
                    SymbolChange(
                        name="process_payment",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=1,
                    )
                ],
            )
        ]
    )

    generator = AttackGenerator(repo_root=tmp_path)
    attacks = generator.generate_attacks(change_summary)

    categories = [a.category for a in attacks]
    assert AttackCategory.ERROR_PATH in categories or AttackCategory.BOUNDARY_VALUE in categories


def test_generate_attacks_no_suitable_targets(tmp_path: Path):
    # Only doc files modified
    change_summary = ChangeSummary(
        files=[
            FileChange(
                path="README.md",
                status=FileStatus.MODIFIED,
                category=FileCategory.DOCUMENTATION,
                additions=5,
                deletions=1,
            )
        ]
    )

    generator = AttackGenerator(repo_root=tmp_path)
    attacks = generator.generate_attacks(change_summary)
    assert len(attacks) == 0


def test_generate_attacks_multi_language_targets(tmp_path: Path):
    # Go file modified
    go_file = tmp_path / "server.go"
    go_file.write_text(
        "package main\n\nfunc HandleRequest(req string) string {\n    return req\n}\n",
        encoding="utf-8",
    )

    change_summary = ChangeSummary(
        files=[
            FileChange(
                path="server.go",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=5,
                deletions=0,
                changed_symbols=[
                    SymbolChange(
                        name="HandleRequest",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=3,
                    )
                ],
            )
        ]
    )

    generator = AttackGenerator(repo_root=tmp_path)
    attacks = generator.generate_attacks(change_summary)

    assert len(attacks) == 1
    assert attacks[0].target_symbol == "HandleRequest"
    assert attacks[0].status == "NOT_APPLICABLE"
    assert "go changes" in attacks[0].rationale

