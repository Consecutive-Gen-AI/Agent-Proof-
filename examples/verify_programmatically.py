"""Example: Programmatic verification and proof passport generation with AgentProof."""

from pathlib import Path
from agentproof.git.repo import GitRepo
from agentproof.analyzer.change import ChangeAnalyzer
from agentproof.impact.analyzer import ImpactAnalyzer
from agentproof.core.models import VerificationReport
from agentproof.core.verdict import evaluate_verdict
from agentproof.graph.builder import ProofGraphBuilder
from agentproof.passport.generator import PassportGenerator


def main() -> None:
    # 1. Target the current repository
    repo_root = Path(__file__).resolve().parent.parent
    git_repo = GitRepo(target_dir=str(repo_root))

    print(f"Inspecting repository at: {repo_root}")
    print(f"Current branch: {git_repo.get_current_branch()}")
    print(f"HEAD commit: {git_repo.get_head_commit()[:8] if git_repo.get_head_commit() else 'None'}")

    # 2. Inspect working tree changes
    change_summary = git_repo.inspect_changes()
    print(f"Changed files: {change_summary.total_files} (+{change_summary.total_additions}/-{change_summary.total_deletions})")

    # 3. Static change analysis & risk findings
    analyzer = ChangeAnalyzer()
    change_summary, warnings = analyzer.analyze(change_summary)
    print(f"Risk warnings identified: {len(warnings)}")

    # 4. Change impact mapping
    impact_analyzer = ImpactAnalyzer(repo_root)
    impact = impact_analyzer.analyze(change_summary)
    print(f"Impact rating: {impact.total_impact_score}")

    # 5. Evaluate verdict (no checks executed in inspection-only demo)
    verdict, reasoning = evaluate_verdict(
        checks=[],
        warnings=warnings,
        drift=None,
        missing_work=None,
        adversarial=None,
    )
    print(f"Evaluation verdict: {verdict.value}")

    # 6. Build report and Proof Passport
    report = VerificationReport(
        schema_version="1.2.0",
        target_dir=str(repo_root),
        git_branch=git_repo.get_current_branch(),
        git_commit=git_repo.get_head_commit(),
        change_summary=change_summary,
        impact=impact,
        verdict=verdict,
        reasoning=reasoning,
    )

    graph = ProofGraphBuilder(report).build()
    passport = PassportGenerator(report=report, graph=graph).generate()

    print(f"\nGenerated Proof Passport:")
    print(f"  Passport ID:     {passport.passport_id}")
    print(f"  Status:          {passport.verdict.status}")
    print(f"  Integrity SHA:   {passport.metadata.passport_integrity_hash[:16]}...")


if __name__ == "__main__":
    main()
