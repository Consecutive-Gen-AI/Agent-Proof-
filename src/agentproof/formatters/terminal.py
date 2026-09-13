"""Human-friendly terminal formatter for V2 verification reports."""

from __future__ import annotations

import sys
from agentproof.core.models import (
    CheckResult,
    CheckStatus,
    FileCategory,
    RiskSeverity,
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
    return sys.stdout.isatty()


def format_terminal_report(report: VerificationReport, no_color: bool = False) -> str:
    """Format a VerificationReport into clean, 6-section human-readable terminal output."""
    use_color = _supports_color(no_color)

    def color(text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if use_color else text

    lines: list[str] = []

    # Banner Header
    lines.append("")
    lines.append(color("================================================================", BOLD + CYAN))
    lines.append(color("                       AGENTPROOF V2                           ", BOLD + CYAN))
    lines.append(color("        Evidence & Change Impact Verification Engine            ", DIM + CYAN))
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

    # =========================================================================
    # SECTION 1: CHANGE (Repository Facts)
    # =========================================================================
    cs = report.change_summary
    lines.append(color("--- 1. CHANGE (Repository Facts) -------------------------------", BOLD))
    if cs.total_files == 0:
        lines.append(color("  Working tree is clean. No uncommitted or staged changes.", DIM))
    else:
        sign_add = color(f"+{cs.total_additions}", GREEN)
        sign_del = color(f"-{cs.total_deletions}", RED)
        lines.append(f"  Total Changes: {color(str(cs.total_files), BOLD)} files ({sign_add} lines, {sign_del} lines)")

        # Staged vs Unstaged breakdown
        stg_summary = f"{cs.staged_files_count} files ({color('+' + str(cs.staged_additions), GREEN)} / {color('-' + str(cs.staged_deletions), RED)})"
        uns_summary = f"{cs.unstaged_files_count} files ({color('+' + str(cs.unstaged_additions), GREEN)} / {color('-' + str(cs.unstaged_deletions), RED)})"
        lines.append(f"  Stage State:   Staged: {stg_summary} | Unstaged: {uns_summary}")

        if cs.categories_count:
            cats = [f"{k.lower()}: {v}" for k, v in sorted(cs.categories_count.items())]
            lines.append(f"  Categories:    {', '.join(cats)}")

        lines.append("")
        lines.append("  Changed Files:")
        for f in cs.files[:15]:
            status_tag = f"[{f.status.value[:3]}]"
            tag_color = GREEN if f.status.value in ("ADDED", "UNTRACKED") else (RED if f.status.value == "DELETED" else YELLOW)

            stage_indicator = ""
            if f.is_staged and f.is_unstaged:
                stage_indicator = color("[stg+uns]", CYAN)
            elif f.is_staged:
                stage_indicator = color("[staged]", CYAN)
            elif f.is_unstaged:
                stage_indicator = color("[unstaged]", DIM)

            # Display rename mapping
            path_display = f"{f.old_path} -> {f.path}" if f.old_path else f.path

            lines.append(
                f"    {color(status_tag, tag_color)} {path_display} "
                f"({color('+' + str(f.additions), GREEN)} / {color('-' + str(f.deletions), RED)}) "
                f"{stage_indicator} {color('[' + f.category.value.lower() + ']', DIM)}"
            )

            # Show changed symbols if extracted
            if f.changed_symbols:
                sym_names = [f"{s.name} ({s.symbol_type.value.lower()})" for s in f.changed_symbols[:4]]
                if len(f.changed_symbols) > 4:
                    sym_names.append(f"+{len(f.changed_symbols) - 4} more")
                lines.append(f"       {color('Symbols:', DIM)} {', '.join(sym_names)}")

        if len(cs.files) > 15:
            lines.append(f"    {color(f'... and {len(cs.files) - 15} more files', DIM)}")
    lines.append("")

    # =========================================================================
    # SECTION 2: IMPACT (Change Impact Analysis)
    # =========================================================================
    lines.append(color("--- 2. IMPACT (Change Impact Analysis) -------------------------", BOLD))
    impact = report.impact
    if not impact or (not impact.impacted_source_files and not impact.impacted_test_files and not impact.impacted_configs):
        lines.append(color("  No dependent components or callers impacted outside changed files.", DIM))
    else:
        score_color = {
            "LOW": GREEN,
            "MEDIUM": YELLOW + BOLD,
            "HIGH": RED + BOLD,
        }.get(impact.total_impact_score, WHITE)

        lines.append(f"  Impact Rating: {color('[' + impact.total_impact_score + ']', score_color)}")
        if impact.changed_modules:
            lines.append(f"  Target Modules: {', '.join(impact.changed_modules[:8])}")

        if impact.impacted_source_files:
            lines.append(f"  {color('Impacted Source Callers / Dependents (' + str(len(impact.impacted_source_files)) + '):', BOLD)}")
            for comp in impact.impacted_source_files[:5]:
                lines.append(f"    -> {comp.file_path} {color('(' + comp.description + ')', DIM)}")
            if len(impact.impacted_source_files) > 5:
                lines.append(f"       {color(f'... and {len(impact.impacted_source_files) - 5} more callers', DIM)}")

        if impact.impacted_test_files:
            lines.append(f"  {color('Related Test Suites (' + str(len(impact.impacted_test_files)) + '):', BOLD)}")
            for comp in impact.impacted_test_files[:5]:
                lines.append(f"    -> {comp.file_path} {color('(' + comp.description + ')', DIM)}")

        if impact.untested_impacts:
            lines.append(f"  {color('Untested Impact Callers:', YELLOW)}")
            for unt in impact.untested_impacts[:3]:
                lines.append(f"    ! {unt}")
    lines.append("")

    # =========================================================================
    # SECTION 3: CHECKS (Validation Execution)
    # =========================================================================
    lines.append(color("--- 3. CHECKS (Validation Execution) ---------------------------", BOLD))
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
            if c.output_summary:
                lines.append(f"    {color('Result:', DIM)} {c.output_summary}")
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

    # =========================================================================
    # SECTION 4: RISKS & FINDINGS (AgentProof Analysis)
    # =========================================================================
    lines.append(color("--- 4. RISKS & FINDINGS (AgentProof Analysis) -----------------", BOLD))
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
            lines.append(f"  {badge:<17} {color(w.code, BOLD)}")
            what_desc = w.what_was_detected or w.message
            lines.append(f"    {color('What was detected:', BOLD)} {what_desc}")
            if w.why_it_matters:
                lines.append(f"    {color('Why it matters:', BOLD)}    {w.why_it_matters}")
            if w.evidence:
                lines.append(f"    {color('Evidence:', BOLD)}          {'; '.join(w.evidence[:4])}")
            elif w.related_files:
                lines.append(f"    {color('Related files:', DIM)}     {', '.join(w.related_files[:5])}")
            lines.append("")
    lines.append("")

    # =========================================================================
    # SECTION 5: EVIDENCE (Facts & Provenance)
    # =========================================================================
    lines.append(color("--- 5. EVIDENCE (Facts & Provenance) --------------------------", BOLD))
    lines.append(f"  Repo Revision: {report.git_commit or 'working tree uncommitted'}")
    lines.append(f"  Schema:        AgentProof Evidence v{report.schema_version}")
    lines.append(f"  Checks Total:  {len(report.checks)} (Passed: {sum(1 for c in report.checks if c.status == CheckStatus.PASS)}, Failed: {sum(1 for c in report.checks if c.status in (CheckStatus.FAIL, CheckStatus.TIMEOUT))})")
    for c in report.checks:
        lines.append(f"    - {c.name}: {c.status.value} (exit code {c.exit_code}, {c.duration_ms}ms)")
    lines.append("")

    # =========================================================================
    # SECTION 6: VERDICT
    # =========================================================================
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
