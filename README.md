# AgentProof

> **Let AI write the code. AgentProof makes the AI prove what it changed.**

AgentProof is an **agent-agnostic verification and evidence layer for AI-generated software changes**.

It independently collects, analyzes, verifies, and presents evidence about software changes produced by AI coding agents or human developers before changes are merged or deployed.

---

## The Core Philosophy

AgentProof distinguishes between:
- **Agent Assertions**: *"All tests pass"*, *"The fix is safe"*, *"Only authentication was touched"*.
- **Independent Evidence**: Direct tool execution exits, git diff analysis, static type checking, risk heuristics, and reproducible test results.

**Agent assertions are never treated as proof.**

---

## AgentProof V1 Features

- **Git Inspection**: Automatically detects git repository state, working tree modifications, staged changes, and untracked files with added/deleted line statistics.
- **Project Tool Auto-Detection**: Detects applicable test frameworks, linters, and type checkers (Python, Node/TypeScript, Rust, Go) safely without arbitrary script execution.
- **Secure Execution**: Subprocess runner strictly using argument vectors, isolated environment variables, strict timeouts, and memory-safe output capping.
- **Zero Fake Completeness**: If test tools are not configured or missing, AgentProof honestly reports `UNAVAILABLE` and assigns `INCONCLUSIVE` rather than fabricating a pass.
- **Static Change & Risk Analysis**:
  - Automatically categorizes files into Source, Test, Dependency, Configuration, Documentation, Security-Sensitive.
  - Detects **Missing Work** (source code changed without corresponding test additions).
  - Flags **Dependency Modifications**, **CI/CD Workflow Alterations**, and **Large Diff Blast Radii**.
- **Dual Output Formats**:
  - Clean, colorized terminal reports for developer UX.
  - Versioned, machine-readable JSON reports for CI/CD automation.

---

## Installation

### Local Development Install
Install in editable mode:
```bash
pip install -e .
```

Or install with development dependencies:
```bash
pip install -e ".[dev]"
```

---

## CLI Usage

### Verify Working Tree
Inspect uncommitted changes in the current repository and run validation checks:
```bash
agentproof verify
```

### Machine-Readable JSON Output
Output the complete verification report as structured JSON:
```bash
agentproof verify --json
```

### Inspect Only Staged Changes
Verify changes that have been staged with `git add`:
```bash
agentproof verify --staged
```

### Specify Target Directory
Point to any repository directory:
```bash
agentproof verify -d /path/to/repo
```

### CLI Options Reference
```text
options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -d, --target-dir TARGET_DIR
                        Target repository directory (default: .)
  --staged              Inspect only staged changes instead of the entire working tree
  --json                Output structured verification results as JSON
  --no-color            Disable ANSI color output in terminal
  --timeout TIMEOUT     Execution timeout per check in seconds (default: 60)
  --strict              Treat INCONCLUSIVE verdicts as non-zero exit codes in CI
```

---

## Exit Codes

- `0`: Change is `VERIFIED` or `VERIFIED_WITH_WARNINGS` (or `INCONCLUSIVE` in non-strict mode).
- `1`: Change `FAILED` or encountered execution `ERROR` (or `INCONCLUSIVE` in `--strict` mode).
- `2`: Target directory is not a Git repository or Git is unavailable.

---

## License

Apache-2.0
