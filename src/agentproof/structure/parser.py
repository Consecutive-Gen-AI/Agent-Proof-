"""Multi-language structural parser using Tree-sitter with robust AST/heuristic fallback."""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from agentproof.structure.models import (
    AnalysisLevel,
    CodeImport,
    CodeReference,
    CodeSymbol,
    FileStructure,
    SupportedLanguage,
    SymbolKind,
)

# Optional Tree-sitter imports with safe fallback
_TREE_SITTER_AVAILABLE = False
_PARSERS: Dict[SupportedLanguage, Any] = {}

try:
    from tree_sitter import Language, Parser
    import tree_sitter_go
    import tree_sitter_java
    import tree_sitter_javascript
    import tree_sitter_python
    import tree_sitter_rust
    import tree_sitter_typescript

    _PARSERS[SupportedLanguage.PYTHON] = Parser(Language(tree_sitter_python.language()))
    _PARSERS[SupportedLanguage.JAVASCRIPT] = Parser(Language(tree_sitter_javascript.language()))
    _PARSERS[SupportedLanguage.TYPESCRIPT] = Parser(Language(tree_sitter_typescript.language_typescript()))
    _PARSERS[SupportedLanguage.GO] = Parser(Language(tree_sitter_go.language()))
    _PARSERS[SupportedLanguage.RUST] = Parser(Language(tree_sitter_rust.language()))
    _PARSERS[SupportedLanguage.JAVA] = Parser(Language(tree_sitter_java.language()))
    _TREE_SITTER_AVAILABLE = True
except Exception:
    _TREE_SITTER_AVAILABLE = False


# Generic regex heuristics for fallback parsing
_REGEX_SYMBOLS = [
    # Functions / Methods
    (
        re.compile(r"^\s*(?:async\s+)?(?:def|function|fn|func)\s+([A-Za-z_][A-Za-z0-9_]*)\s*\((.*?)\)", re.MULTILINE),
        SymbolKind.FUNCTION,
    ),
    # Classes
    (
        re.compile(r"^\s*(?:public\s+|export\s+)?class\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
        SymbolKind.CLASS,
    ),
    # Structs (Go, Rust)
    (
        re.compile(r"^\s*(?:pub\s+)?struct\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
        SymbolKind.STRUCT,
    ),
    (
        re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+struct\b", re.MULTILINE),
        SymbolKind.STRUCT,
    ),
    # Interfaces (TS, Go, Java)
    (
        re.compile(r"^\s*(?:public\s+|export\s+)?interface\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
        SymbolKind.INTERFACE,
    ),
    (
        re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\s+interface\b", re.MULTILINE),
        SymbolKind.INTERFACE,
    ),
    # Traits (Rust)
    (
        re.compile(r"^\s*(?:pub\s+)?trait\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE),
        SymbolKind.TRAIT,
    ),
]

_REGEX_IMPORTS = [
    re.compile(r"^\s*(?:import|from)\s+([A-Za-z0-9_.]+)", re.MULTILINE),
    re.compile(r"^\s*import\s+.*?from\s+['\"](.*?)['\"]", re.MULTILINE),
    re.compile(r"^\s*import\s+['\"](.*?)['\"]", re.MULTILINE),
    re.compile(r"^\s*use\s+([A-Za-z0-9_:]+)", re.MULTILINE),
    re.compile(r"^\s*package\s+([A-Za-z0-9_.]+)", re.MULTILINE),
]

_REGEX_CALLS = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")


class StructureParser:
    """Parses source code into a language-independent FileStructure."""

    def parse_source(self, file_path: str, content: str) -> FileStructure:
        """Parse source text for a given file path into FileStructure."""
        ext = Path(file_path).suffix
        language = SupportedLanguage.from_extension(ext)

        if language == SupportedLanguage.UNSUPPORTED or not content.strip():
            return FileStructure(
                file_path=file_path,
                language=language,
                analysis_level=AnalysisLevel.UNSUPPORTED if language == SupportedLanguage.UNSUPPORTED else AnalysisLevel.STRUCTURAL_AST,
                symbols=[],
                imports=[],
                references=[],
            )

        # Attempt Tree-sitter parsing if available
        if _TREE_SITTER_AVAILABLE and language in _PARSERS:
            try:
                parser = _PARSERS[language]
                tree = parser.parse(content.encode("utf-8", errors="replace"))
                if not tree.root_node.has_error:
                    return self._extract_from_tree_sitter(file_path, language, tree.root_node, content)
                # Tree has errors (malformed syntax) — attempt extraction anyway, record note
                fs = self._extract_from_tree_sitter(file_path, language, tree.root_node, content)
                fs.parse_error = "Syntax errors encountered during tree-sitter parsing"
                return fs
            except Exception as e:
                # Fallback to Python AST or regex
                pass

        # Fallback for Python using standard library ast
        if language == SupportedLanguage.PYTHON:
            try:
                return self._parse_python_ast(file_path, content)
            except Exception as e:
                return self._parse_regex_fallback(file_path, language, content, str(e))

        # Heuristic fallback for other languages
        return self._parse_regex_fallback(file_path, language, content)

    def _extract_from_tree_sitter(
        self, file_path: str, language: SupportedLanguage, root_node: Any, content: str
    ) -> FileStructure:
        """Walk Tree-sitter CST and extract symbols, imports, and references."""
        symbols: List[CodeSymbol] = []
        imports: List[CodeImport] = []
        references: List[CodeReference] = []

        lines = content.splitlines()

        def get_text(node: Any) -> str:
            if not node:
                return ""
            return node.text.decode("utf-8", errors="replace")

        def extract_params(node: Any) -> List[str]:
            params: List[str] = []
            params_node = node.child_by_field_name("parameters")
            if not params_node:
                # Some languages use 'parameter_list' or direct children
                for child in node.children:
                    if "param" in child.type:
                        params_node = child
                        break
            if params_node:
                for p in params_node.children:
                    if p.type in ("identifier", "name"):
                        params.append(get_text(p))
                    elif p.child_by_field_name("name"):
                        params.append(get_text(p.child_by_field_name("name")))
                    elif p.type in (
                        "typed_parameter", "default_parameter", "typed_default_parameter",
                        "parameter_declaration", "formal_parameter", "parameter",
                        "required_parameter", "optional_parameter"
                    ):
                        for sub in p.children:
                            if sub.type in ("identifier", "name"):
                                params.append(get_text(sub))
                                break
            # Filter out syntax tokens
            return [p for p in params if p and p not in ("self", "cls", "(", ")", ",")]

        def walk(node: Any, current_parent: Optional[str] = None):
            nonlocal symbols, imports, references
            ntype = node.type

            # --- Symbols ---
            sym: Optional[CodeSymbol] = None

            # Python
            if language == SupportedLanguage.PYTHON:
                if ntype in ("function_definition", "async_function_definition"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        kind = SymbolKind.METHOD if current_parent else SymbolKind.FUNCTION
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=kind,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parameters=extract_params(node),
                            parent_symbol=current_parent,
                            is_public=not sym_name.startswith("_"),
                        )
                elif ntype == "class_definition":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=SymbolKind.CLASS,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parent_symbol=current_parent,
                            is_public=not sym_name.startswith("_"),
                        )
                elif ntype in ("import_statement", "import_from_statement"):
                    mod_text = get_text(node)
                    # Extract imported module
                    for child in node.children:
                        if child.type == "dotted_name":
                            imports.append(CodeImport(module=get_text(child), line_number=node.start_point[0] + 1))
                            break
                elif ntype == "call":
                    func_node = node.child_by_field_name("function")
                    if func_node:
                        call_name = get_text(func_node).split(".")[-1]
                        references.append(CodeReference(symbol_name=call_name, calling_symbol=current_parent, line_number=node.start_point[0] + 1))

            # JavaScript / TypeScript
            elif language in (SupportedLanguage.JAVASCRIPT, SupportedLanguage.TYPESCRIPT):
                if ntype in ("function_declaration", "method_definition"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        kind = SymbolKind.METHOD if (current_parent or ntype == "method_definition") else SymbolKind.FUNCTION
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=kind,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parameters=extract_params(node),
                            parent_symbol=current_parent,
                            is_public=not sym_name.startswith("_"),
                        )
                elif ntype == "class_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=SymbolKind.CLASS,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parent_symbol=current_parent,
                        )
                elif ntype == "interface_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym = CodeSymbol(
                            name=get_text(name_node),
                            kind=SymbolKind.INTERFACE,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                        )
                elif ntype == "type_alias_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym = CodeSymbol(
                            name=get_text(name_node),
                            kind=SymbolKind.TYPE_ALIAS,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                        )
                elif ntype == "import_statement":
                    source_node = node.child_by_field_name("source")
                    if source_node:
                        mod = get_text(source_node).strip("'\"")
                        imports.append(CodeImport(module=mod, line_number=node.start_point[0] + 1))
                elif ntype == "call_expression":
                    func_node = node.child_by_field_name("function")
                    if func_node:
                        call_name = get_text(func_node).split(".")[-1]
                        references.append(CodeReference(symbol_name=call_name, calling_symbol=current_parent, line_number=node.start_point[0] + 1))

            # Go
            elif language == SupportedLanguage.GO:
                if ntype == "function_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=SymbolKind.FUNCTION,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parameters=extract_params(node),
                            is_public=sym_name[0].isupper(),
                        )
                elif ntype == "method_declaration":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=SymbolKind.METHOD,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parameters=extract_params(node),
                            is_public=sym_name[0].isupper(),
                        )
                elif ntype == "type_declaration":
                    for sub in node.children:
                        if sub.type == "type_spec":
                            name_node = sub.child_by_field_name("name")
                            type_node = sub.child_by_field_name("type")
                            if name_node:
                                sym_name = get_text(name_node)
                                kind = SymbolKind.INTERFACE if (type_node and type_node.type == "interface_type") else SymbolKind.STRUCT
                                symbols.append(CodeSymbol(
                                    name=sym_name,
                                    kind=kind,
                                    file_path=file_path,
                                    line_start=sub.start_point[0] + 1,
                                    line_end=sub.end_point[0] + 1,
                                    is_public=sym_name[0].isupper(),
                                ))
                elif ntype == "import_declaration":
                    for sub in node.children:
                        if sub.type == "import_spec":
                            path_node = sub.child_by_field_name("path")
                            if path_node:
                                imports.append(CodeImport(module=get_text(path_node).strip('"'), line_number=sub.start_point[0] + 1))
                        elif sub.type == "import_spec_list":
                            for s2 in sub.children:
                                if s2.type == "import_spec":
                                    path_node = s2.child_by_field_name("path")
                                    if path_node:
                                        imports.append(CodeImport(module=get_text(path_node).strip('"'), line_number=s2.start_point[0] + 1))
                elif ntype == "call_expression":
                    func_node = node.child_by_field_name("function")
                    if func_node:
                        call_name = get_text(func_node).split(".")[-1]
                        references.append(CodeReference(symbol_name=call_name, calling_symbol=current_parent, line_number=node.start_point[0] + 1))

            # Rust
            elif language == SupportedLanguage.RUST:
                if ntype == "function_item":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=SymbolKind.METHOD if current_parent else SymbolKind.FUNCTION,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parameters=extract_params(node),
                            parent_symbol=current_parent,
                            is_public=get_text(node).strip().startswith("pub"),
                        )
                elif ntype in ("struct_item", "enum_item"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym = CodeSymbol(
                            name=get_text(name_node),
                            kind=SymbolKind.STRUCT,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            is_public=get_text(node).strip().startswith("pub"),
                        )
                elif ntype == "trait_item":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym = CodeSymbol(
                            name=get_text(name_node),
                            kind=SymbolKind.TRAIT,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            is_public=get_text(node).strip().startswith("pub"),
                        )
                elif ntype == "use_declaration":
                    use_text = get_text(node).replace("use", "").replace(";", "").strip()
                    imports.append(CodeImport(module=use_text, line_number=node.start_point[0] + 1))
                elif ntype == "call_expression":
                    func_node = node.child_by_field_name("function")
                    if func_node:
                        call_name = get_text(func_node).split("::")[-1].split(".")[-1]
                        references.append(CodeReference(symbol_name=call_name, calling_symbol=current_parent, line_number=node.start_point[0] + 1))

            # Java
            elif language == SupportedLanguage.JAVA:
                if ntype in ("method_declaration", "constructor_declaration"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=SymbolKind.METHOD,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            parameters=extract_params(node),
                            parent_symbol=current_parent,
                            is_public="public" in get_text(node),
                        )
                elif ntype in ("class_declaration", "interface_declaration"):
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        sym_name = get_text(name_node)
                        kind = SymbolKind.INTERFACE if ntype == "interface_declaration" else SymbolKind.CLASS
                        sym = CodeSymbol(
                            name=sym_name,
                            kind=kind,
                            file_path=file_path,
                            line_start=node.start_point[0] + 1,
                            line_end=node.end_point[0] + 1,
                            is_public="public" in get_text(node),
                        )
                elif ntype == "import_declaration":
                    for sub in node.children:
                        if sub.type == "scoped_identifier":
                            imports.append(CodeImport(module=get_text(sub), line_number=node.start_point[0] + 1))
                            break
                elif ntype == "method_invocation":
                    name_node = node.child_by_field_name("name")
                    if name_node:
                        references.append(CodeReference(symbol_name=get_text(name_node), calling_symbol=current_parent, line_number=node.start_point[0] + 1))

            if sym:
                symbols.append(sym)
                next_parent = sym.name
            else:
                next_parent = current_parent

            for child in node.children:
                walk(child, next_parent)

        walk(root_node)

        # De-duplicate references preserving order
        unique_refs: List[CodeReference] = []
        seen_refs: Set[Tuple[str, Optional[str], int]] = set()
        for r in references:
            key = (r.symbol_name, r.calling_symbol, r.line_number)
            if key not in seen_refs:
                seen_refs.add(key)
                unique_refs.append(r)

        return FileStructure(
            file_path=file_path,
            language=language,
            analysis_level=AnalysisLevel.STRUCTURAL_AST,
            symbols=symbols,
            imports=imports,
            references=unique_refs,
        )

    def _parse_python_ast(self, file_path: str, content: str) -> FileStructure:
        """Parse Python source using standard library ast module."""
        tree = ast.parse(content, filename=file_path)
        symbols: List[CodeSymbol] = []
        imports: List[CodeImport] = []
        references: List[CodeReference] = []

        class ASTVisitor(ast.NodeVisitor):
            def __init__(self):
                self.current_parent: Optional[str] = None

            def visit_FunctionDef(self, node: ast.FunctionDef):
                self._handle_func(node, is_async=False)

            def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
                self._handle_func(node, is_async=True)

            def _handle_func(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool):
                params = [a.arg for a in node.args.args if a.arg not in ("self", "cls")]
                kind = SymbolKind.METHOD if self.current_parent else SymbolKind.FUNCTION
                sym = CodeSymbol(
                    name=node.name,
                    kind=kind,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    parameters=params,
                    parent_symbol=self.current_parent,
                    docstring=ast.get_docstring(node),
                    is_public=not node.name.startswith("_"),
                )
                symbols.append(sym)
                old_parent = self.current_parent
                self.current_parent = node.name
                self.generic_visit(node)
                self.current_parent = old_parent

            def visit_ClassDef(self, node: ast.ClassDef):
                sym = CodeSymbol(
                    name=node.name,
                    kind=SymbolKind.CLASS,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=getattr(node, "end_lineno", node.lineno),
                    parent_symbol=self.current_parent,
                    docstring=ast.get_docstring(node),
                    is_public=not node.name.startswith("_"),
                )
                symbols.append(sym)
                old_parent = self.current_parent
                self.current_parent = node.name
                self.generic_visit(node)
                self.current_parent = old_parent

            def visit_Import(self, node: ast.Import):
                for alias in node.names:
                    imports.append(CodeImport(module=alias.name, alias=alias.asname, line_number=node.lineno))

            def visit_ImportFrom(self, node: ast.ImportFrom):
                mod = node.module or ""
                names = [n.name for n in node.names]
                imports.append(CodeImport(module=mod, imported_symbols=names, line_number=node.lineno))

            def visit_Call(self, node: ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name:
                    references.append(CodeReference(symbol_name=name, calling_symbol=self.current_parent, line_number=node.lineno))
                self.generic_visit(node)

        visitor = ASTVisitor()
        visitor.visit(tree)

        return FileStructure(
            file_path=file_path,
            language=SupportedLanguage.PYTHON,
            analysis_level=AnalysisLevel.STRUCTURAL_AST,
            symbols=symbols,
            imports=imports,
            references=references,
        )

    def _parse_regex_fallback(
        self, file_path: str, language: SupportedLanguage, content: str, parse_error: Optional[str] = None
    ) -> FileStructure:
        """Fallback lexical/regex parser for environments without tree-sitter or on parse failures."""
        symbols: List[CodeSymbol] = []
        imports: List[CodeImport] = []
        references: List[CodeReference] = []

        lines = content.splitlines()

        for idx, line in enumerate(lines, start=1):
            # Check symbols
            for pattern, kind in _REGEX_SYMBOLS:
                m = pattern.search(line)
                if m:
                    sym_name = m.group(1)
                    params = []
                    if m.lastindex and m.lastindex >= 2:
                        raw_params = m.group(2)
                        params = [p.strip().split()[-1].split(":")[-1] for p in raw_params.split(",") if p.strip()]
                    symbols.append(
                        CodeSymbol(
                            name=sym_name,
                            kind=kind,
                            file_path=file_path,
                            line_start=idx,
                            line_end=idx,
                            parameters=params,
                            is_public=not sym_name.startswith("_") if language != SupportedLanguage.GO else sym_name[0].isupper(),
                        )
                    )
                    break

            # Check imports
            for pat in _REGEX_IMPORTS:
                m = pat.search(line)
                if m:
                    imports.append(CodeImport(module=m.group(1), line_number=idx))
                    break

            # Check calls
            for call_m in _REGEX_CALLS.finditer(line):
                call_name = call_m.group(1)
                # Ignore common language keywords that look like function calls
                if call_name not in ("if", "for", "while", "switch", "catch", "return", "sizeof"):
                    references.append(CodeReference(symbol_name=call_name, line_number=idx))

        return FileStructure(
            file_path=file_path,
            language=language,
            analysis_level=AnalysisLevel.BASIC_HEURISTIC,
            symbols=symbols,
            imports=imports,
            references=references,
            parse_error=parse_error,
        )
