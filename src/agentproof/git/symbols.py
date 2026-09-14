"""Deterministic code symbol extraction from diff hunks and AST."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import List, Set, Tuple

from agentproof.core.models import SymbolChange, SymbolType
from agentproof.structure import StructureEngine, SupportedLanguage, SymbolKind

# Regex to match hunk headers in git diff: @@ -x,y +a,b @@ [context]
HUNK_HEADER_REGEX = re.compile(r"^@@\s+-\d+(?:,\d+)?\s+\+(\d+)(?:,(\d+))?\s+@@\s*(.*)$")

# Regex heuristics for non-Python symbols in diff headers or changed lines
GENERIC_SYMBOL_REGEX = re.compile(
    r"(?:def|class|function|fn|func|interface|struct|type|const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)"
)


class SymbolExtractor:
    """Extracts changed functions, classes, and methods from changed files and patches."""

    def __init__(self, engine: Optional[StructureEngine] = None) -> None:
        self.engine = engine or StructureEngine()

    def extract_from_diff_text(self, diff_text: str, rel_path: str) -> List[SymbolChange]:
        """Extract symbols mentioned in git diff hunk headers."""
        symbols: List[SymbolChange] = []
        seen: Set[Tuple[str, str]] = set()

        for line in diff_text.splitlines():
            match = HUNK_HEADER_REGEX.match(line)
            if not match:
                continue

            line_start = int(match.group(1))
            context = match.group(3).strip()
            if not context:
                continue

            sym_match = GENERIC_SYMBOL_REGEX.search(context)
            if sym_match:
                name = sym_match.group(1)
                sym_type = SymbolType.CLASS if "class " in context else SymbolType.FUNCTION
                if (name, sym_type.value) not in seen:
                    seen.add((name, sym_type.value))
                    symbols.append(
                        SymbolChange(
                            name=name,
                            symbol_type=sym_type,
                            file_path=rel_path,
                            change_type="MODIFIED",
                            line_number=line_start,
                        )
                    )
        return symbols

    def extract_from_python_file(
        self,
        full_path: Path,
        rel_path: str,
        changed_lines: Set[int],
    ) -> List[SymbolChange]:
        """Use Python AST to precisely identify functions and classes overlapping changed lines."""
        if not full_path.is_file() or full_path.suffix != ".py":
            return []

        try:
            source = full_path.read_text(encoding="utf-8", errors="ignore")
            tree = ast.parse(source, filename=str(full_path))
        except Exception:
            return []

        symbols: List[SymbolChange] = []
        seen: Set[str] = set()

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                start_line = getattr(node, "lineno", 0)
                end_line = getattr(node, "end_lineno", start_line)

                # Check if this node overlaps any changed lines, or if changed_lines is empty (e.g. added file)
                overlaps = not changed_lines or any(start_line <= line <= end_line for line in changed_lines)
                if overlaps and node.name not in seen:
                    seen.add(node.name)
                    sym_type = SymbolType.CLASS if isinstance(node, ast.ClassDef) else SymbolType.FUNCTION
                    change_type = "ADDED" if not changed_lines else "MODIFIED"
                    symbols.append(
                        SymbolChange(
                            name=node.name,
                            symbol_type=sym_type,
                            file_path=rel_path,
                            change_type=change_type,
                            line_number=start_line,
                        )
                    )
        return symbols

    def extract_from_source_file(
        self,
        full_path: Path,
        rel_path: str,
        changed_lines: Set[int],
    ) -> List[SymbolChange]:
        """Use StructureEngine to extract symbols overlapping changed lines across supported languages."""
        if not full_path.is_file():
            return []

        ext = full_path.suffix.lower()
        if SupportedLanguage.from_extension(ext) == SupportedLanguage.UNSUPPORTED:
            return []

        overlapping = self.engine.get_overlapping_symbols(full_path, rel_path, changed_lines)
        symbols: List[SymbolChange] = []
        seen: Set[str] = set()

        kind_map = {
            SymbolKind.FUNCTION: SymbolType.FUNCTION,
            SymbolKind.METHOD: SymbolType.METHOD,
            SymbolKind.CLASS: SymbolType.CLASS,
            SymbolKind.INTERFACE: SymbolType.TYPE,
            SymbolKind.STRUCT: SymbolType.TYPE,
            SymbolKind.TRAIT: SymbolType.TYPE,
            SymbolKind.TYPE_ALIAS: SymbolType.TYPE,
            SymbolKind.CONSTANT: SymbolType.CONSTANT,
            SymbolKind.VARIABLE: SymbolType.VARIABLE,
        }

        for sym in overlapping:
            if sym.name not in seen:
                seen.add(sym.name)
                sym_type = kind_map.get(sym.kind, SymbolType.FUNCTION)
                change_type = "ADDED" if not changed_lines else "MODIFIED"
                symbols.append(
                    SymbolChange(
                        name=sym.name,
                        symbol_type=sym_type,
                        file_path=rel_path,
                        change_type=change_type,
                        line_number=sym.line_start,
                    )
                )
        return symbols

    def parse_changed_line_numbers(self, patch: str) -> Set[int]:
        """Extract target line numbers modified according to unified diff."""
        changed: Set[int] = set()
        current_line = 0

        for line in patch.splitlines():
            match = HUNK_HEADER_REGEX.match(line)
            if match:
                current_line = int(match.group(1))
                continue
            if current_line == 0:
                continue

            if line.startswith("+") and not line.startswith("+++"):
                changed.add(current_line)
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                # deletion occurs at current_line
                changed.add(current_line)
            elif line.startswith(" "):
                current_line += 1

        return changed
