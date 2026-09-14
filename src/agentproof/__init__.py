"""AgentProof: An agent-agnostic verification and evidence layer for software changes."""

from agentproof.core.models import (
    ChangeSummary,
    TaskContext,
    Verdict,
    VerificationReport,
)
from agentproof.graph.models import ProofGraph
from agentproof.passport.models import ProofPassport

__version__ = "0.6.0"

__all__ = [
    "__version__",
    "ChangeSummary",
    "ProofGraph",
    "ProofPassport",
    "TaskContext",
    "Verdict",
    "VerificationReport",
]
