# Security Policy

The AgentProof project takes software security seriously. Because AgentProof executes commands, inspects diffs, and verifies changes produced by autonomous coding agents and external contributors, defensive engineering is built directly into our architectural foundation.

---

## 1. Reporting a Vulnerability

Please **do not** report security vulnerabilities via public GitHub issues or discussions.

If you discover a vulnerability or security flaw in AgentProof:

1. Send an email to **security@agentproof.dev** (or open a private GitHub Security Advisory).
2. Include:
   - A clear description of the vulnerability.
   - Step-by-step reproduction steps or a proof-of-concept repository.
   - The affected version or commit SHA.
   - Any potential impact on host environments or CI pipelines.
3. You will receive an initial response within 48 hours. We coordinate patches and public disclosures responsibly.

---

## 2. Security Model & Execution Boundaries

AgentProof treats repositories, commits, diffs, and agent prompts as **potentially untrusted inputs**.

### Safe Subprocess Execution
- **Argument Vectors Only**: External processes are executed strictly via argument lists (e.g. `['pytest', '-v']`) rather than string-interpolated shell commands (`shell=False`).
- **Execution Sandboxing & Timeouts**: Subprocesses are constrained by timeouts (default 30–60s) to prevent resource exhaustion and hanging processes.
- **Output Truncation**: Standard output and error streams are capped to prevent memory-exhaustion attacks from malicious or runaway test runners.
- **Safe Environment**: Subprocess executions do not forward credentials, authentication tokens, or private secrets into untrusted execution targets.

### Adversarial Verification Safety
- Generated adversarial tests run in isolated temporary processes with strict execution timeouts.
- Code from repositories is never executed automatically unless explicitly configured via safe verification flags (e.g. `--adversarial`).

### Dependency & Ingestion Safety
- Context ingested from agents (via `--agent-input`, files, or environment variables) is validated and typed before being parsed.
- No dynamic code evaluation (`eval`, `exec` on unvetted strings) is permitted in AgentProof's core analysis engine.
