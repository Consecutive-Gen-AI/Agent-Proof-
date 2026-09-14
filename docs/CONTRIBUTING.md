# Contributing to AgentProof

Thank you for your interest in contributing to **AgentProof**!

AgentProof is an **agent-agnostic verification and evidence layer for AI-generated software changes**. Our engineering constitution is defined in [`AGENTS.md`](./AGENTS.md). Every contributor and coding agent MUST read and adhere to those principles.

---

## 1. Core Engineering Principles

Before proposing any change or writing code, internalize our core tenets:

1. **Evidence Over Assertions**: Never trust an author or agent claiming "all tests pass" or "this fix is safe." Collect and evaluate independent, reproducible evidence.
2. **Agent-Agnostic Core**: AgentProof must remain decoupled from specific AI providers. Core logic must never depend on a proprietary agent's internal quirks or cloud prompts.
3. **Deterministic Behavior**: Prefer deterministic, verifiable algorithms over speculative heuristics.
4. **Zero AI Slop**: Reject unnecessary wrappers, boilerplate abstractions, dead code, and speculative features. Optimize for *minimum unnecessary complexity + maximum useful correctness*.
5. **Safe Execution Boundaries**: Code in repositories is potentially untrusted. Never pass unvetted strings into shell interpreters. Execute commands with explicit argument vectors, strict timeouts, and output truncation limits.

---

## 2. Development Setup

### Prerequisites
- Python 3.10 or newer (tested up to Python 3.14)
- Git (2.25+)
- (Optional, recommended for multi-language CST analysis) Tree-sitter parsers:
  ```bash
  pip install tree-sitter tree-sitter-python tree-sitter-javascript tree-sitter-typescript tree-sitter-go tree-sitter-rust tree-sitter-java
  ```

### Local Installation
```bash
git clone https://github.com/Consecutive-Gen-AI/Agent-Proof-.git
cd Agent-Proof-
pip install -e .[dev]
```

### Running Tests
Every contribution must pass the full test suite without regressions:
```bash
pytest -v
```

---

## 3. Code Standards & Architecture

- **Static Typing**: All new code must include explicit type annotations. Use Python standard `typing` and dataclasses.
- **Error Handling**: Handle partial results, missing tools, and subprocess timeouts gracefully. Never silently convert errors into success states.
- **Honest Analysis Level**: When analyzing code, report the real `AnalysisLevel` (`FULL_SEMANTIC`, `STRUCTURAL_AST`, `BASIC_HEURISTIC`, or `UNSUPPORTED`). Never claim full understanding when using heuristic fallbacks.
- **Modular Subsystems**:
  - `src/agentproof/git/`: Git diff inspection and symbol extraction.
  - `src/agentproof/structure/`: Language-independent CST parsing and symbol graph.
  - `src/agentproof/detector/`: Tool discovery and configuration analysis.
  - `src/agentproof/analyzer/`: Static file classification and risk warnings.
  - `src/agentproof/impact/`: Downstream dependency and test mapping.
  - `src/agentproof/drift/`: Task-to-change alignment and drift detection.
  - `src/agentproof/missing/`: Missing tests, docs, and validation detection.
  - `src/agentproof/adversarial/`: Boundary and stress test generation.
  - `src/agentproof/graph/`: Deterministic ProofGraph modeling.
  - `src/agentproof/passport/`: Cryptographic, portable ProofPassports.
  - `src/agentproof/integration/`: Agent-agnostic context ingestion and feedback formatting.

---

## 4. Testing Expectations

Contributions without tests will not be accepted. We follow a multi-tier testing strategy:

1. **Unit Tests** (`tests/unit/`): Deterministic validation of individual functions, analyzers, and parsers.
2. **Integration Tests** (`tests/integration/`): End-to-end repository scenarios verifying CLI workflows, Git interactions, and output formats.
3. **Adversarial & Regression Tests**: If you fix a bug or add a detector, supply a test verifying that the flaw is actively caught.

---

## 5. Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. Commit logical, focused changes with informative commit messages:
   ```bash
   git commit -m "feat(structure): add Rust trait symbol extraction"
   ```
3. Run the full test suite locally:
   ```bash
   pytest
   ```
4. Submit a Pull Request targeting `main`. Fill out the [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md) completely, including evidence of test results and backwards compatibility verification.
5. All CI checks must pass before merging.
