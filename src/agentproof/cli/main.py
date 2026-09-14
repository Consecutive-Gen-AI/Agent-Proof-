"""Command-line interface for AgentProof."""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path
from typing import List, Optional

from agentproof import __version__
from agentproof.adversarial.generator import AttackGenerator
from agentproof.adversarial.runner import AdversarialRunner
from agentproof.analyzer.change import ChangeAnalyzer
from agentproof.core.models import (
    Verdict,
    VerificationReport,
)
from agentproof.core.verdict import evaluate_verdict
from agentproof.detector.tools import ToolDetector
from agentproof.drift.analyzer import DriftAnalyzer
from agentproof.formatters.json_format import format_json_report
from agentproof.formatters.terminal import (
    format_graph_terminal,
    format_passport_terminal,
    format_terminal_report,
)
from agentproof.git.repo import GitError, GitRepo, NotAGitRepositoryError
from agentproof.graph.builder import ProofGraphBuilder
from agentproof.impact.analyzer import ImpactAnalyzer
from agentproof.missing.analyzer import MissingWorkAnalyzer
from agentproof.integration import AgentContextIngestion, AgentFeedback
from agentproof.passport.generator import PassportGenerator
from agentproof.runner.executor import CheckExecutor
from agentproof.task.context import TaskParser


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
        help="Inspect Git changes, analyze drift and missing work, and run verification checks.",
    )
    _add_verify_arguments(verify_parser)

    # inspect subcommand
    inspect_parser = subparsers.add_parser(
        "inspect",
        help="Inspect Git changes, impact, and missing work without executing test checks.",
    )
    _add_verify_arguments(inspect_parser)

    # passport subcommand (V4)
    passport_parser = subparsers.add_parser(
        "passport",
        help="Generate and inspect a machine-readable Proof Passport.",
    )
    _add_verify_arguments(passport_parser)

    # graph subcommand (V4)
    graph_parser = subparsers.add_parser(
        "graph",
        help="Inspect the Proof Graph connecting tasks, changes, evidence, and verdict.",
    )
    _add_verify_arguments(graph_parser)

    # Also add arguments to root parser so `agentproof verify` flags work at root too
    _add_verify_arguments(parser)

    return parser


def _add_verify_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "-d", "--target-dir",
        default=".",
        help="Target repository directory (default: current working directory).",
    )
    parser.add_argument(
        "-t", "--task",
        default="",
        help="Task description or intent to evaluate scope drift against.",
    )
    parser.add_argument(
        "--task-file",
        default="",
        help="Path to file containing task description.",
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
        "--adversarial",
        action="store_true",
        help="Run deterministic adversarial verification checks against changed behavior.",
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
    parser.add_argument(
        "--agent",
        action="store_true",
        help="Format output as concise, actionable feedback optimized for AI coding agents.",
    )
    parser.add_argument(
        "--agent-input",
        default="",
        help="Path to JSON file (or '-' for stdin) containing structured agent context.",
    )


def _execute_pipeline(
    target_dir: str = ".",
    task_text: str = "",
    task_file: str = "",
    agent_input: str = "",
    staged: bool = False,
    adversarial: bool = False,
    timeout: int = 60,
    skip_checks: bool = False,
) -> tuple[VerificationReport, GitRepo]:
    """Execute the full V1-V6 analysis, check, and adversarial pipeline, returning the report and repo."""
    now_iso = datetime.timezone.utc and datetime.datetime.now(datetime.timezone.utc).isoformat()
    git_repo = GitRepo(target_dir=target_dir)

    # 1. Ingest Agent / Task Context (V3 + V6)
    task_parser = TaskParser()
    agent_ctx = None
    if agent_input:
        agent_ctx = AgentContextIngestion.from_file_or_stdin(agent_input)
    else:
        agent_ctx = AgentContextIngestion.from_env()

    if agent_ctx and (agent_ctx.task_intent or agent_ctx.intended_files):
        task_context = agent_ctx.to_task_context()
    elif task_file:
        task_context = task_parser.parse_file(task_file)
    elif task_text:
        task_context = task_parser.parse(task_text)
    else:
        task_context = None

    # 2. Inspect Git working tree
    branch = git_repo.get_current_branch()
    commit = git_repo.get_head_commit()
    change_summary = git_repo.inspect_changes(staged_only=staged)

    # 3. Static change & risk analysis
    analyzer = ChangeAnalyzer()
    change_summary, warnings = analyzer.analyze(change_summary)

    # 4. Change impact analysis
    impact_analyzer = ImpactAnalyzer(git_repo.root_dir)
    impact = impact_analyzer.analyze(change_summary)

    # 5. Task Drift Analysis (V3)
    drift_analyzer = DriftAnalyzer()
    drift = drift_analyzer.analyze(summary=change_summary, task=task_context, impact=impact)

    # 6. Missing Work Analysis (V3)
    missing_analyzer = MissingWorkAnalyzer()
    missing_work = missing_analyzer.analyze(summary=change_summary, task=task_context, impact=impact)

    # 7. Detect available validation checks
    check_results = []
    if not skip_checks:
        detector = ToolDetector(git_repo.root_dir)
        check_defs = detector.detect_checks()

        # 8. Safely execute checks with commit provenance
        executor = CheckExecutor(cwd=git_repo.root_dir, timeout=timeout, git_commit=commit)
        check_results = executor.run_all(check_defs)

    # 8b. Adversarial verification (V5)
    adversarial_report = None
    if adversarial and not skip_checks:
        generator = AttackGenerator(repo_root=git_repo.root_dir)
        attack_cases = generator.generate_attacks(
            change_summary=change_summary,
            task_context=task_context,
        )
        runner = AdversarialRunner(repo_root=git_repo.root_dir, timeout=min(timeout, 10))
        adversarial_report = runner.run_all(attack_cases)

    # 9. Evaluate final verdict
    if skip_checks:
        verdict = Verdict.INCONCLUSIVE
        reasoning = "Inspection complete. Verification checks were skipped."
    else:
        verdict, reasoning = evaluate_verdict(
            checks=check_results,
            warnings=warnings,
            drift=drift,
            missing_work=missing_work,
            adversarial=adversarial_report,
        )

    # 10. Assemble complete report (Schema 1.2.0 / 1.3.0)
    report = VerificationReport(
        schema_version="1.3.0" if adversarial_report is not None else "1.2.0",
        target_dir=str(git_repo.root_dir),
        git_branch=branch,
        git_commit=commit,
        task_context=task_context,
        change_summary=change_summary,
        impact=impact,
        drift=drift,
        missing_work=missing_work,
        adversarial=adversarial_report,
        checks=check_results,
        warnings=warnings,
        verdict=verdict,
        reasoning=reasoning,
        timestamp=now_iso,
    )

    return report, git_repo


def _handle_git_error(e: Exception, json_output: bool, target_dir: str, error_code: str) -> int:
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    if json_output:
        err_doc = {
            "error": error_code,
            "message": str(e),
            "target_dir": str(Path(target_dir).resolve()),
            "timestamp": now_iso,
        }
        print(json.dumps(err_doc, indent=2))
    else:
        prefix = "Error:" if error_code == "NOT_A_GIT_REPOSITORY" else "Git Error:"
        print(f"{prefix} {e}", file=sys.stderr)
    return 2


def run_verify(
    target_dir: str = ".",
    task_text: str = "",
    task_file: str = "",
    agent_input: str = "",
    staged: bool = False,
    adversarial: bool = False,
    json_output: bool = False,
    no_color: bool = False,
    agent_mode: bool = False,
    timeout: int = 60,
    strict: bool = False,
    skip_checks: bool = False,
) -> int:
    """Run verification and display the structured report or JSON."""
    try:
        report, _ = _execute_pipeline(
            target_dir=target_dir,
            task_text=task_text,
            task_file=task_file,
            agent_input=agent_input,
            staged=staged,
            adversarial=adversarial,
            timeout=timeout,
            skip_checks=skip_checks,
        )
    except NotAGitRepositoryError as e:
        return _handle_git_error(e, json_output, target_dir, "NOT_A_GIT_REPOSITORY")
    except GitError as e:
        return _handle_git_error(e, json_output, target_dir, "GIT_ERROR")

    # Render output for AI agents
    if agent_mode:
        feedback = AgentFeedback.from_report(report)
        if json_output:
            print(json.dumps(feedback.to_dict(), indent=2))
        else:
            print(feedback.to_markdown())
        return feedback.exit_code

    # Render output
    if json_output:
        print(format_json_report(report))
    else:
        print(format_terminal_report(report, no_color=no_color))

    # Return exit status
    if report.verdict in (Verdict.VERIFIED, Verdict.VERIFIED_WITH_WARNINGS):
        return 0
    elif report.verdict in (Verdict.FAILED, Verdict.ERROR, Verdict.BLOCKED):
        return 1
    elif report.verdict == Verdict.INCONCLUSIVE:
        return 1 if strict else 0
    return 1


def run_passport(
    target_dir: str = ".",
    task_text: str = "",
    task_file: str = "",
    agent_input: str = "",
    staged: bool = False,
    adversarial: bool = False,
    json_output: bool = False,
    no_color: bool = False,
    timeout: int = 60,
    strict: bool = False,
) -> int:
    """Run verification, build ProofGraph and ProofPassport, and output the passport."""
    try:
        report, _ = _execute_pipeline(
            target_dir=target_dir,
            task_text=task_text,
            task_file=task_file,
            agent_input=agent_input,
            staged=staged,
            adversarial=adversarial,
            timeout=timeout,
        )
    except NotAGitRepositoryError as e:
        return _handle_git_error(e, json_output, target_dir, "NOT_A_GIT_REPOSITORY")
    except GitError as e:
        return _handle_git_error(e, json_output, target_dir, "GIT_ERROR")

    graph = ProofGraphBuilder(report).build()
    passport = PassportGenerator(report, graph=graph).generate()

    if json_output:
        print(passport.to_json())
    else:
        print(format_passport_terminal(passport, no_color=no_color))

    if report.verdict in (Verdict.VERIFIED, Verdict.VERIFIED_WITH_WARNINGS):
        return 0
    elif report.verdict in (Verdict.FAILED, Verdict.ERROR, Verdict.BLOCKED):
        return 1
    elif report.verdict == Verdict.INCONCLUSIVE:
        return 1 if strict else 0
    return 1


def run_graph(
    target_dir: str = ".",
    task_text: str = "",
    task_file: str = "",
    agent_input: str = "",
    staged: bool = False,
    adversarial: bool = False,
    json_output: bool = False,
    no_color: bool = False,
    timeout: int = 60,
    strict: bool = False,
) -> int:
    """Run verification, construct the ProofGraph, and output graph structure or summary."""
    try:
        report, _ = _execute_pipeline(
            target_dir=target_dir,
            task_text=task_text,
            task_file=task_file,
            agent_input=agent_input,
            staged=staged,
            adversarial=adversarial,
            timeout=timeout,
        )
    except NotAGitRepositoryError as e:
        return _handle_git_error(e, json_output, target_dir, "NOT_A_GIT_REPOSITORY")
    except GitError as e:
        return _handle_git_error(e, json_output, target_dir, "GIT_ERROR")

    graph = ProofGraphBuilder(report).build()

    if json_output:
        print(graph.to_json())
    else:
        print(format_graph_terminal(graph, no_color=no_color))

    if report.verdict in (Verdict.VERIFIED, Verdict.VERIFIED_WITH_WARNINGS):
        return 0
    elif report.verdict in (Verdict.FAILED, Verdict.ERROR, Verdict.BLOCKED):
        return 1
    elif report.verdict == Verdict.INCONCLUSIVE:
        return 1 if strict else 0
    return 1


def main(args: Optional[List[str]] = None) -> None:
    """Main entrypoint for the CLI."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = build_parser()
    parsed_args = parser.parse_args(args)

    command = parsed_args.command or "verify"
    adversarial = getattr(parsed_args, "adversarial", False)
    agent_mode = getattr(parsed_args, "agent", False)
    agent_input = getattr(parsed_args, "agent_input", "")

    if command == "passport":
        exit_code = run_passport(
            target_dir=parsed_args.target_dir,
            task_text=parsed_args.task,
            task_file=parsed_args.task_file,
            agent_input=agent_input,
            staged=parsed_args.staged,
            adversarial=adversarial,
            json_output=parsed_args.json,
            no_color=parsed_args.no_color,
            timeout=parsed_args.timeout,
            strict=parsed_args.strict,
        )
        sys.exit(exit_code)
    elif command == "graph":
        exit_code = run_graph(
            target_dir=parsed_args.target_dir,
            task_text=parsed_args.task,
            task_file=parsed_args.task_file,
            agent_input=agent_input,
            staged=parsed_args.staged,
            adversarial=adversarial,
            json_output=parsed_args.json,
            no_color=parsed_args.no_color,
            timeout=parsed_args.timeout,
            strict=parsed_args.strict,
        )
        sys.exit(exit_code)
    elif command in ("verify", "inspect"):
        exit_code = run_verify(
            target_dir=parsed_args.target_dir,
            task_text=parsed_args.task,
            task_file=parsed_args.task_file,
            agent_input=agent_input,
            staged=parsed_args.staged,
            adversarial=adversarial,
            json_output=parsed_args.json,
            no_color=parsed_args.no_color,
            agent_mode=agent_mode,
            timeout=parsed_args.timeout,
            strict=parsed_args.strict,
            skip_checks=(command == "inspect"),
        )
        sys.exit(exit_code)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()

