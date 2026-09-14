# AgentProof

<p align="center">
  <strong>Let AI write the code. AgentProof makes the AI prove what it changed.</strong>
</p>

<p align="center">
  <a href="#quickstart-setup-guide"><img src="https://img.shields.io/badge/quickstart-guide-blue.svg?style=flat-square" alt="Quickstart"></a>
  <a href="https://opensource.org/licenses/Apache-2.0"><img src="https://img.shields.io/badge/license-Apache%202.0-blue.svg?style=flat-square" alt="License: Apache 2.0"></a>
  <img src="https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13%20%7C%203.14-blue.svg?style=flat-square" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/tests-139%20passed-brightgreen.svg?style=flat-square" alt="Tests">
  <img src="https://img.shields.io/badge/core%20dependencies-0-success.svg?style=flat-square" alt="Core Dependencies: 0">
  <img src="https://img.shields.io/badge/multi--language-Tree--sitter%20CST-orange.svg?style=flat-square" alt="Multi-Language CST">
</p>

---

AgentProof is an **agent-agnostic verification and evidence layer for software changes produced by AI coding agents or human developers**.

When an AI coding assistant modifies your repository, it usually claims:
> *"I have fixed the issue, updated the logic, and all tests are passing!"*

**AgentProof does not trust that claim.**

Instead of believing the agent's assertions, AgentProof independently:
1. **Analyzes your Git diff**: Extracts changed functions, classes, interfaces, and file categories across multiple programming languages.
2. **Maps change impact**: Traces the blast radius to find downstream modules, affected callers, and relevant test suites.
3. **Detects scope drift**: Evaluates your task prompt against what the agent *actually* modified, flagging unrequested edits or accidental file touches.
4. **Catches omitted work**: Flags missing unit tests, omitted error handling, and unaddressed security validations.
5. **Runs adversarial boundary verification**: Generates deterministic stress tests (null, boundary, type, and error paths) to actively break the implementation before you merge.
6. **Produces a cryptographic Proof Passport & Proof Graph**: Emits an auditable SHA-256 digest summarizing all independent evidence.

---

## The Core Philosophy

AgentProof enforces a strict boundary between assertions and facts:

| Concept | What it Means | Examples |
|:---|:---|:---|
| **Agent Assertions** | Statements made by the AI coding assistant. *Never accepted as proof.* | *"All tests pass"*, *"The fix is completely safe"*, *"Only the auth module was touched"*. |
| **Independent Evidence** | Facts collected or executed independently by AgentProof. | Test subprocess exit codes, Tree-sitter CST parsing, downstream dependency graph, and adversarial test execution. |

---

## 🚀 Quickstart Setup Guide

Anyone can install and use AgentProof on their existing projects in seconds.

### Step 1: Installation

#### Option A: Install directly via `pip` from GitHub
```bash
# Core installation (Zero external dependencies, standard library only)
pip install git+https://github.com/agentproof/agentproof.git

# With multi-language Tree-sitter CST parsing support (Python, JS, TS, Go, Rust, Java)
pip install "agentproof[treesitter] @ git+https://github.com/agentproof/agentproof.git"
```

#### Option B: Clone and install locally for development
```bash
git clone https://github.com/agentproof/agentproof.git
cd agentproof
pip install -e ".[treesitter]"
```

Verify installation:
```bash
agentproof --version
```

---

### Step 2: How to Use AgentProof on Your Own Project

You can run AgentProof on **any** repository (Django, FastAPI, React/Next.js, Go, Rust, Java, or multi-language monorepos).

#### 1. Navigate to your project directory
```bash
cd /path/to/my-project
```

#### 2. Let your AI agent (or yourself) make code changes
For example, you ask Cursor, Claude Code, GitHub Copilot, or Aider:
> *"Fix the authentication token expiration logic in `auth/tokens.py`"*

#### 3. Inspect the changes and blast radius
Before running tests, check what symbols changed and what other parts of the repo might break:
```bash
agentproof inspect
```
*Output displays: changed files, added/deleted symbols (functions, classes), downstream callers, and related test files.*

#### 4. Verify against your task intent (Catch Agent Drift)
Run your repository's test suite and detect if the AI drifted outside the requested scope:
```bash
agentproof verify --task "Fix the authentication token expiration logic in auth/tokens.py"
```

#### 5. Stress-test the changed code with Adversarial Verification
Do not just trust the author's tests. Actively challenge the modified functions with boundary attacks:
```bash
agentproof verify --adversarial
```

#### 6. Generate an auditable Proof Passport
Generate a clean, machine-readable summary with a cryptographic SHA-256 digest for pull requests:
```bash
agentproof passport
```

---

## 🤖 Using AgentProof with AI Coding Tools

### Cursor Integration
Add this rule to your project's `.cursorrules` or `.cursor/rules` file so Cursor automatically verifies its work:

```markdown
# AgentProof Verification Rule
After completing any feature implementation or bug fix, ALWAYS run:
`agentproof verify --agent --adversarial`

If the verdict is anything other than VERIFIED, review the findings in the output,
fix the issues, and re-run verification before reporting completion.
```

### Claude Code & Terminal Agents
When using terminal-based agents like Claude Code or Codex CLI, pass the `--agent` flag for a concise, token-efficient summary designed specifically for LLM context windows:

```bash
agentproof verify --agent --task "Refactor payment webhook processing"
```

To ingest structured JSON context from automated agent pipelines:
```bash
agentproof verify --agent-input agent_context.json --agent --json
```

---

## ⚙️ Using AgentProof in GitHub Actions CI

Enforce independent verification on every Pull Request by creating `.github/workflows/agentproof.yml` in your repository:

```yaml
name: AgentProof Verification

on:
  pull_request:
    branches: [main, master]
  push:
    branches: [main, master]

jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install AgentProof
        run: |
          pip install "agentproof[treesitter] @ git+https://github.com/agentproof/agentproof.git"

      - name: Run Independent Proof Verification
        run: |
          agentproof verify --strict --adversarial
```

---

## 🐍 Programmatic Python API

You can also integrate AgentProof directly into custom Python tools, test runners, or agent harnesses:

```python
from pathlib import Path
from agentproof.analyzer.change import ChangeAnalyzer
from agentproof.core.models import TaskContext
from agentproof.verification.executor import VerificationExecutor

# 1. Inspect working tree changes
analyzer = ChangeAnalyzer()
change = analyzer.analyze(Path("."))
print(f"Changed files: {len(change.files)}")

# 2. Configure verification with explicit task intent
task = TaskContext(description="Fix authentication token expiration")
executor = VerificationExecutor(task=task)

# 3. Execute independent verification
report = executor.verify(Path("."), change=change)

# 4. Check the verdict
print(f"Verdict: {report.verdict.state.value}")
for finding in report.findings:
    print(f"[{finding.severity.value}] {finding.title}: {finding.description}")
```

---

## Language Support Matrix

AgentProof provides a multi-tiered analysis engine to ensure cross-language coverage while reporting honest `AnalysisLevel` values without fabricating semantic relationships:

| Language | Primary Parser | Fallback Parser | Symbol Extraction | Import / Reference Tracking | Adversarial Verification |
|:---|:---|:---|:---:|:---:|:---:|
| **Python** | Tree-sitter CST | Python `ast` | Full (functions, classes, methods) | Full (modules, imports, calls) | Full (native execution sandbox) |
| **JavaScript** | Tree-sitter CST | Lexical Regex | Full (functions, classes, exports) | Full (ES imports, require, calls) | Target Discovery / Static |
| **TypeScript** | Tree-sitter CST | Lexical Regex | Full (interfaces, types, functions) | Full (TS imports, references) | Target Discovery / Static |
| **Go** | Tree-sitter CST | Lexical Regex | Full (funcs, structs, interfaces) | Full (package imports, calls) | Target Discovery / Static |
| **Rust** | Tree-sitter CST | Lexical Regex | Full (fn, struct, trait, impl) | Full (use declarations, paths) | Target Discovery / Static |
| **Java** | Tree-sitter CST | Lexical Regex | Full (classes, interfaces, methods) | Full (package imports, methods) | Target Discovery / Static |
| *Other* | Lexical Regex | N/A | Heuristic diff headers | Extension heuristics | Static checks |

---

## CLI Command Reference

AgentProof provides 4 first-class subcommands:

```text
usage: agentproof [-h] [-v] [-d TARGET_DIR] {inspect,verify,passport,graph} ...
```

| Subcommand | Description | Common Usage |
|:---|:---|:---|
| **`inspect`** | Inspect Git changes, modified symbols, and change impact blast radius. | `agentproof inspect` |
| **`verify`** | Run independent verification checks, detect scope drift, and find missing work. | `agentproof verify --task "..." --adversarial` |
| **`passport`** | Generate an auditable Proof Passport with a SHA-256 cryptographic digest. | `agentproof passport --json` |
| **`graph`** | Inspect the Proof Graph connecting tasks, changes, checks, evidence, and verdict. | `agentproof graph` |

### Global & Verification Flags

| Flag | Description |
|:---|:---|
| `-t, --task TEXT` | Task description or user prompt to evaluate scope drift against. |
| `--task-file FILE` | Path to a text file containing the task description. |
| `--adversarial` | Run deterministic adversarial verification attacks against changed functions. |
| `--agent` | Format output optimized for AI coding agent consumption (token-efficient). |
| `--agent-input FILE` | Ingest structured JSON agent context from Claude Code, Cursor, or Codex. |
| `--staged` | Inspect only staged changes instead of the entire working tree. |
| `--json` | Output structured, machine-readable JSON. |
| `--strict` | Treat `INCONCLUSIVE` verdicts as non-zero exit codes (useful in CI). |
| `--timeout SEC` | Execution timeout per check in seconds (default: 60s). |
| `-d, --target-dir DIR` | Target repository directory (default: `.`). |
| `--no-color` | Disable ANSI color sequences in terminal output. |

---

## The 7 Explicit Verdict States

AgentProof never reduces verification to a naive boolean:

| Verdict | Meaning | CI Exit Code |
|:---|:---|:---:|
| **`VERIFIED`** | All independent checks passed, no blockers, no critical omissions. | `0` |
| **`VERIFIED_WITH_WARNINGS`** | Core checks passed, but non-blocking risks or low drift were detected. | `0` |
| **`INCONCLUSIVE`** | No checks ran or checks were unavailable (requires developer investigation). | `0` *(or `1` if `--strict`)* |
| **`BLOCKED`** | Adversarial verification triggered a reproducible failure on changed code. | `1` |
| **`FAILED`** | One or more existing tests, linters, or typecheckers failed. | `1` |
| **`ERROR`** | Verification could not complete due to timeouts or infrastructure failure. | `1` |
| **`NOT_EVALUATED`** | Repository state was not evaluated. | `1` |

---

## Security Engineering

AgentProof treats repository content and AI-generated code as potentially untrusted input:
- **Zero Shell Interpolation**: All external commands and adversarial tests run via direct argument lists (`subprocess.run([sys.executable, "-c", ...])`). `shell=True` is strictly forbidden.
- **Resource Constraints**: Subprocesses execute with timeouts (default 5–60s) and memory-safe output truncation buffers (64 KB).
- **Safe Defaults**: Destructive commands and unauthorized network operations are prevented by design.

---

## Repository Documentation

All detailed reference documentation is organized in the [`docs/`](./docs) directory:

- [Engineering Constitution (`docs/AGENTS.md`)](./docs/AGENTS.md)
- [Agent Integration Guide (`docs/AGENT_INTEGRATION.md`)](./docs/AGENT_INTEGRATION.md)
- [Contributing Guidelines (`docs/CONTRIBUTING.md`)](./docs/CONTRIBUTING.md)
- [Security Policy (`docs/SECURITY.md`)](./docs/SECURITY.md)
- [Changelog (`docs/CHANGELOG.md`)](./docs/CHANGELOG.md)

---

## License

AgentProof is open-source software licensed under the [Apache-2.0 License](./LICENSE).
