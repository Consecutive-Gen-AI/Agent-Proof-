"""Human-friendly terminal formatter for V3 verification reports."""

from __future__ import annotations

import sys
from agentproof.core.models import (
    CheckResult,
    CheckStatus,
    DriftLevel,
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
    """Format a VerificationReport into clean, 8-section human-readable terminal output."""
    use_color = _supports_color(no_color)

    def color(text: str, code: str) -> str:
        return f"{code}{text}{RESET}" if use_color else text

    lines: list[str] = []

    # Banner Header
    lines.append("")
    lines.append(color("================================================================", BOLD + CYAN))
    lines.append(color("                       AGENTPROOF V3                           ", BOLD + CYAN))
    lines.append(color("    Verification, Drift Detection & Missing Work Engine         ", DIM + CYAN))
    lines.append(color("================================================================", BOLD + CYAN))
    lines.append("")

    # Repo and Task context
    lines.append(f"{color('Target Directory:', BOLD)} {report.target_dir}")
    if report.git_branch or report.git_commit:
        branch = report.git_branch or "detached"
        commit = report.git_commit[:8] if report.git_commit else "no commits"
        lines.append(f"{color('Git Context:', BOLD)}      branch: {color(branch, CYAN)} | commit: {color(commit, DIM)}")
    if report.task_context and report.task_context.raw_text:
        lines.append(f"{color('Task Intent:', BOLD)}     \"{color(report.task_context.raw_text, BOLD)}\" (scope: {report.task_context.inferred_scope.lower()})")
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

        stg_summary = f"{cs.staged_files_count} files ({color('+' + str(cs.staged_additions), GREEN)} / {color('-' + str(cs.staged_deletions), RED)})"
        uns_summary = f"{cs.unstaged_files_count} files ({color('+' + str(cs.unstaged_additions), GREEN)} / {color('-' + str(cs.unstaged_deletions), RED)})"
        lines.append(f"  Stage State:   Staged: {stg_summary} | Unstaged: {uns_summary}")

        if cs.categories_count:
            cats = [f"{k.lower()}: {v}" for k, v in sorted(cs.categories_count.items())]
            lines.append(f"  Categories:    {', '.join(cats)}")

        lines.append("")
        lines.append("  Changed Files:")
        for f in cs.files[:12]:
            status_tag = f"[{f.status.value[:3]}]"
            tag_color = GREEN if f.status.value in ("ADDED", "UNTRACKED") else (RED if f.status.value == "DELETED" else YELLOW)

            stage_indicator = ""
            if f.is_staged and f.is_unstaged:
                stage_indicator = color("[stg+uns]", CYAN)
            elif f.is_staged:
                stage_indicator = color("[staged]", CYAN)
            elif f.is_unstaged:
                stage_indicator = color("[unstaged]", DIM)

            path_display = f"{f.old_path} -> {f.path}" if f.old_path else f.path

            lines.append(
                f"    {color(status_tag, tag_color)} {path_display} "
                f"({color('+' + str(f.additions), GREEN)} / {color('-' + str(f.deletions), RED)}) "
                f"{stage_indicator} {color('[' + f.category.value.lower() + ']', DIM)}"
            )

            if f.changed_symbols:
                sym_names = [f"{s.name} ({s.symbol_type.value.lower()})" for s in f.changed_symbols[:3]]
                if len(f.changed_symbols) > 3:
                    sym_names.append(f"+{len(f.changed_symbols) - 3} more")
                lines.append(f"       {color('Symbols:', DIM)} {', '.join(sym_names)}")

        if len(cs.files) > 12:
            lines.append(f"    {color(f'... and {len(cs.files) - 12} more files', DIM)}")
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
            lines.append(f"  Target Modules: {', '.join(impact.changed_modules[:6])}")

        if impact.impacted_source_files:
            lines.append(f"  {color('Impacted Source Callers / Dependents (' + str(len(impact.impacted_source_files)) + '):', BOLD)}")
            for comp in impact.impacted_source_files[:4]:
                lines.append(f"    -> {comp.file_path} {color('(' + comp.description + ')', DIM)}")
            if len(impact.impacted_source_files) > 4:
                lines.append(f"       {color(f'... and {len(impact.impacted_source_files) - 4} more callers', DIM)}")

        if impact.impacted_test_files:
            lines.append(f"  {color('Related Test Suites (' + str(len(impact.impacted_test_files)) + '):', BOLD)}")
            for comp in impact.impacted_test_files[:4]:
                lines.append(f"    -> {comp.file_path} {color('(' + comp.description + ')', DIM)}")
    lines.append("")

    # =========================================================================
    # SECTION 3: DRIFT (Task-to-Change Drift Analysis)
    # =========================================================================
    lines.append(color("--- 3. DRIFT (Task-to-Change Drift Analysis) -------------------", BOLD))
    drift = report.drift
    if not drift or drift.drift_level == DriftLevel.UNKNOWN:
        lines.append(color("  Task context was not supplied. Run with `--task \"<desc>\"` to enable drift analysis.", DIM))
    else:
        drift_color = {
            DriftLevel.NONE: GREEN + BOLD,
            DriftLevel.LOW: GREEN,
            DriftLevel.MEDIUM: YELLOW + BOLD,
            DriftLevel.HIGH: RED + BOLD,
        }.get(drift.drift_level, WHITE)

        lines.append(f"  Drift Level:   {color('[' + drift.drift_level.value + ']', drift_color)} (confidence: {drift.confidence.lower()})")
        lines.append(f"  Summary:       {drift.summary}")

        if drift.unexpected_files:
            lines.append(f"  {color('Unexpected Modifications Outside Scope (' + str(len(drift.unexpected_files)) + '):', RED + BOLD)}")
            for df in drift.findings[:4]:
                lines.append(f"    ! {color(df.file_path, RED)}")
                lines.append(f"      {color('Why drift:', DIM)} {df.why_it_was_considered_drift}")
            if len(drift.findings) > 4:
                lines.append(f"      {color(f'... and {len(drift.findings) - 4} more unexpected files', DIM)}")
        else:
            lines.append(color("  All changes strictly align with intended task scope.", GREEN))
    lines.append("")

    # =========================================================================
    # SECTION 4: MISSING WORK (Omission & Gap Detection)
    # =========================================================================
    lines.append(color("--- 4. MISSING WORK (Omission & Gap Detection) -----------------", BOLD))
    mw = report.missing_work
    if not mw or mw.findings_count == 0:
        lines.append(color("  No omitted engineering work or verification gaps detected.", GREEN))
    else:
        lines.append(f"  Gaps Detected: {color(str(mw.findings_count), YELLOW + BOLD)} item(s)")
        for finding in mw.findings[:5]:
            badge_color = RED + BOLD if finding.severity == RiskSeverity.HIGH else YELLOW + BOLD
            lines.append(f"  {color('[' + finding.code + ']', badge_color)}: {finding.title}")
            lines.append(f"    {color('What:', BOLD)} {finding.what_was_detected}")
            lines.append(f"    {color('Why:', BOLD)}  {finding.why_it_matters}")
            if finding.evidence:
                lines.append(f"    {color('Evidence:', DIM)} {'; '.join(finding.evidence[:3])}")
            lines.append("")
    lines.append("")

    # =========================================================================
    # SECTION 5: CHECKS (Validation Execution)
    # =========================================================================
    lines.append(color("--- 5. CHECKS (Validation Execution) ---------------------------", BOLD))
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
                    for err_line in err_snippet.splitlines()[:4]:
                        lines.append(f"      {color(err_line, RED)}")
    lines.append("")

    # =========================================================================
    # SECTION 6: RISKS & FINDINGS (AgentProof Analysis)
    # =========================================================================
    lines.append(color("--- 6. RISKS & FINDINGS (AgentProof Analysis) -----------------", BOLD))
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
            lines.append(f"    {color('What was detected:', BOLD)} {w.what_was_detected or w.message}")
            if w.why_it_matters:
                lines.append(f"    {color('Why it matters:', BOLD)}    {w.why_it_matters}")
            if w.evidence:
                lines.append(f"    {color('Evidence:', BOLD)}          {'; '.join(w.evidence[:3])}")
            lines.append("")
    lines.append("")

    # =========================================================================
    # SECTION 7: EVIDENCE (Facts & Provenance)
    # =========================================================================
    lines.append(color("--- 7. EVIDENCE (Facts & Provenance) --------------------------", BOLD))
    lines.append(f"  Repo Revision: {report.git_commit or 'working tree uncommitted'}")
    lines.append(f"  Schema:        AgentProof Evidence v{report.schema_version}")
    lines.append(f"  Checks Total:  {len(report.checks)} (Passed: {sum(1 for c in report.checks if c.status == CheckStatus.PASS)}, Failed: {sum(1 for c in report.checks if c.status in (CheckStatus.FAIL, CheckStatus.TIMEOUT))})")
    for c in report.checks:
        lines.append(f"    - {c.name}: {c.status.value} (exit code {c.exit_code}, {c.duration_ms}ms)")
    lines.append("")

    # =========================================================================
    # SECTION 8: FINAL VERDICT
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
