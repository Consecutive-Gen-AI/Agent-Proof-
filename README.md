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

## AgentProof V3 Capabilities

AgentProof V3 introduces deterministic **Task-to-Change Drift Detection**, an evidence-based **Missing Work Analyzer**, and an expanded **8-Section Verification Report**:

### 1. Task-to-Change Drift Detection
Compares the intended task with actual repository changes:
```text
TASK / INTENDED CHANGE
        ↓
EXPECTED CHANGE AREA
        ↓
ACTUAL CHANGE
        ↓
IMPACTED AREA
```
- **Deterministic Alignment**: Extracts task keywords, explicit paths, symbol references, and domain categories (`auth`, `db`, `api`, `cli`, `ui`, `billing`, `test`).
- **Explainable Findings**: Identifies files modified outside expected scope and explains *why* (no keyword match, no symbol link, outside impact graph).
- **Drift Rating**: Computes `DriftLevel` (`NONE`, `LOW`, `MEDIUM`, `HIGH`, `UNKNOWN`) with confidence scores.

### 2. Evidence-Based Missing Work Detection
Detects omitted work and verification gaps based on repository signals:
- `MISSING_TESTS_FOR_CHANGE`: Source files modified without any corresponding test file updates.
- `MISSING_DATABASE_MIGRATION`: Models or schema definitions modified without migration scripts.
- `MISSING_CLI_TEST`: CLI command parser or argument handling modified without CLI test updates.
- `MISSING_LOCKFILE_UPDATE`: Dependency manifests modified without corresponding lockfile synchronization.
- `MISSING_SECURITY_VALIDATION`: Security/auth boundaries modified without security-related test coverage.
- `MISSING_ERROR_HANDLING_OR_TEST`: Error-handling modifications without failure-path test coverage.
- `REMOVED_BEHAVIOR_WITHOUT_TEST_UPDATE`: Code deletions without corresponding test refactoring.

### 3. Change Impact Analysis (V2 Foundation)
- Identifies likely affected areas across the repository:
  $$\text{Changed File} \longrightarrow \text{Changed Symbol} \longrightarrow \text{Dependent Callers / Imports} \longrightarrow \text{Related Tests} \longrightarrow \text{Config / Deps}$$
- Maps dependent callers and related test suites for every modified module.
- Calculates an overall **Impact Rating** (`LOW`, `MEDIUM`, `HIGH`).

### 4. Evidence-Backed Risk Findings
Every finding provides three structured dimensions:
- **What was detected**
- **Why it matters**
- **Supporting evidence**

### 5. Structured 8-Section Reports
Both terminal and JSON formats (Schema v1.2.0) clearly separate repository facts, deterministic analysis, and tool execution:
1. `CHANGE` (Repository Facts)
2. `IMPACT` (Change Impact Analysis)
3. `DRIFT` (Task-to-Change Drift Analysis)
4. `MISSING WORK` (Omission & Gap Detection)
5. `CHECKS` (Validation Execution)
6. `RISKS & FINDINGS` (AgentProof Analysis)
7. `EVIDENCE` (Facts & Provenance)
8. `FINAL VERDICT`

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

### Verify with Task Intent (Drift Analysis)
Supply task context via command-line argument:
```bash
agentproof verify --task "Fix authentication token expiration"
```

Or supply task context via a text file:
```bash
agentproof verify --task-file task_description.txt
```

### Machine-Readable JSON Output (Schema v1.2.0)
Output the complete verification report as structured JSON:
```bash
agentproof verify --task "Refactor CLI" --json
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
  --task TASK           Task description or instruction string to check drift against
  --task-file TASK_FILE
                        Path to file containing task description to check drift against
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

## Known Limitations & Design Boundaries

AgentProof V3 adheres strictly to deterministic analysis principles:
1. **Deterministic Intent Extraction**: Task parsing is rule-based and keyword/token-driven. It avoids hallucinations and probabilistic guesses, but does not perform complex semantic or natural language reasoning.
2. **Standard Library AST**: Symbol extraction and caller reference tracking currently target Python projects out of the box. Multi-language AST parsing (Tree-sitter, language servers) is planned for future releases.
3. **No Fake Intelligence**: AgentProof will never manufacture evidence or claim an assertion is "proven" without verifiable artifacts (exit codes, AST nodes, git diffs).
4. **Local-First Execution**: Validation checks run in local subprocesses within the repository root. Isolated containerization and sandbox environments are planned for future versions.

---

## License

Apache-2.0

