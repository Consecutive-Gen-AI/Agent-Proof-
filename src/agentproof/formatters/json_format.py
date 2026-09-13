"""Machine-readable JSON formatter for verification reports."""

from __future__ import annotations

import json
from agentproof.core.models import VerificationReport


def format_json_report(report: VerificationReport, indent: int = 2) -> str:
    """Serialize a VerificationReport into formatted JSON string."""
    return json.dumps(report.to_dict(), indent=indent, ensure_ascii=False)
