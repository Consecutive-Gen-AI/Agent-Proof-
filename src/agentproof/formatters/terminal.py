"""Human-friendly terminal formatter for verification reports."""

from __future__ import annotations

import sys
from agentproof.core.models import (
    CheckResult,
    CheckStatus,
    FileCategory,
    RiskSeverity,
    RiskWarning,
    Verdict,
    VerificationReport,
)

# ANSI Color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"


def _supports_color(no_color: bool = False) -> bool:
    if no_color:
        return False
    # Standard terminal check
    return sys.stdout.isatty()


def format_terminal_report(report: VerificationReport, no_color: bool = False) -> str:
    """Format a VerificationReport into clean, human-readable terminal output."""
    use_color = _supports_color(no_color)

    def color(text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if use_color else text

    lines: list[str] = []

    # 1. Header
    lines.append("")
    lines.append(color("================================================================", BOLD + CYAN))
    lines.append(color("                       AGENTPROOF V1                           ", BOLD + CYAN))
    lines.append(color("       Independent Evidence & Software Change Verifier         ", DIM + CYAN))
    lines.append(color("================================================================", BOLD + CYAN))
    lines.append("")

    # Repo context
    lines.append(f"{color('Target Directory:', BOLD)} {report.target_dir}")
    if report.git_branch or report.git_commit:
        branch = report.git_branch or "detached"
        commit = report.git_commit[:8] if report.git_commit else "no commits"
        lines.append(f"{color('Git Context:', BOLD)}      branch: {color(branch, CYAN)} | commit: {color(commit, DIM)}")
    lines.append(f"{color('Timestamp:', BOLD)}        {report.timestamp}")
    lines.append("")

    # 2. Change Summary
    cs = report.change_summary
    lines.append(color("--- 1. CHANGE SUMMARY ------------------------------------------", BOLD))
    if cs.total_files == 0:
        lines.append(color("  Working tree is clean. No uncommitted or staged changes.", DIM))
    else:
        sign_add = color(f"+{cs.total_additions}", GREEN)
        sign_del = color(f"-{cs.total_deletions}", RED)
        lines.append(f"  {color(str(cs.total_files), BOLD)} files changed ({sign_add} lines, {sign_del} lines)")

        if cs.categories_count:
            cats = [f"{k.lower()}: {v}" for k, v in sorted(cs.categories_count.items())]
            lines.append(f"  {color('Breakdown:', DIM)} {', '.join(cats)}")

        lines.append("")
        lines.append("  Files:")
        for f in cs.files[:15]:
            status_tag = f"[{f.status.value[:3]}]"
            tag_color = GREEN if f.status.value in ("ADDED", "UNTRACKED") else (RED if f.status.value == "DELETED" else YELLOW)
            lines.append(
                f"    {color(status_tag, tag_color)} {f.path} "
                f"({color('+' + str(f.additions), GREEN)} / {color('-' + str(f.deletions), RED)}) "
                f"{color('[' + f.category.value.lower() + ']', DIM)}"
            )
        if len(cs.files) > 15:
            lines.append(f"    {color(f'... and {len(cs.files) - 15} more files', DIM)}")
    lines.append("")

    # 3. Checks Executed
    lines.append(color("--- 2. INDEPENDENT CHECKS --------------------------------------", BOLD))
    if not report.checks:
        lines.append(color("  No validation checks detected or run.", YELLOW))
    else:
        for c in report.checks:
            badge_color = {
                CheckStatus.PASS: GREEN + BOLD,
                CheckStatus.FAIL: RED + BOLD,
                CheckStatus.TIMEOUT: RED + BOLD,
                CheckStatus.ERROR: RED + BOLD,
                CheckStatus.UNAVAILABLE: YELLOW,
                CheckStatus.SKIPPED: DIM,
            }.get(c.status, WHITE)

            badge = color(f"[{c.status.value}]", badge_color)
            cmd_str = " ".join(c.command) if c.command else "(no command)"
            duration_str = f"{c.duration_ms}ms" if c.status != CheckStatus.UNAVAILABLE else "n/a"

            lines.append(f"  {badge:<18} {color(c.name, BOLD)} ({c.category.value.lower()}) - {duration_str}")
            if c.command:
                lines.append(f"    {color('Command:', DIM)} {cmd_str}")

            if c.status in (CheckStatus.FAIL, CheckStatus.TIMEOUT, CheckStatus.ERROR):
                err_snippet = (c.stderr or c.stdout).strip()
                if err_snippet:
                    lines.append(f"    {color('Failure details:', RED)}")
                    for err_line in err_snippet.splitlines()[:6]:
                        lines.append(f"      {color(err_line, RED)}")
                    if len(err_snippet.splitlines()) > 6:
                        lines.append(f"      {color('... [truncated]', DIM)}")

            elif c.status == CheckStatus.UNAVAILABLE and c.stderr:
                lines.append(f"    {color('Reason:', YELLOW)} {c.stderr}")
    lines.append("")

    # 4. Detected Warnings / Risks
    lines.append(color("--- 3. DETECTED WARNINGS & RISKS --------------------------------", BOLD))
    if not report.warnings:
        lines.append(color("  No risks or anomalous change patterns detected.", GREEN))
    else:
        for w in report.warnings:
            sev_color = {
                RiskSeverity.HIGH: RED + BOLD,
                RiskSeverity.WARNING: YELLOW + BOLD,
                RiskSeverity.INFO: CYAN,
            }.get(w.severity, WHITE)

            badge = color(f"[{w.severity.value}]", sev_color)
            lines.append(f"  {badge:<17} {color(w.code, BOLD)}: {w.message}")
            if w.related_files:
                lines.append(f"    {color('Related files:', DIM)} {', '.join(w.related_files[:5])}")
    lines.append("")

    # 5. Final Verdict Block
    lines.append(color("================================================================", BOLD + CYAN))
    v_color = {
        Verdict.VERIFIED: GREEN + BOLD,
        Verdict.VERIFIED_WITH_WARNINGS: YELLOW + BOLD,
        Verdict.FAILED: RED + BOLD,
        Verdict.ERROR: RED + BOLD,
        Verdict.INCONCLUSIVE: YELLOW + BOLD,
    }.get(report.verdict, WHITE + BOLD)

    lines.append(f"  FINAL VERDICT: {color(report.verdict.value, v_color)}")
    lines.append(f"  Reasoning:     {report.reasoning}")
    lines.append(color("================================================================", BOLD + CYAN))
    lines.append("")

    return "\n".join(lines)
