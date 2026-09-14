"""Unit tests for the multi-language code structure parser (Python, JS, TS, Go, Rust, Java)."""

from agentproof.structure.models import (
    AnalysisLevel,
    SupportedLanguage,
    SymbolKind,
)
from agentproof.structure.parser import StructureParser


def test_parser_python():
    parser = StructureParser()
    code = (
        "import os\n"
        "from typing import List\n"
        "\n"
        "def compute_hash(data: str) -> str:\n"
        "    return os.getenv('SALT', '') + data\n"
        "\n"
        "class TokenManager:\n"
        "    def generate_token(self, user_id: int) -> str:\n"
        "        return compute_hash(str(user_id))\n"
    )
    fs = parser.parse_source("auth/token.py", code)
    assert fs.language == SupportedLanguage.PYTHON
    assert fs.analysis_level == AnalysisLevel.STRUCTURAL_AST
    names = [s.name for s in fs.symbols]
    assert "compute_hash" in names
    assert "TokenManager" in names
    assert "generate_token" in names

    # Verify parameters
    compute_sym = next(s for s in fs.symbols if s.name == "compute_hash")
    assert "data" in compute_sym.parameters
    assert compute_sym.kind == SymbolKind.FUNCTION

    # Verify calls
    ref_names = [r.symbol_name for r in fs.references]
    assert "compute_hash" in ref_names or "getenv" in ref_names


def test_parser_javascript():
    parser = StructureParser()
    code = (
        "import { auth } from './auth';\n"
        "\n"
        "function formatUser(name, age) {\n"
        "    return `${name}:${age}`;\n"
        "}\n"
        "\n"
        "class UserService {\n"
        "    login(username, password) {\n"
        "        return auth(username, password);\n"
        "    }\n"
        "}\n"
    )
    fs = parser.parse_source("services/user.js", code)
    assert fs.language == SupportedLanguage.JAVASCRIPT
    names = [s.name for s in fs.symbols]
    assert "formatUser" in names
    assert "UserService" in names
    assert "login" in names

    # Verify imports
    assert any(i.module in ("./auth", "auth") for i in fs.imports)
    # Verify calls
    assert any(r.symbol_name == "auth" for r in fs.references)


def test_parser_typescript():
    parser = StructureParser()
    code = (
        "import { Config } from './config';\n"
        "\n"
        "export interface UserProfile {\n"
        "    id: string;\n"
        "    email: string;\n"
        "}\n"
        "\n"
        "export type Status = 'active' | 'inactive';\n"
        "\n"
        "export function validateProfile(profile: UserProfile): boolean {\n"
        "    return profile.email.length > 0;\n"
        "}\n"
    )
    fs = parser.parse_source("models/profile.ts", code)
    assert fs.language == SupportedLanguage.TYPESCRIPT
    names = [s.name for s in fs.symbols]
    assert "UserProfile" in names
    assert "Status" in names
    assert "validateProfile" in names


def test_parser_go():
    parser = StructureParser()
    code = (
        "package main\n"
        "\n"
        "import (\n"
        "    \"fmt\"\n"
        "    \"strings\"\n"
        ")\n"
        "\n"
        "type Client struct {\n"
        "    Endpoint string\n"
        "}\n"
        "\n"
        "type Service interface {\n"
        "    Execute(cmd string) error\n"
        "}\n"
        "\n"
        "func NewClient(endpoint string) *Client {\n"
        "    return &Client{Endpoint: endpoint}\n"
        "}\n"
        "\n"
        "func (c *Client) Send(payload string) bool {\n"
        "    fmt.Println(payload)\n"
        "    return true\n"
        "}\n"
    )
    fs = parser.parse_source("client.go", code)
    assert fs.language == SupportedLanguage.GO
    names = [s.name for s in fs.symbols]
    assert "Client" in names
    assert "Service" in names
    assert "NewClient" in names
    assert "Send" in names
    assert any(i.module == "fmt" for i in fs.imports)


def test_parser_rust():
    parser = StructureParser()
    code = (
        "use std::collections::HashMap;\n"
        "\n"
        "pub struct SessionStore {\n"
        "    sessions: HashMap<String, String>,\n"
        "}\n"
        "\n"
        "pub trait Authenticator {\n"
        "    fn authenticate(&self, token: &str) -> bool;\n"
        "}\n"
        "\n"
        "pub fn verify_signature(data: &[u8], sig: &[u8]) -> bool {\n"
        "    data.len() == sig.len()\n"
        "}\n"
    )
    fs = parser.parse_source("auth/store.rs", code)
    assert fs.language == SupportedLanguage.RUST
    names = [s.name for s in fs.symbols]
    assert "SessionStore" in names
    assert "Authenticator" in names
    assert "verify_signature" in names


def test_parser_java():
    parser = StructureParser()
    code = (
        "package com.example.payment;\n"
        "\n"
        "import java.util.Currency;\n"
        "\n"
        "public class PaymentProcessor {\n"
        "    private final String merchantId;\n"
        "\n"
        "    public PaymentProcessor(String merchantId) {\n"
        "        this.merchantId = merchantId;\n"
        "    }\n"
        "\n"
        "    public boolean charge(double amount, String currency) {\n"
        "        return amount > 0;\n"
        "    }\n"
        "}\n"
    )
    fs = parser.parse_source("PaymentProcessor.java", code)
    assert fs.language == SupportedLanguage.JAVA
    names = [s.name for s in fs.symbols]
    assert "PaymentProcessor" in names
    assert "charge" in names


def test_parser_unsupported_language():
    parser = StructureParser()
    code = "Some raw text without known extension"
    fs = parser.parse_source("notes.txt", code)
    assert fs.language == SupportedLanguage.UNSUPPORTED
    assert fs.analysis_level == AnalysisLevel.UNSUPPORTED
    assert len(fs.symbols) == 0


def test_parser_empty_file():
    parser = StructureParser()
    fs = parser.parse_source("empty.py", "")
    assert fs.language == SupportedLanguage.PYTHON
    assert len(fs.symbols) == 0


def test_parser_malformed_syntax():
    parser = StructureParser()
    code = "def incomplete_func(\nclass Broken {\n"
    fs = parser.parse_source("broken.py", code)
    assert fs.language == SupportedLanguage.PYTHON
    # Must not throw, extracts gracefully
    assert isinstance(fs.symbols, list)


def test_parser_regex_fallback():
    parser = StructureParser()
    code = "func ProcessData(items []string) error {\n return nil\n}\n"
    # Call internal regex fallback directly
    fs = parser._parse_regex_fallback("worker.go", SupportedLanguage.GO, code)
    assert fs.language == SupportedLanguage.GO
    assert fs.analysis_level == AnalysisLevel.BASIC_HEURISTIC
    names = [s.name for s in fs.symbols]
    assert "ProcessData" in names
