"""Language-independent code structure models for AgentProof V6."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple


class SupportedLanguage(str, Enum):
    """Programming languages recognized by AgentProof."""
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    UNSUPPORTED = "unsupported"

    @classmethod
    def from_extension(cls, ext: str) -> SupportedLanguage:
        """Map a file extension (with leading dot) to a SupportedLanguage."""
        normalized = ext.lower().strip()
        mapping = {
            ".py": cls.PYTHON,
            ".pyw": cls.PYTHON,
            ".js": cls.JAVASCRIPT,
            ".mjs": cls.JAVASCRIPT,
            ".cjs": cls.JAVASCRIPT,
            ".jsx": cls.JAVASCRIPT,
            ".ts": cls.TYPESCRIPT,
            ".tsx": cls.TYPESCRIPT,
            ".mts": cls.TYPESCRIPT,
            ".cts": cls.TYPESCRIPT,
            ".go": cls.GO,
            ".rs": cls.RUST,
            ".java": cls.JAVA,
        }
        return mapping.get(normalized, cls.UNSUPPORTED)


class AnalysisLevel(str, Enum):
    """
    Honest transparency into the actual depth of code analysis.
    In alignment with AGENTS.md, unsupported languages must never be
    labeled as having full semantic understanding.
    """
    FULL_SEMANTIC = "FULL_SEMANTIC"        # Deep type-checked AST & cross-module symbol resolution
    STRUCTURAL_AST = "STRUCTURAL_AST"      # Concrete Syntax Tree via Tree-sitter or standard AST
    BASIC_HEURISTIC = "BASIC_HEURISTIC"    # Lexical or regex token matching
    UNSUPPORTED = "UNSUPPORTED"            # Unanalyzed or plain text file


class SymbolKind(str, Enum):
    """Universal categorization of code symbols across languages."""
    FUNCTION = "FUNCTION"
    METHOD = "METHOD"
    CLASS = "CLASS"
    INTERFACE = "INTERFACE"
    STRUCT = "STRUCT"
    TRAIT = "TRAIT"
    TYPE_ALIAS = "TYPE_ALIAS"
    VARIABLE = "VARIABLE"
    CONSTANT = "CONSTANT"


@dataclass
class CodeSymbol:
    """A declared symbol (function, method, class, struct, etc.)."""
    name: str
    kind: SymbolKind
    file_path: str
    line_start: int
    line_end: int
    signature: Optional[str] = None
    parameters: List[str] = field(default_factory=list)
    parent_symbol: Optional[str] = None
    docstring: Optional[str] = None
    is_public: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind.value,
            "file_path": self.file_path,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "signature": self.signature,
            "parameters": self.parameters,
            "parent_symbol": self.parent_symbol,
            "docstring": self.docstring,
            "is_public": self.is_public,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CodeSymbol:
        return cls(
            name=data["name"],
            kind=SymbolKind(data["kind"]),
            file_path=data["file_path"],
            line_start=data["line_start"],
            line_end=data["line_end"],
            signature=data.get("signature"),
            parameters=data.get("parameters", []),
            parent_symbol=data.get("parent_symbol"),
            docstring=data.get("docstring"),
            is_public=data.get("is_public", True),
        )


@dataclass
class CodeImport:
    """An import statement referencing an external or sibling module."""
    module: str
    imported_symbols: List[str] = field(default_factory=list)
    alias: Optional[str] = None
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "module": self.module,
            "imported_symbols": self.imported_symbols,
            "alias": self.alias,
            "line_number": self.line_number,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CodeImport:
        return cls(
            module=data["module"],
            imported_symbols=data.get("imported_symbols", []),
            alias=data.get("alias"),
            line_number=data.get("line_number", 0),
        )


@dataclass
class CodeReference:
    """A reference or function call to a symbol within a file."""
    symbol_name: str
    calling_symbol: Optional[str] = None
    line_number: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol_name": self.symbol_name,
            "calling_symbol": self.calling_symbol,
            "line_number": self.line_number,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CodeReference:
        return cls(
            symbol_name=data["symbol_name"],
            calling_symbol=data.get("calling_symbol"),
            line_number=data.get("line_number", 0),
        )


@dataclass
class FileStructure:
    """Structured AST representation of a single code file."""
    file_path: str
    language: SupportedLanguage
    analysis_level: AnalysisLevel
    symbols: List[CodeSymbol] = field(default_factory=list)
    imports: List[CodeImport] = field(default_factory=list)
    references: List[CodeReference] = field(default_factory=list)
    parse_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "language": self.language.value,
            "analysis_level": self.analysis_level.value,
            "symbols": [s.to_dict() for s in self.symbols],
            "imports": [i.to_dict() for i in self.imports],
            "references": [r.to_dict() for r in self.references],
            "parse_error": self.parse_error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> FileStructure:
        return cls(
            file_path=data["file_path"],
            language=SupportedLanguage(data["language"]),
            analysis_level=AnalysisLevel(data["analysis_level"]),
            symbols=[CodeSymbol.from_dict(s) for s in data.get("symbols", [])],
            imports=[CodeImport.from_dict(i) for i in data.get("imports", [])],
            references=[CodeReference.from_dict(r) for r in data.get("references", [])],
            parse_error=data.get("parse_error"),
        )


@dataclass
class ProjectStructure:
    """Project-level aggregation of file structures and relationships."""
    files: Dict[str, FileStructure] = field(default_factory=dict)

    def get_symbols_by_name(self, name: str) -> List[CodeSymbol]:
        """Find all symbols across files matching a given name."""
        results: List[CodeSymbol] = []
        for file_struct in self.files.values():
            for sym in file_struct.symbols:
                if sym.name == name:
                    results.append(sym)
        return results

    def find_callers_of(self, symbol_name: str) -> List[Tuple[str, CodeReference]]:
        """Find all files and call references that invoke the given symbol name."""
        callers: List[Tuple[str, CodeReference]] = []
        for file_path, file_struct in self.files.items():
            for ref in file_struct.references:
                if ref.symbol_name == symbol_name:
                    callers.append((file_path, ref))
        return callers

    def find_importers_of(self, module_name: str) -> List[Tuple[str, CodeImport]]:
        """Find files that import the specified module or symbol."""
        importers: List[Tuple[str, CodeImport]] = []
        for file_path, file_struct in self.files.items():
            for imp in file_struct.imports:
                if imp.module == module_name or module_name in imp.imported_symbols or imp.module.endswith(f"/{module_name}"):
                    importers.append((file_path, imp))
        return importers

    def to_dict(self) -> Dict[str, Any]:
        return {
            "files": {path: fs.to_dict() for path, fs in self.files.items()},
            "file_count": len(self.files),
            "total_symbols": sum(len(fs.symbols) for fs in self.files.values()),
        }
