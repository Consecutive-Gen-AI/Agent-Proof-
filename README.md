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

## AgentProof V2 Capabilities

AgentProof V2 upgrades the verification engine into an intelligent change-analysis, impact-mapping, and evidence system:

### 1. Deeper Git Change Analysis
- **Staged vs. Unstaged Breakdown**: Accurately differentiates staged changes from unstaged working tree changes.
- **Symbol Extraction**: Extracts modified, added, and deleted classes, functions, and methods directly from diff hunks and Python AST.
- **Rename & Deletion Tracking**: Tracks renamed files (`old_path -> new_path`) and deleted modules.

### 2. Deterministic Change Impact Analysis
- Identifies likely affected areas across the repository:
  $$\text{Changed File} \longrightarrow \text{Changed Symbol} \longrightarrow \text{Dependent Callers / Imports} \longrightarrow \text{Related Tests} \longrightarrow \text{Config / Deps}$$
- Maps dependent callers and related test suites for every modified module.
- Calculates an overall **Impact Rating** (`LOW`, `MEDIUM`, `HIGH`).

### 3. Evidence-Backed Risk Findings
Every finding provides three structured dimensions:
- **What was detected**
- **Why it matters**
- **Supporting evidence**

Findings include:
- `TESTS_REDUCED`: Flags when test files are removed or test line count drops significantly.
- `API_SURFACE_MODIFIED`: Flags edits to public interfaces, `__init__.py`, or public API contracts.
- `IMPORTANT_FILE_DELETED_OR_RENAMED`: Alerts on renames or deletions of core files.
- `UNTESTED_SOURCE_CHANGE`: Detects modified source files that lack test coverage.
- `SECURITY_SENSITIVE_MODIFIED`: Highlights modifications to auth, tokens, crypto, and security boundaries.
- `CI_WORKFLOW_MODIFIED`: Flags changes to CI/CD pipeline definitions (`.github/workflows/*`).
- `DEPENDENCY_MODIFIED`: Monitors changes to package manifests and lockfiles.
- `LARGE_DIFF`: Warns on high-blast-radius changes (> 500 lines or > 25 files).

### 4. Rich Evidence Provenance
- Check results include exact duration, exit codes, command argument vectors, output summaries, and the pinned Git commit SHA.
- Automatic secret token and credential masking.

### 5. Structured 6-Section Reports
Both terminal and JSON formats clearly distinguish repository facts, tool execution, and analysis:
1. `CHANGE` (Repository Facts)
2. `IMPACT` (Change Impact Analysis)
3. `CHECKS` (Validation Execution)
4. `RISKS & FINDINGS` (AgentProof Analysis)
5. `EVIDENCE` (Facts & Provenance)
6. `FINAL VERDICT`

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
Inspect changes in the current repository and run verification:
```bash
agentproof verify
```

### Machine-Readable JSON Output (Schema v1.1.0)
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
