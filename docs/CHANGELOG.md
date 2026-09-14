# Changelog

All notable changes to **AgentProof** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.0] - 2026-09-14 (AgentProof V6)

### Added
- **Multi-Language Code Understanding Subsystem** (`src/agentproof/structure/`):
  - Abstract syntax tree & concrete syntax tree (CST) parsing powered by Tree-sitter.
  - Native support for Python, JavaScript, TypeScript, Go, Rust, and Java.
  - Robust multi-tiered fallback architecture: Tree-sitter CST -> Python `ast` -> Regex lexical fallback.
  - Honest `AnalysisLevel` reporting (`FULL_SEMANTIC`, `STRUCTURAL_AST`, `BASIC_HEURISTIC`, `UNSUPPORTED`).
  - Cross-language symbol, import, and call reference extraction.
- **Deep Multi-Language Impact Analysis**:
  - Downstream import tracking and symbol reference detection across TypeScript, JavaScript, Go, Rust, Java, and Python.
  - Java test file naming conventions (`*test.java`, `*tests.java`).
- **Agent-Agnostic Integration Layer** (`src/agentproof/integration/`):
  - Generic context ingestion (`AgentContext`, `AgentContextIngestion`) from CLI arguments, environment variables (`AGENTPROOF_*`), or JSON task input files.
  - Agent-optimized feedback protocol (`AgentFeedback`) delivering token-efficient, actionable remediation hints in markdown and JSON.
  - CLI flags `--agent` and `--agent-input` for seamless tool integration with Claude Code, Codex, Cursor, Gemini CLI, and custom agents.
  - Full integration documentation in `docs/AGENT_INTEGRATION.md`.
- **Open-Source Infrastructure**:
  - Full Apache-2.0 license (`LICENSE`).
  - Comprehensive `.gitignore` covering caches, environments, OS files, and scratch dirs.
  - `CONTRIBUTING.md` detailing architectural guidelines and testing expectations.
  - `SECURITY.md` establishing vulnerability disclosure policies and safe execution boundaries.
  - GitHub Actions CI workflow (`.github/workflows/ci.yml`) across Linux, macOS, Windows on Python 3.10 through 3.14.
  - Issue templates (bug report, feature request) and PR template.

---

## [0.5.0] - 2026-09-13 (AgentProof V5)

### Added
- **Adversarial Verification Engine** (`src/agentproof/adversarial/`):
  - Automatic synthesis of adversarial attack cases from AST inspection (Empty Input, Boundary Values, Maximum/Negative Numbers, Null/None parameters, Type Violations, Invalid Formats).
  - Isolated subprocess test runner with strict timeouts, memory truncation, and environment sandboxing.
  - Adversarial verification findings blocking verdicts upon verified runtime failures (`BLOCKED`).
  - Seamless ProofGraph integration linking attack cases to target symbols and findings.

---

## [0.4.0] - 2026-09-13 (AgentProof V4)

### Added
- **Proof Graph Engine** (`src/agentproof/graph/`):
  - Deterministic typed property graph connecting Tasks, Files, Symbols, Changes, Checks, Evidence, Findings, and Verdicts.
  - Graph traversal, cycle detection, and JSON graph serialization.
- **Proof Passport** (`src/agentproof/passport/`):
  - Portable, machine-readable verification credential with SHA-256 cryptographic attestation.
  - CLI command `agentproof passport`.

---

## [0.3.0] - 2026-09-13 (AgentProof V3)

### Added
- **Task-to-Change Drift Analyzer** (`src/agentproof/drift/`):
  - CLI flag `--task` for user/agent intent specification.
  - Deterministic keyword and path extraction with drift level scoring (`NONE`, `LOW`, `MEDIUM`, `HIGH`).
- **Missing Work Detector** (`src/agentproof/missing/`):
  - Evidence-backed detection of omitted tests (`MISSING_TESTS`), security validations (`MISSING_SECURITY_VALIDATION`), documentation updates, and error handling.

---

## [0.2.0] - 2026-09-13 (AgentProof V2)

### Added
- **Deep Git Change Analysis**:
  - Staged vs. unstaged change tracking.
  - Symbol extraction from unified diff headers and Python AST.
  - Category classification (Source, Test, Build, Config, Documentation, Dependency, CI, Security).
- **Change Impact Analysis** (`src/agentproof/impact/`):
  - Dependency and import traversal mapping changed code to downstream callers and affected tests.

---

## [0.1.0] - 2026-09-13 (AgentProof V1)

### Added
- Initial local CLI with `agentproof verify` and `agentproof inspect`.
- Automatic tool detection (pytest, unittest, flake8, ruff, black, mypy).
- Safe subprocess execution boundaries with timeouts and structured output parsing.
- 7-verdict evaluation system (`VERIFIED`, `VERIFIED_WITH_WARNINGS`, `BLOCKED`, `FAILED`, `ERROR`, `INCONCLUSIVE`, `NOT_EVALUATED`).
