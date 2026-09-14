# Agent Integration Guide

AgentProof is an **agent-agnostic verification and evidence layer for AI-generated software changes**.

Rather than trusting an AI agent's claim that a code edit is complete and safe, AgentProof runs independent checks, traces impact, generates adversarial cases, and delivers actionable feedback.

This document describes how to integrate AgentProof with AI coding agents including **Claude Code**, **Cursor**, **OpenAI Codex**, **Gemini CLI**, and custom autonomous workflows.

---

## 1. Architectural Model

```text
┌───────────────────────────┐
│     AI Coding Agent       │
│ (Claude, Codex, Cursor)   │
└─────────────┬─────────────┘
              │ 1. Supplies task intent & intended files
              ▼
┌───────────────────────────┐
│        AgentProof         │
│   Verification Pipeline   │
└─────────────┬─────────────┘
              │ 2. Returns token-efficient AgentFeedback
              ▼
┌───────────────────────────┐
│     Agent Context / PR    │
│  (Fixes blockers/omits)   │
└───────────────────────────┘
```

---

## 2. Ingesting Agent Context

AgentProof accepts task intent and change scope through three non-intrusive channels:

### Option A: CLI Flags
```bash
agentproof verify --task "Fix JWT token expiration handling"
```

### Option B: Structured JSON Input File (or Stdin)
Use `--agent-input <file>` or `--agent-input -` (stdin):
```bash
agentproof verify --agent-input agent_context.json
```
**`agent_context.json` format:**
```json
{
  "agent": "claude-code",
  "model": "claude-3-7-sonnet",
  "task": "Fix JWT token expiration handling in auth module",
  "intended_files": [
    "pkg/auth/token.go",
    "pkg/auth/session.go"
  ],
  "session_id": "sess-987654",
  "metadata": {
    "pr_number": 42
  }
}
```

### Option C: Environment Variables
External agent runners can inject environment variables without modifying execution arguments:
```bash
export AGENTPROOF_TASK="Fix JWT token expiration handling"
export AGENTPROOF_AGENT_NAME="claude-code"
export AGENTPROOF_INTENDED_FILES="pkg/auth/token.go,pkg/auth/session.go"
agentproof verify
```

---

## 3. Agent-Optimized Feedback Protocol

By default, AgentProof formats output for human terminals. When invoking from an AI agent or CI bot, pass `--agent`:

```bash
agentproof verify --agent
```

### Markdown Mode (`--agent`)
Outputs high-signal, token-efficient markdown ready to be inserted directly into an LLM's context window:

```markdown
# AgentProof Verification: FAILED

**Status**: ACTION REQUIRED
**Summary**: 1 validation check(s) failed: pytest (exit 1).

## Blockers to Fix
- [!] Check failed: pytest [FAIL]: AssertionError: assert token.is_valid() == True
- [!] MISSING_SECURITY_VALIDATION: Changes in security-sensitive files (pkg/auth/token.go) lack corresponding security tests.

## Missing Work / Omissions
- [?] MISSING_SECURITY_VALIDATION: Changes in security-sensitive files (pkg/auth/token.go) lack corresponding security tests.

## Scope Drift
- **Level**: HIGH
- **Details**: 2 file(s) modified outside expected task scope: frontend/theme.css

## Passed Verification Checks
- [x] ruff (lint)
- [x] mypy (typecheck)
```

### JSON Mode (`--agent --json`)
Outputs machine-parseable JSON for programmatic agent loops:

```bash
agentproof verify --agent --json
```

**JSON Schema:**
```json
{
  "verdict": "FAILED",
  "is_verified": false,
  "exit_code": 1,
  "summary": "1 validation check(s) failed: pytest (exit 1).",
  "blockers": [
    "Check failed: pytest [FAIL]: assert False"
  ],
  "drift_level": "NONE",
  "drift_description": null,
  "missing_work": [],
  "adversarial_findings": [],
  "passed_checks": [
    "ruff (lint)"
  ]
}
```

---

## 4. Exit Codes & Automation Loop

| Exit Code | Meaning | Agent Action Required |
|:---:|:---|:---|
| `0` | Change is `VERIFIED` or `VERIFIED_WITH_WARNINGS` | Proceed to commit / create pull request. |
| `1` | Verification `FAILED`, `BLOCKED`, or `INCONCLUSIVE` | Review blockers in feedback and remediate. |
| `2` | Configuration / execution runtime error | Review local environment setup. |

---

## 5. Integrating with Common Coding Agents

### Claude Code
Add AgentProof as a post-edit verification hook in `.claude/config.json` or run directly in prompt:
```bash
claude "Review my changes and verify them with agentproof verify --agent"
```

### Cursor / Roo Code
In `.cursorrules` or custom agent system prompt:
```text
After modifying code, run `agentproof verify --agent`. If the status is 'ACTION REQUIRED', resolve all items under 'Blockers to Fix' before reporting completion.
```

### Model Context Protocol (MCP) Tool Definition
You can expose AgentProof to any MCP-compliant agent using this tool schema:

```json
{
  "name": "agentproof_verify",
  "description": "Run independent verification, change impact analysis, and missing work detection on the current Git working tree.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "task": {
        "type": "string",
        "description": "The goal or description of the current code change."
      },
      "adversarial": {
        "type": "boolean",
        "description": "Whether to generate and execute boundary stress tests against changed functions."
      }
    }
  }
}
```
Tool implementation invokes:
```python
import subprocess
def agentproof_verify(task: str = "", adversarial: bool = False):
    cmd = ["agentproof", "verify", "--agent"]
    if task:
        cmd.extend(["--task", task])
    if adversarial:
        cmd.append("--adversarial")
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout
```
