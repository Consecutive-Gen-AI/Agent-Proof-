"""Domain models for the AgentProof Evidence Graph (Proof Graph)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class NodeType(str, Enum):
    """Types of nodes in the Proof Graph."""
    TASK = "TASK"
    FILE = "FILE"
    SYMBOL = "SYMBOL"
    CHANGE = "CHANGE"
    CHECK = "CHECK"
    EVIDENCE = "EVIDENCE"
    RISK_FINDING = "RISK_FINDING"
    DRIFT_FINDING = "DRIFT_FINDING"
    MISSING_WORK = "MISSING_WORK"
    VERDICT = "VERDICT"


class RelationType(str, Enum):
    """Types of directed relationships in the Proof Graph."""
    TARGETS = "TARGETS"          # TASK -> FILE (explicit path or domain target)
    CONTAINS = "CONTAINS"        # CHANGE -> FILE or FILE -> SYMBOL
    MODIFIES = "MODIFIES"        # CHANGE -> SYMBOL
    IMPACTS = "IMPACTS"          # SYMBOL -> SYMBOL or FILE -> FILE
    VALIDATED_BY = "VALIDATED_BY"# CHANGE -> CHECK
    PRODUCES = "PRODUCES"        # CHECK -> EVIDENCE
    SUPPORTS = "SUPPORTS"        # EVIDENCE -> VERDICT or EVIDENCE -> FINDING
    TRIGGERS = "TRIGGERS"        # EVIDENCE/CHANGE -> RISK_FINDING, DRIFT_FINDING, MISSING_WORK
    AFFECTS = "AFFECTS"          # FINDING -> VERDICT or CHECK -> VERDICT


@dataclass
class GraphNode:
    """A typed entity node within the Proof Graph."""
    id: str
    node_type: NodeType
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    integrity_hash: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "node_type": self.node_type.value,
            "label": self.label,
            "properties": self.properties,
            "integrity_hash": self.integrity_hash,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphNode:
        return cls(
            id=data["id"],
            node_type=NodeType(data["node_type"]),
            label=data["label"],
            properties=data.get("properties", {}),
            integrity_hash=data.get("integrity_hash"),
        )


@dataclass
class GraphEdge:
    """A directed, typed relationship between two nodes in the Proof Graph."""
    source_id: str
    target_id: str
    relation: RelationType
    label: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "label": self.label or self.relation.value,
            "properties": self.properties,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> GraphEdge:
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            relation=RelationType(data["relation"]),
            label=data.get("label", ""),
            properties=data.get("properties", {}),
        )


@dataclass
class ProofGraph:
    """Complete, queryable Proof Graph connecting task, changes, checks, evidence, findings, and verdict."""
    schema_version: str = "1.0.0"
    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph if not already present."""
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add a directed edge between existing or forward-referenced nodes."""
        # Avoid duplicate identical edges
        for existing in self.edges:
            if (
                existing.source_id == edge.source_id
                and existing.target_id == edge.target_id
                and existing.relation == edge.relation
            ):
                return
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Retrieve a node by its ID."""
        return self.nodes.get(node_id)

    def find_nodes_by_type(self, node_type: NodeType) -> List[GraphNode]:
        """Retrieve all nodes matching a specific NodeType."""
        return [node for node in self.nodes.values() if node.node_type == node_type]

    def get_outgoing_edges(self, node_id: str) -> List[GraphEdge]:
        """Return all edges originating from node_id."""
        return [edge for edge in self.edges if edge.source_id == node_id]

    def get_incoming_edges(self, node_id: str) -> List[GraphEdge]:
        """Return all edges pointing into node_id."""
        return [edge for edge in self.edges if edge.target_id == node_id]

    def trace_verdict(self) -> Dict[str, Any]:
        """
        Trace the verdict node back to all incoming factors:
        - checks affecting verdict
        - findings affecting verdict
        - evidence supporting those checks/findings
        """
        verdict_nodes = self.find_nodes_by_type(NodeType.VERDICT)
        if not verdict_nodes:
            return {"verdict": None, "factors": []}

        verdict_node = verdict_nodes[0]
        incoming = self.get_incoming_edges(verdict_node.id)

        factors = []
        for edge in incoming:
            source_node = self.get_node(edge.source_id)
            if not source_node:
                continue

            # Find evidence supporting this source
            supporting_evidence = []
            for ev_edge in self.get_incoming_edges(source_node.id):
                if ev_edge.relation in (RelationType.SUPPORTS, RelationType.PRODUCES, RelationType.TRIGGERS):
                    ev_node = self.get_node(ev_edge.source_id)
                    if ev_node:
                        supporting_evidence.append({
                            "evidence_id": ev_node.id,
                            "label": ev_node.label,
                            "properties": ev_node.properties,
                        })

            factors.append({
                "factor_id": source_node.id,
                "factor_type": source_node.node_type.value,
                "label": source_node.label,
                "relation": edge.relation.value,
                "reason": edge.properties.get("reason", edge.label),
                "supporting_evidence": supporting_evidence,
            })

        return {
            "verdict": verdict_node.label,
            "properties": verdict_node.properties,
            "factors": factors,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "metadata": self.metadata,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ProofGraph:
        graph = cls(
            schema_version=data.get("schema_version", "1.0.0"),
            metadata=data.get("metadata", {}),
        )
        for node_dict in data.get("nodes", []):
            graph.add_node(GraphNode.from_dict(node_dict))
        for edge_dict in data.get("edges", []):
            graph.add_edge(GraphEdge.from_dict(edge_dict))
        return graph

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> ProofGraph:
        return cls.from_dict(json.loads(json_str))
