"""Provenance and integrity hashing utilities for AgentProof.

Generates deterministic canonical SHA-256 digests over structured evidence and graph nodes
to provide tamper-evident provenance without claiming asymmetric cryptographic signatures.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_dumps(data: Any) -> str:
    """
    Serialize data to a deterministic, canonical JSON string:
    - Sorted dictionary keys
    - Compact delimiters (no whitespace between separators)
    - UTF-8 encoding
    """
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def compute_integrity_hash(data: Any) -> str:
    """
    Compute a SHA-256 hexadecimal digest for any JSON-serializable structure or string.
    """
    if isinstance(data, str):
        payload = data.encode("utf-8")
    elif isinstance(data, bytes):
        payload = data
    else:
        canonical_str = canonical_json_dumps(data)
        payload = canonical_str.encode("utf-8")

    return hashlib.sha256(payload).hexdigest()


def verify_integrity_hash(data: Any, expected_hash: str) -> bool:
    """
    Verify whether the computed SHA-256 digest of data matches the expected hash.
    """
    if not expected_hash:
        return False
    computed = compute_integrity_hash(data)
    return computed.lower() == expected_hash.lower()
