"""Command-line interface for AgentProof."""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional

from agentproof import __version__
from agentproof.analyzer.change import ChangeAnalyzer
from agentproof.core.models import (
    ChangeSummary,
    Verdict,
    VerificationReport,
)
from agentproof.core.verdict import evaluate_verdict
from agentproof.detector.tools import ToolDetector
from agentproof.formatters.json_format import format_json_report
from agentproof.formatters.terminal import format_terminal_report
from agentproof.git.repo import GitError, GitRepo, NotAGitRepositoryError
from agentproof.runner.executor import CheckExecutor


def build_parser() -> argparse.ArgumentParser:
    """Construct command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="agentproof",
        description="AgentProof: An agent-agnostic verification and evidence layer for software changes.",
    )
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"agentproof {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # verify subcommand
    verify_parser = subparsers.add_parser(
        "verify",
        help="Inspect Git changes and run independent verification checks.",
    )
    _add_verify_arguments(verify_parser)

    # Also add arguments to the root parser so `agentproof --json` works as a shortcut for `agentproof verify --json`
    _add_verify_arguments(parser)

    return parser


def _add_verify_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-d", "--target-dir",
        default=".",
        help="Target repository directory (default: current working directory).",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Inspect only staged changes instead of the entire working tree.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output structured verification results as JSON.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable ANSI color output in terminal.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=60,
        help="Execution timeout per check in seconds (default: 60).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat INCONCLUSIVE verdicts as non-zero exit codes in CI.",
    )


def run_verify(
    target_dir: str = ".",
    staged: bool = False,
    json_output: bool = False,
    no_color: bool = False,
    timeout: int = 60,
    strict: bool = False,
) -> int:
    """
    Core verification pipeline:
    1. Inspect Git repository
    2. Analyze changes & detect risks
    3. Detect available validation tools
    4. Safely execute checks
    5. Evaluate verdict
    6. Output report
    """
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        git_repo = GitRepo(target_dir=target_dir)
    except NotAGitRepositoryError as e:
        if json_output:
            err_doc = {
                "error": "NOT_A_GIT_REPOSITORY",
                "message": str(e),
                "target_dir": str(Path(target_dir).resolve()),
                "timestamp": now_iso,
            }
            print(json.dumps(err_doc, indent=2))
        else:
            print(f"Error: {e}", file=sys.stderr)
        return 2
    except GitError as e:
        if json_output:
            err_doc = {
                "error": "GIT_ERROR",
                "message": str(e),
                "target_dir": str(Path(target_dir).resolve()),
                "timestamp": now_iso,
            }
            print(json.dumps(err_doc, indent=2))
        else:
            print(f"Git Error: {e}", file=sys.stderr)
        return 2

    # 1. Inspect Git working tree
    branch = git_repo.get_current_branch()
    commit = git_repo.get_head_commit()
    change_summary = git_repo.inspect_changes(staged_only=staged)

    # 2. Static change & risk analysis
    analyzer = ChangeAnalyzer()
    change_summary, warnings = analyzer.analyze(change_summary)

    # 3. Detect available validation checks
    detector = ToolDetector(git_repo.root_dir)
    check_defs = detector.detect_checks()

    # 4. Safely execute checks
    executor = CheckExecutor(cwd=git_repo.root_dir, timeout=timeout)
    check_results = executor.run_all(check_defs)

    # 5. Evaluate final verdict
    verdict, reasoning = evaluate_verdict(checks=check_results, warnings=warnings)

    # 6. Assemble complete report
    report = VerificationReport(
        schema_version="1.0.0",
        target_dir=str(git_repo.root_dir),
        git_branch=branch,
        git_commit=commit,
        change_summary=change_summary,
        checks=check_results,
        warnings=warnings,
        verdict=verdict,
        reasoning=reasoning,
        timestamp=now_iso,
    )

    # 7. Render output
    if json_output:
        print(format_json_report(report))
    else:
        print(format_terminal_report(report, no_color=no_color))

    # 8. Return exit status
    if verdict in (Verdict.VERIFIED, Verdict.VERIFIED_WITH_WARNINGS):
        return 0
    elif verdict in (Verdict.FAILED, Verdict.ERROR):
        return 1
    elif verdict == Verdict.INCONCLUSIVE:
        return 1 if strict else 0
    return 1


def main(args: Optional[List[str]] = None) -> None:
    """Main entrypoint for the CLI."""
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    # Default command is 'verify'
    command = parsed_args.command or "verify"

    if command == "verify":
        exit_code = run_verify(
            target_dir=parsed_args.target_dir,
            staged=parsed_args.staged,
            json_output=parsed_args.json,
            no_color=parsed_args.no_color,
            timeout=parsed_args.timeout,
            strict=parsed_args.strict,
        )
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
