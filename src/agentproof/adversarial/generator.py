"""Deterministic adversarial test case generator for changed code."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentproof.adversarial.models import (
    AttackCase,
    AttackCategory,
    AttackResultStatus,
)
from agentproof.core.models import ChangeSummary, FileCategory, FileChange, SymbolChange


from agentproof.structure import StructureEngine, SupportedLanguage, SymbolKind


class AttackGenerator:
    """Generates deterministic adversarial attack cases targeting changed functions and symbols."""

    def __init__(self, repo_root: Optional[Path] = None, engine: Optional[StructureEngine] = None):
        self.repo_root = Path(repo_root) if repo_root else Path(".")
        self.engine = engine or StructureEngine()

    def generate_attacks(
        self,
        summary: Optional[ChangeSummary] = None,
        task_context: Optional[Any] = None,
        **kwargs: Any,
    ) -> List[AttackCase]:
        """Generate attack cases for changed functions across source files."""
        if summary is None and "change_summary" in kwargs:
            summary = kwargs["change_summary"]
        if summary is None:
            return []

        attacks: List[AttackCase] = []

        for fc in summary.files:
            if fc.category != FileCategory.SOURCE:
                continue

            file_path = self.repo_root / fc.path
            if not file_path.exists():
                continue

            # Multi-language target discovery for non-Python source files
            if not fc.path.endswith(".py"):
                fs = self.engine.analyze_file(file_path, fc.path)
                if fs.language != SupportedLanguage.UNSUPPORTED:
                    target_symbols = [s.name for s in fc.changed_symbols]
                    for sym in fs.symbols:
                        if sym.kind in (SymbolKind.FUNCTION, SymbolKind.METHOD):
                            if target_symbols and sym.name not in target_symbols:
                                continue
                            if not sym.is_public:
                                continue
                            attacks.append(AttackCase(
                                id=f"atk:{fc.path}:{sym.name}:target_discovery",
                                category=AttackCategory.BOUNDARY_VALUE,
                                target_file=fc.path,
                                target_symbol=sym.name,
                                rationale=f"Function '{sym.name}' identified in {fs.language.value} changes; execution sandbox unavailable in current runner.",
                                test_input=None,
                                expected_behavior="Requires language-specific test runner",
                                execution_code="",
                                result=AttackResultStatus.NOT_APPLICABLE,
                            ))
                continue

            try:
                content = file_path.read_text(encoding="utf-8", errors="replace")
                tree = ast.parse(content, filename=fc.path)
            except Exception:
                continue

            # Identify target functions from changed symbols or all top-level functions in modified file
            target_symbols = [s.name for s in fc.changed_symbols]
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # If symbols are identified, prioritize them; otherwise target functions in file
                    if target_symbols and node.name not in target_symbols:
                        continue
                    # Skip private and internal functions/methods starting with _
                    if node.name.startswith("_"):
                        continue

                    func_attacks = self._generate_for_function(fc.path, node)
                    attacks.extend(func_attacks)

        return attacks

    def _generate_for_function(self, file_path: str, func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> List[AttackCase]:
        """Generate attack cases targeting a specific function's parameters and domain."""
        cases: List[AttackCase] = []
        func_name = func_node.name
        module_import_path = self._file_to_module(file_path)

        arg_names = [a.arg for a in func_node.args.args if a.arg != "self" and a.arg != "cls"]

        if not arg_names:
            # Function takes 0 arguments: generate unexpected argument attack
            case_id = f"atk:{file_path}:{func_name}:unexpected_arg"
            exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=["'unexpected_value'"],
                expect_exception=True,
                expected_error_types=("TypeError",),
            )
            cases.append(AttackCase(
                id=case_id,
                category=AttackCategory.UNEXPECTED_TYPE,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Function '{func_name}' accepts 0 parameters; verify passing arguments raises TypeError.",
                test_input="unexpected_value",
                expected_behavior="Raises TypeError on extra argument",
                execution_code=exec_code,
            ))
            return cases

        primary_arg = arg_names[0]
        arg_lower = primary_arg.lower()
        func_lower = func_name.lower()

        # 1. NULL / NONE INPUT (primary argument)
        case_id = f"atk:{file_path}:{func_name}:none_input"
        exec_code = self._build_execution_snippet(
            module_path=module_import_path,
            func_name=func_name,
            call_args=["None"] + [self._default_safe_arg(a) for a in arg_names[1:]],
            expect_exception=False,
            expected_error_types=("ValueError", "TypeError", "AttributeError"),
        )
        cases.append(AttackCase(
            id=case_id,
            category=AttackCategory.NULL_OR_NONE_INPUT,
            target_file=file_path,
            target_symbol=func_name,
            rationale=f"Passing None to primary parameter '{primary_arg}' must not produce unhandled panic.",
            test_input=None,
            expected_behavior="Gracefully handles None or raises expected validation/type error",
            execution_code=exec_code,
        ))

        # Secondary argument None check if multiple arguments
        if len(arg_names) > 1:
            sec_arg = arg_names[1]
            sec_case_id = f"atk:{file_path}:{func_name}:none_sec_input"
            sec_exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=[self._default_safe_arg(primary_arg), "None"] + [self._default_safe_arg(a) for a in arg_names[2:]],
                expect_exception=False,
                expected_error_types=("ValueError", "TypeError", "AttributeError"),
            )
            cases.append(AttackCase(
                id=sec_case_id,
                category=AttackCategory.NULL_OR_NONE_INPUT,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Passing None to secondary parameter '{sec_arg}' must not produce unhandled panic.",
                test_input=None,
                expected_behavior="Gracefully handles None or raises expected validation/type error",
                execution_code=sec_exec_code,
            ))

        # 2. String/Path/Data targets -> EMPTY_INPUT and MALFORMED_INPUT
        is_string_target = any(k in arg_lower or k in func_lower for k in (
            "name", "path", "text", "str", "data", "token", "payload", "query", "url",
            "line", "delim", "header", "content", "msg", "message", "key", "title", "user", "raw"
        ))
        if is_string_target:
            case_id = f"atk:{file_path}:{func_name}:empty_string"
            exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=["''"] + [self._default_safe_arg(a) for a in arg_names[1:]],
                expect_exception=False,
                expected_error_types=("ValueError", "TypeError"),
            )
            cases.append(AttackCase(
                id=case_id,
                category=AttackCategory.EMPTY_INPUT,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Parameter '{primary_arg}' receives empty string; verify rejection or graceful empty handling.",
                test_input="",
                expected_behavior="Handled gracefully without unhandled crash",
                execution_code=exec_code,
            ))

            case_id = f"atk:{file_path}:{func_name}:malformed_input"
            exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=["'\\x00\\xff\\xfe<script>alert(1)</script>'"] + [self._default_safe_arg(a) for a in arg_names[1:]],
                expect_exception=False,
                expected_error_types=("ValueError", "UnicodeError"),
            )
            cases.append(AttackCase(
                id=case_id,
                category=AttackCategory.MALFORMED_INPUT,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Parameter '{primary_arg}' receives null bytes and injection characters.",
                test_input="\\x00\\xff\\xfe<script>",
                expected_behavior="Rejects malformed input or handles without crash",
                execution_code=exec_code,
            ))

        # 3. Numeric targets -> MINIMUM_VALUE / BOUNDARY_VALUE / MAXIMUM_VALUE
        is_numeric_target = any(k in arg_lower or k in func_lower for k in (
            "count", "amount", "timeout", "limit", "port", "size", "lines", "age", "num", "id",
            "price", "rate", "cost", "score", "val", "value", "balance", "index", "offset",
            "length", "level", "threshold", "percent", "discount", "qty", "quantity", "calc",
            "divide", "add", "sub", "mul", "math", "x", "y", "a", "b"
        ))
        if is_numeric_target:
            case_id = f"atk:{file_path}:{func_name}:negative_boundary"
            exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=["-1"] + [self._default_safe_arg(a) for a in arg_names[1:]],
                expect_exception=False,
                expected_error_types=("ValueError", "TypeError", "AssertionError"),
            )
            cases.append(AttackCase(
                id=case_id,
                category=AttackCategory.MINIMUM_VALUE,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Numeric parameter '{primary_arg}' receives negative boundary value -1.",
                test_input=-1,
                expected_behavior="Validates negative value or rejects with ValueError",
                execution_code=exec_code,
            ))

            case_id = f"atk:{file_path}:{func_name}:zero_boundary"
            # If function has secondary argument (like divisor b in divide(a, b)), test secondary=0 as well
            if len(arg_names) > 1 and any(k in arg_names[1].lower() for k in ("b", "denom", "divisor", "rate", "count", "step")):
                sec_call = [self._default_safe_arg(primary_arg), "0"] + [self._default_safe_arg(a) for a in arg_names[2:]]
            else:
                sec_call = ["0"] + [self._default_safe_arg(a) for a in arg_names[1:]]

            exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=sec_call,
                expect_exception=False,
                expected_error_types=("ValueError", "TypeError"),
            )
            cases.append(AttackCase(
                id=case_id,
                category=AttackCategory.BOUNDARY_VALUE,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Numeric parameter receives zero boundary value.",
                test_input=0,
                expected_behavior="Handles zero boundary without unhandled panic",
                execution_code=exec_code,
            ))

        # 4. Auth/Token targets -> PERMISSION_OR_AUTH_EDGE_CASE
        is_auth_target = any(k in func_lower or k in arg_lower for k in (
            "auth", "token", "session", "cred", "permission", "login", "password",
            "secret", "role", "admin", "authorize"
        ))
        if is_auth_target:
            case_id = f"atk:{file_path}:{func_name}:invalid_token"
            exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=["'invalid.expired.token'"] + [self._default_safe_arg(a) for a in arg_names[1:]],
                expect_exception=False,
                expected_error_types=("ValueError", "PermissionError", "KeyError"),
            )
            cases.append(AttackCase(
                id=case_id,
                category=AttackCategory.PERMISSION_OR_AUTH_EDGE_CASE,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Security/auth function '{func_name}' challenged with forged/expired token payload.",
                test_input="invalid.expired.token",
                expected_behavior="Rejects unauthorized or expired token",
                execution_code=exec_code,
            ))

        # 5. Financial / Critical error-handling path -> ERROR_PATH
        is_error_path_target = any(k in func_lower for k in (
            "payment", "transact", "transfer", "order", "charge", "pay", "process", "checkout", "billing"
        ))
        if is_error_path_target:
            case_id = f"atk:{file_path}:{func_name}:error_path"
            exec_code = self._build_execution_snippet(
                module_path=module_import_path,
                func_name=func_name,
                call_args=["-999999"] + [self._default_safe_arg(a) for a in arg_names[1:]],
                expect_exception=False,
                expected_error_types=("ValueError", "AssertionError"),
            )
            cases.append(AttackCase(
                id=case_id,
                category=AttackCategory.ERROR_PATH,
                target_file=file_path,
                target_symbol=func_name,
                rationale=f"Business-critical workflow '{func_name}' challenged with extreme negative input.",
                test_input=-999999,
                expected_behavior="Rejects illegal transaction amount on error path",
                execution_code=exec_code,
            ))

        return cases

    def _default_safe_arg(self, arg_name: str) -> str:
        """Provide a benign placeholder argument for secondary parameters."""
        lower = arg_name.lower()
        if (
            any(k in lower for k in ("count", "num", "limit", "port", "timeout", "price", "rate", "cost", "score", "amount", "size", "val", "value", "denom", "divisor"))
            or lower in ("a", "b", "x", "y", "z", "n", "m")
        ):
            return "10"
        if any(k in lower for k in ("items", "list", "files")):
            return "[]"
        if any(k in lower for k in ("dict", "map", "config", "opts")):
            return "{}"
        if any(k in lower for k in ("flag", "is_", "has_", "strict")):
            return "False"
        return "''"

    def _file_to_module(self, file_path: str) -> str:
        """Convert relative file path (e.g. src/agentproof/core/models.py) to Python import path."""
        p = file_path.replace("\\", "/")
        if p.startswith("src/"):
            p = p[4:]
        if p.endswith(".py"):
            p = p[:-3]
        return p.replace("/", ".")

    def _build_execution_snippet(
        self,
        module_path: str,
        func_name: str,
        call_args: List[str],
        expect_exception: bool = False,
        expected_error_types: Tuple[str, ...] = ("ValueError", "TypeError"),
    ) -> str:
        """Construct safe Python execution code for subprocess."""
        args_str = ", ".join(call_args)
        err_types = ", ".join(expected_error_types)

        return (
            f"import sys, importlib\n"
            f"try:\n"
            f"    mod = importlib.import_module('{module_path}')\n"
            f"    target = getattr(mod, '{func_name}')\n"
            f"    res = target({args_str})\n"
            f"    print('RESULT: ' + repr(res)[:100])\n"
            f"    sys.exit(0)\n"
            f"except ({err_types}) as e:\n"
            f"    print('HANDLED_EXPECTED_ERROR: ' + type(e).__name__ + ': ' + str(e)[:100])\n"
            f"    sys.exit(0)\n"
            f"except Exception as e:\n"
            f"    print('UNHANDLED_EXCEPTION: ' + type(e).__name__ + ': ' + str(e), file=sys.stderr)\n"
            f"    sys.exit(1)\n"
        )
