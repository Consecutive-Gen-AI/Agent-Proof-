"""Agent-agnostic context ingestion for external AI coding agents and human developers."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agentproof.core.models import TaskContext


@dataclass
class AgentContext:
    """Standardized context supplied by an AI coding agent or development workflow."""
    task_intent: Optional[str] = None
    agent_name: Optional[str] = None
    model: Optional[str] = None
    session_id: Optional[str] = None
    intended_files: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_intent": self.task_intent,
            "agent_name": self.agent_name,
            "model": self.model,
            "session_id": self.session_id,
            "intended_files": self.intended_files,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentContext:
        return cls(
            task_intent=data.get("task_intent") or data.get("task") or data.get("prompt"),
            agent_name=data.get("agent_name") or data.get("agent"),
            model=data.get("model"),
            session_id=data.get("session_id") or data.get("session"),
            intended_files=data.get("intended_files", []),
            metadata=data.get("metadata", {}),
        )

    def to_task_context(self) -> TaskContext:
        """Convert AgentContext into AgentProof's internal TaskContext."""
        from agentproof.task.context import TaskParser
        parser = TaskParser()
        ctx = parser.parse(self.task_intent or "")
        for path in self.intended_files:
            clean_p = path.replace("\\", "/")
            if clean_p not in ctx.referenced_paths:
                ctx.referenced_paths.append(clean_p)
        return ctx


class AgentContextIngestion:
    """Utilities to ingest AgentContext across environment, JSON files, or stdin."""

    @classmethod
    def from_env(cls) -> Optional[AgentContext]:
        """Ingest context from AGENTPROOF_* environment variables."""
        task = os.getenv("AGENTPROOF_TASK") or os.getenv("AGENTPROOF_PROMPT")
        agent_name = os.getenv("AGENTPROOF_AGENT_NAME") or os.getenv("AGENTPROOF_AGENT")
        model = os.getenv("AGENTPROOF_MODEL")
        session_id = os.getenv("AGENTPROOF_SESSION_ID")
        raw_files = os.getenv("AGENTPROOF_INTENDED_FILES", "")
        intended_files = [f.strip() for f in raw_files.split(",") if f.strip()]

        if not any([task, agent_name, model, session_id, intended_files]):
            return None

        return AgentContext(
            task_intent=task,
            agent_name=agent_name,
            model=model,
            session_id=session_id,
            intended_files=intended_files,
        )

    @classmethod
    def from_json_string(cls, json_str: str) -> AgentContext:
        """Parse AgentContext from a JSON string."""
        data = json.loads(json_str)
        if not isinstance(data, dict):
            raise ValueError("Agent input JSON must be an object")
        return AgentContext.from_dict(data)

    @classmethod
    def from_file_or_stdin(cls, path_or_stdin: str) -> AgentContext:
        """Read AgentContext from a JSON file path or '-' for stdin."""
        if path_or_stdin == "-":
            content = sys.stdin.read()
        else:
            p = Path(path_or_stdin)
            if not p.exists():
                raise FileNotFoundError(f"Agent input file not found: {path_or_stdin}")
            content = p.read_text(encoding="utf-8")

        return cls.from_json_string(content)
