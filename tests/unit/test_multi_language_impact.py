"""Unit tests verifying multi-language impact analysis across TypeScript, Go, Rust, and Java."""

from pathlib import Path

from agentproof.core.models import (
    ChangeSummary,
    FileCategory,
    FileChange,
    FileStatus,
    SymbolChange,
    SymbolType,
)
from agentproof.impact.analyzer import ImpactAnalyzer


def test_typescript_impact_analysis(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()

    calc_file = src_dir / "calc.ts"
    calc_file.write_text("export function multiply(a: number, b: number) { return a * b; }\n", encoding="utf-8")

    app_file = src_dir / "app.ts"
    app_file.write_text("import { multiply } from './calc';\nconsole.log(multiply(2, 3));\n", encoding="utf-8")

    test_file = src_dir / "calc.test.ts"
    test_file.write_text("import { multiply } from './calc';\ntest('mult', () => expect(multiply(2, 2)).toBe(4));\n", encoding="utf-8")

    summary = ChangeSummary(
        files=[
            FileChange(
                path="src/calc.ts",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=1,
                deletions=1,
                changed_symbols=[
                    SymbolChange(
                        name="multiply",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=1,
                    )
                ],
            )
        ]
    )

    analyzer = ImpactAnalyzer(root_dir=tmp_path)
    impact = analyzer.analyze(summary)

    impacted_srcs = [s.file_path.replace("\\", "/") for s in impact.impacted_source_files]
    assert any("src/app.ts" in s for s in impacted_srcs)

    # Must detect calc.test.ts as impacted test
    impacted_tests = [t.file_path.replace("\\", "/") for t in impact.impacted_test_files]
    assert any("src/calc.test.ts" in t for t in impacted_tests)


def test_go_impact_analysis(tmp_path: Path):
    auth_file = tmp_path / "auth.go"
    auth_file.write_text("package auth\n\nfunc ValidateToken(t string) bool { return t != \"\" }\n", encoding="utf-8")

    handler_file = tmp_path / "handler.go"
    handler_file.write_text("package auth\n\nfunc Login(t string) bool {\n    return ValidateToken(t)\n}\n", encoding="utf-8")

    test_file = tmp_path / "auth_test.go"
    test_file.write_text("package auth\nimport \"testing\"\nfunc TestAuth(t *testing.T) { ValidateToken(\"abc\") }\n", encoding="utf-8")

    summary = ChangeSummary(
        files=[
            FileChange(
                path="auth.go",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=2,
                deletions=0,
                changed_symbols=[
                    SymbolChange(
                        name="ValidateToken",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=3,
                    )
                ],
            )
        ]
    )

    analyzer = ImpactAnalyzer(root_dir=tmp_path)
    impact = analyzer.analyze(summary)

    impacted_srcs = [s.file_path.replace("\\", "/") for s in impact.impacted_source_files]
    assert any("handler.go" in s for s in impacted_srcs)

    impacted_tests = [t.file_path.replace("\\", "/") for t in impact.impacted_test_files]
    assert any("auth_test.go" in t for t in impacted_tests)


def test_java_impact_analysis(tmp_path: Path):
    pkg_dir = tmp_path / "src" / "main" / "java"
    pkg_dir.mkdir(parents=True)
    svc_file = pkg_dir / "PaymentService.java"
    svc_file.write_text(
        "package java;\npublic class PaymentService {\n    public static boolean process(double amt) { return amt > 0; }\n}\n",
        encoding="utf-8",
    )

    app_file = pkg_dir / "MainApp.java"
    app_file.write_text(
        "package java;\npublic class MainApp {\n    public static void main(String[] args) {\n        PaymentService.process(100.0);\n    }\n}\n",
        encoding="utf-8",
    )

    test_dir = tmp_path / "src" / "test" / "java"
    test_dir.mkdir(parents=True)
    test_file = test_dir / "PaymentServiceTest.java"
    test_file.write_text(
        "package java;\npublic class PaymentServiceTest {\n    public void testProcess() { PaymentService.process(50); }\n}\n",
        encoding="utf-8",
    )

    summary = ChangeSummary(
        files=[
            FileChange(
                path="src/main/java/PaymentService.java",
                status=FileStatus.MODIFIED,
                category=FileCategory.SOURCE,
                additions=1,
                deletions=1,
                changed_symbols=[
                    SymbolChange(
                        name="process",
                        symbol_type=SymbolType.FUNCTION,
                        change_type="MODIFIED",
                        line_number=3,
                    )
                ],
            )
        ]
    )

    analyzer = ImpactAnalyzer(root_dir=tmp_path)
    impact = analyzer.analyze(summary)

    impacted_srcs = [s.file_path.replace("\\", "/") for s in impact.impacted_source_files]
    assert any("MainApp.java" in s for s in impacted_srcs)

    impacted_tests = [t.file_path.replace("\\", "/") for t in impact.impacted_test_files]
    assert any("PaymentServiceTest.java" in t for t in impacted_tests)
