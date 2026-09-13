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

## AgentProof V4 Capabilities

AgentProof V4 introduces the first real **Evidence Graph (Proof Graph)**, the **Proof Passport** system, and **Verdict Traceability** with deterministic integrity hashing:

```text
TASK ──> CHANGE ──> IMPACT ──> CHECKS ──> EVIDENCE ──> FINDINGS ──> VERDICT
```

### 1. Evidence Graph (Proof Graph)
Connects all repository facts, changes, symbols, and test outcomes into a queryable, typed graph:
- **Typed Nodes**: `TASK`, `FILE`, `SYMBOL`, `CHANGE`, `CHECK`, `EVIDENCE`, `RISK_FINDING`, `DRIFT_FINDING`, `MISSING_WORK`, `VERDICT`.
- **Relational Edges**:
  - `TARGETS` (`TASK -> FILE`)
  - `CONTAINS` (`CHANGE -> FILE` or `FILE -> SYMBOL`)
  - `MODIFIES` (`CHANGE -> SYMBOL`)
  - `IMPACTS` (`SYMBOL -> SYMBOL` or `FILE -> FILE`)
  - `VALIDATED_BY` (`CHANGE -> CHECK`)
  - `PRODUCES` (`CHECK -> EVIDENCE`)
  - `SUPPORTS` (`EVIDENCE -> FINDING`)
  - `TRIGGERS` (`FILE/CHANGE -> RISK_FINDING`, `DRIFT_FINDING`, `MISSING_WORK`)
  - `AFFECTS` (`FINDING -> VERDICT` or `EVIDENCE -> VERDICT`)

### 2. Verdict Traceability
Enables developers and CI systems to answer:
> *"Why did AgentProof reach this verdict, and what specific evidence supports it?"*
Every check result, risk warning, drift finding, and missing work omission connects directly to the root `VERDICT` node with human-readable rationale and linked evidence records.

### 3. Machine-Readable Proof Passport (Schema v1.0.0)
A concise, portable verification summary artifact generated deterministically from the Proof Graph and verification run:
- Repository identity and pinned Git commit SHA.
- Change statistics (files, symbols, lines added/deleted).
- Change blast radius impact summary.
- Scope drift detection status.
- Missing work & omission analysis.
- Execution check statuses, exit codes, and durations.
- Unified findings list (risks, drift, missing work).
- Evidence references with SHA-256 integrity hashes.
- Tamper-evident passport digest.

### 4. Deterministic Integrity & Provenance
- Canonical JSON serialization (sorted dictionary keys, compact delimiters).
- Cryptographic SHA-256 digests over evidence records and the full passport to provide tamper-evident provenance without claiming asymmetric cryptographic signatures.

### 5. Task-to-Change Drift Detection (V3 Foundation)
- Compares intended task with actual repository changes.
- Computes `DriftLevel` (`NONE`, `LOW`, `MEDIUM`, `HIGH`, `UNKNOWN`) with explainable rationale.

### 6. Evidence-Based Missing Work Detection (V3 Foundation)
- Detects omitted engineering work: missing tests, missing migrations, missing lockfile updates, and unvalidated CLI changes.

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

### 1. Verify Working Tree (8-Section Report)
Inspect changes in the current repository and run verification:
```bash
agentproof verify
```

With task intent (to evaluate scope drift):
```bash
agentproof verify --task "Fix authentication token expiration"
```

Structured JSON output (Schema v1.2.0):
```bash
agentproof verify --json
```

### 2. Generate Proof Passport
Generate and inspect the concise Proof Passport in your terminal:
```bash
agentproof passport
```

With task intent:
```bash
agentproof passport --task "Refactor CLI options"
```

Output machine-readable Proof Passport JSON (Schema v1.0.0):
```bash
agentproof passport --json
```

### 3. Inspect Proof Graph
Inspect node counts, relationships, and verdict traceability:
```bash
agentproof graph
```

Output the complete, structured Proof Graph as JSON:
```bash
agentproof graph --json
```

### 4. CLI Options Reference
```text
subcommands:
  verify                Inspect Git changes, analyze drift and missing work, and run verification checks
  passport              Generate and inspect a machine-readable Proof Passport
  graph                 Inspect the Proof Graph connecting tasks, changes, evidence, and verdict

options:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -d, --target-dir TARGET_DIR
                        Target repository directory (default: .)
  -t, --task TASK       Task description or intent to evaluate scope drift against
  --task-file TASK_FILE Path to file containing task description
  --staged              Inspect only staged changes instead of the entire working tree
  --json                Output structured results as JSON
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

AgentProof V4 adheres strictly to deterministic evidence principles:
1. **Deterministic Proof Graph**: Every node and edge is derived directly from observable repository facts, AST parsing, or tool execution. No speculative relationships are fabricated.
2. **Tamper-Evident Digest vs. Signatures**: Integrity digests are canonical SHA-256 hashes to detect accidental modifications. Cryptographic key-pair signing (PKI / notary) is reserved for future versions.
3. **Local Graph Storage**: The Proof Graph is generated in-memory and serialized as JSON on-demand. Persistent graph databases are not required for local operations.
4. **Standard Library AST**: Symbol extraction and caller reference tracking currently target Python projects out of the box. Multi-language AST parsing (Tree-sitter, LSP) is planned for future releases.
5. **No Fake Intelligence**: In alignment with `AGENTS.md`, AgentProof will never manufacture evidence or label an inference as "proven" without verifiable artifacts.

---

## License

Apache-2.0


