"""Unit tests for AgentProof graph and evidence integrity hashing."""

from agentproof.graph.integrity import (
    canonical_json_dumps,
    compute_integrity_hash,
    verify_integrity_hash,
)


def test_canonical_json_key_order_invariance():
    data1 = {"b": 2, "a": 1, "nested": {"z": 26, "y": 25}}
    data2 = {"nested": {"y": 25, "z": 26}, "a": 1, "b": 2}

    json1 = canonical_json_dumps(data1)
    json2 = canonical_json_dumps(data2)

    assert json1 == json2
    assert compute_integrity_hash(data1) == compute_integrity_hash(data2)


def test_integrity_hash_format():
    hash_val = compute_integrity_hash({"test": "data"})
    assert isinstance(hash_val, str)
    assert len(hash_val) == 64
    assert all(c in "0123456789abcdef" for c in hash_val)


def test_modified_evidence_tamper_detection():
    evidence_original = {
        "check_name": "pytest",
        "status": "PASS",
        "exit_code": 0,
        "stdout": "12 tests passed",
    }
    evidence_tampered = {
        "check_name": "pytest",
        "status": "FAIL",  # Tampered
        "exit_code": 1,
        "stdout": "12 tests passed",
    }

    original_hash = compute_integrity_hash(evidence_original)
    assert verify_integrity_hash(evidence_original, original_hash) is True
    assert verify_integrity_hash(evidence_tampered, original_hash) is False


def test_verify_integrity_hash_edge_cases():
    assert verify_integrity_hash({"test": 123}, "") is False
    assert verify_integrity_hash({"test": 123}, None) is False  # type: ignore[arg-type]
