"""
Evolvable Execution DAG: Dynamic DAG with runtime modification support
P0-2 Implementation: Node injection, reordering, skip/merge, artifact tracking

This module provides:
1. Runtime node injection/removal
2. Node reordering based on signals
3. Node skip/merge capabilities
4. Complete DAG mutation history for replay/rollback
"""

import os
import json
import hashlib
import copy
from datetime import datetime
from typing import Dict, Any, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum


class MutationType(str, Enum):
    """Types of DAG mutations"""
    NODE_INJECT = "node_inject"       # Add new node
    NODE_REMOVE = "node_remove"       # Remove node
    NODE_SKIP = "node_skip"           # Skip node (keep in DAG but don't execute)
    NODE_MERGE = "node_merge"         # Merge multiple nodes into one
    NODE_SPLIT = "node_split"         # Split one node into multiple
    EDGE_ADD = "edge_add"             # Add dependency edge
    EDGE_REMOVE = "edge_remove"       # Remove dependency edge
    REORDER = "reorder"               # Reorder nodes
    CONDITION_UPDATE = "condition_update"  # Update node condition
    PLAN_SWITCH = "plan_switch"       # Switch to different plan


class NodeStatus(str, Enum):
    """Node execution status"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    FAILED = "failed"
    MERGED = "merged"


@dataclass
class DAGNode:
    """Enhanced DAG node with mutation support"""
    node_id: str
    agent_name: str
    description: str
    dependencies: List[str] = field(default_factory=list)
    required: bool = True
    cost_estimate: float = 0.0
    latency_estimate_ms: int = 1000
    risk_level: str = "low"
    status: NodeStatus = NodeStatus.PENDING
    
    # Mutation tracking
    injected: bool = False
    injection_reason: Optional[str] = None
    skip_reason: Optional[str] = None
    merged_into: Optional[str] = None
    merged_from: List[str] = field(default_factory=list)
    
    # Execution
    condition_func: Optional[Callable] = None
    condition_type: str = "always"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "agent_name": self.agent_name,
            "description": self.description,
            "dependencies": self.dependencies,
            "required": self.required,
            "cost_estimate": self.cost_estimate,
            "latency_estimate_ms": self.latency_estimate_ms,
            "risk_level": self.risk_level,
            "status": self.status.value,
            "injected": self.injected,
            "injection_reason": self.injection_reason,
            "skip_reason": self.skip_reason,
            "merged_into": self.merged_into,
            "merged_from": self.merged_from,
            "condition_type": self.condition_type
        }
    
    def can_execute(self, signals: Dict[str, Any]) -> bool:
        """Check if node can execute given current signals"""
        if self.status == NodeStatus.SKIPPED:
            return False
        if self.status == NodeStatus.MERGED:
            return False
        if self.condition_func:
            return self.condition_func(signals)
        return True


@dataclass
class DAGMutation:
    """Record of a single DAG mutation"""
    mutation_id: str
    mutation_type: MutationType
    timestamp: str
    trigger: str  # What triggered this mutation
    details: Dict[str, Any]
    before_hash: str  # DAG state hash before mutation
    after_hash: str   # DAG state hash after mutation
    reversible: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "mutation_id": self.mutation_id,
            "mutation_type": self.mutation_type.value,
            "timestamp": self.timestamp,
            "trigger": self.trigger,
            "details": self.details,
            "before_hash": self.before_hash,
            "after_hash": self.after_hash,
            "reversible": self.reversible
        }


@dataclass
class DAGSnapshot:
    """Immutable snapshot of DAG state for rollback"""
    snapshot_id: str
    timestamp: str
    nodes: List[Dict[str, Any]]
    edges: List[Tuple[str, str]]
    dag_hash: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "timestamp": self.timestamp,
            "nodes": self.nodes,
            "edges": self.edges,
            "dag_hash": self.dag_hash
        }


class EvolvableDAG:
    """
    Dynamic, evolvable Directed Acyclic Graph for execution planning.
    
    Features:
    - Runtime node injection/removal
    - Node reordering based on signals
    - Node skip/merge operations
    - Complete mutation history for audit/replay
    - Rollback support via snapshots
    """
    
    def __init__(
        self,
        dag_id: str,
        run_id: str,
        artifacts_dir: str = "artifacts/dag_evolution"
    ):
        self.dag_id = dag_id
        self.run_id = run_id
        self.artifacts_dir = artifacts_dir
        
        # Core data structures
        self.nodes: Dict[str, DAGNode] = {}
        self.edges: Set[Tuple[str, str]] = set()  # (from_node, to_node)
        
        # Evolution tracking
        self.mutations: List[DAGMutation] = []
        self.snapshots: List[DAGSnapshot] = []
        self.mutation_counter = 0
        
        # Create artifacts directory
        os.makedirs(artifacts_dir, exist_ok=True)
    
    def _compute_hash(self) -> str:
        """Compute hash of current DAG state"""
        state = {
            "nodes": sorted([n.to_dict() for n in self.nodes.values()], key=lambda x: x["node_id"]),
            "edges": sorted(list(self.edges))
        }
        content = json.dumps(state, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _take_snapshot(self) -> DAGSnapshot:
        """Take immutable snapshot of current DAG state"""
        snapshot = DAGSnapshot(
            snapshot_id=f"snap_{len(self.snapshots):04d}",
            timestamp=datetime.now().isoformat(),
            nodes=[n.to_dict() for n in self.nodes.values()],
            edges=list(self.edges),
            dag_hash=self._compute_hash()
        )
        self.snapshots.append(snapshot)
        return snapshot
    
    def _record_mutation(
        self,
        mutation_type: MutationType,
        trigger: str,
        details: Dict[str, Any],
        before_hash: str,
        reversible: bool = True
    ) -> DAGMutation:
        """Record a mutation in history"""
        self.mutation_counter += 1
        mutation = DAGMutation(
            mutation_id=f"mut_{self.mutation_counter:04d}",
            mutation_type=mutation_type,
            timestamp=datetime.now().isoformat(),
            trigger=trigger,
            details=details,
            before_hash=before_hash,
            after_hash=self._compute_hash(),
            reversible=reversible
        )
        self.mutations.append(mutation)
        return mutation
    
    def add_node(
        self,
        node: DAGNode,
        after_node_id: Optional[str] = None,
        before_node_id: Optional[str] = None,
        trigger: str = "initial_setup"
    ) -> DAGMutation:
        """
        Add a node to the DAG.
        
        Args:
            node: Node to add
            after_node_id: Insert after this node (add edge from this node)
            before_node_id: Insert before this node (add edge to this node)
            trigger: What triggered this addition
        """
        before_hash = self._compute_hash()
        
        # Add node
        self.nodes[node.node_id] = node
        
        # Add edges
        if after_node_id and after_node_id in self.nodes:
            self.edges.add((after_node_id, node.node_id))
            node.dependencies.append(after_node_id)
        
        if before_node_id and before_node_id in self.nodes:
            self.edges.add((node.node_id, before_node_id))
            # Update the before_node's dependencies
            self.nodes[before_node_id].dependencies.append(node.node_id)
        
        return self._record_mutation(
            MutationType.NODE_INJECT if trigger != "initial_setup" else MutationType.NODE_INJECT,
            trigger,
            {
                "node_id": node.node_id,
                "agent_name": node.agent_name,
                "after_node": after_node_id,
                "before_node": before_node_id
            },
            before_hash
        )
    
    def inject_node(
        self,
        node: DAGNode,
        after_node_id: str,
        reason: str
    ) -> DAGMutation:
        """
        Inject a new node into the DAG at runtime.
        
        Args:
            node: Node to inject
            after_node_id: Insert after this node
            reason: Reason for injection
        """
        node.injected = True
        node.injection_reason = reason
        
        before_hash = self._compute_hash()
        
        # Find nodes that depend on after_node_id
        affected_edges = [(s, t) for s, t in self.edges if s == after_node_id]
        
        # Add the new node
        self.nodes[node.node_id] = node
        
        # Rewire edges: after_node -> new_node -> (original targets)
        self.edges.add((after_node_id, node.node_id))
        node.dependencies.append(after_node_id)
        
        for src, tgt in affected_edges:
            # Remove old edge
            self.edges.discard((src, tgt))
            # Add edge from new node to original target
            self.edges.add((node.node_id, tgt))
            # Update target's dependencies
            if src in self.nodes[tgt].dependencies:
                self.nodes[tgt].dependencies.remove(src)
            self.nodes[tgt].dependencies.append(node.node_id)
        
        return self._record_mutation(
            MutationType.NODE_INJECT,
            reason,
            {
                "node_id": node.node_id,
                "agent_name": node.agent_name,
                "after_node": after_node_id,
                "rewired_edges": len(affected_edges),
                "reason": reason
            },
            before_hash
        )
    
    def remove_node(
        self,
        node_id: str,
        reason: str
    ) -> Optional[DAGMutation]:
        """Remove a node from the DAG"""
        if node_id not in self.nodes:
            return None
        
        before_hash = self._compute_hash()
        node = self.nodes[node_id]
        
        # Find incoming and outgoing edges
        incoming = [s for s, t in self.edges if t == node_id]
        outgoing = [t for s, t in self.edges if s == node_id]
        
        # Remove all edges involving this node
        self.edges = {(s, t) for s, t in self.edges if s != node_id and t != node_id}
        
        # Reconnect: each incoming node connects to each outgoing node
        for src in incoming:
            for tgt in outgoing:
                self.edges.add((src, tgt))
                if node_id in self.nodes[tgt].dependencies:
                    self.nodes[tgt].dependencies.remove(node_id)
                self.nodes[tgt].dependencies.append(src)
        
        # Remove node
        del self.nodes[node_id]
        
        return self._record_mutation(
            MutationType.NODE_REMOVE,
            reason,
            {
                "node_id": node_id,
                "agent_name": node.agent_name,
                "reconnected_edges": len(incoming) * len(outgoing),
                "reason": reason
            },
            before_hash
        )
    
    def skip_node(
        self,
        node_id: str,
        reason: str
    ) -> Optional[DAGMutation]:
        """Mark a node as skipped (stays in DAG but won't execute)"""
        if node_id not in self.nodes:
            return None
        
        before_hash = self._compute_hash()
        node = self.nodes[node_id]
        node.status = NodeStatus.SKIPPED
        node.skip_reason = reason
        
        return self._record_mutation(
            MutationType.NODE_SKIP,
            reason,
            {
                "node_id": node_id,
                "agent_name": node.agent_name,
                "reason": reason
            },
            before_hash
        )
    
    def merge_nodes(
        self,
        source_node_ids: List[str],
        merged_node: DAGNode,
        reason: str
    ) -> Optional[DAGMutation]:
        """Merge multiple nodes into a single node"""
        if not all(nid in self.nodes for nid in source_node_ids):
            return None
        
        before_hash = self._compute_hash()
        
        # Collect all dependencies and dependents
        all_deps: Set[str] = set()
        all_dependents: Set[str] = set()
        
        for nid in source_node_ids:
            # Incoming edges (dependencies)
            all_deps.update(s for s, t in self.edges if t == nid and s not in source_node_ids)
            # Outgoing edges (dependents)
            all_dependents.update(t for s, t in self.edges if s == nid and t not in source_node_ids)
        
        # Mark source nodes as merged
        for nid in source_node_ids:
            self.nodes[nid].status = NodeStatus.MERGED
            self.nodes[nid].merged_into = merged_node.node_id
        
        # Add merged node
        merged_node.merged_from = source_node_ids
        merged_node.dependencies = list(all_deps)
        self.nodes[merged_node.node_id] = merged_node
        
        # Remove edges involving source nodes (except internal)
        self.edges = {
            (s, t) for s, t in self.edges 
            if not (s in source_node_ids or t in source_node_ids)
        }
        
        # Add new edges for merged node
        for dep in all_deps:
            self.edges.add((dep, merged_node.node_id))
        for dependent in all_dependents:
            self.edges.add((merged_node.node_id, dependent))
            self.nodes[dependent].dependencies = [
                d if d not in source_node_ids else merged_node.node_id
                for d in self.nodes[dependent].dependencies
            ]
        
        return self._record_mutation(
            MutationType.NODE_MERGE,
            reason,
            {
                "source_nodes": source_node_ids,
                "merged_node_id": merged_node.node_id,
                "reason": reason
            },
            before_hash
        )
    
    def reorder_nodes(
        self,
        new_order: List[str],
        reason: str
    ) -> DAGMutation:
        """
        Reorder nodes while respecting dependencies.
        This doesn't change dependencies, just the iteration order.
        """
        before_hash = self._compute_hash()
        
        # Validate: ensure all nodes exist and new order respects dependencies
        for node_id in new_order:
            if node_id not in self.nodes:
                raise ValueError(f"Node {node_id} not in DAG")
        
        # Store the order preference (will be used in get_executable_order)
        self._preferred_order = new_order
        
        return self._record_mutation(
            MutationType.REORDER,
            reason,
            {
                "new_order": new_order,
                "reason": reason
            },
            before_hash
        )
    
    def update_condition(
        self,
        node_id: str,
        condition_type: str,
        condition_func: Optional[Callable] = None,
        reason: str = "condition_update"
    ) -> Optional[DAGMutation]:
        """Update a node's execution condition"""
        if node_id not in self.nodes:
            return None
        
        before_hash = self._compute_hash()
        node = self.nodes[node_id]
        node.condition_type = condition_type
        node.condition_func = condition_func
        
        return self._record_mutation(
            MutationType.CONDITION_UPDATE,
            reason,
            {
                "node_id": node_id,
                "condition_type": condition_type,
                "reason": reason
            },
            before_hash
        )
    
    def get_executable_order(self, signals: Dict[str, Any]) -> List[DAGNode]:
        """
        Get topologically sorted nodes that can execute given signals.
        Respects dependencies and current conditions.
        """
        # Build adjacency list
        in_degree = {nid: 0 for nid in self.nodes}
        for src, tgt in self.edges:
            if tgt in in_degree:
                in_degree[tgt] += 1
        
        # Kahn's algorithm for topological sort
        queue = [nid for nid, deg in in_degree.items() if deg == 0]
        result = []
        
        while queue:
            # Sort by preferred order if available
            if hasattr(self, '_preferred_order'):
                queue.sort(key=lambda x: self._preferred_order.index(x) 
                          if x in self._preferred_order else float('inf'))
            
            node_id = queue.pop(0)
            node = self.nodes[node_id]
            
            # Only include if executable
            if node.can_execute(signals):
                result.append(node)
            
            # Reduce in-degree of dependents
            for src, tgt in self.edges:
                if src == node_id and tgt in in_degree:
                    in_degree[tgt] -= 1
                    if in_degree[tgt] == 0:
                        queue.append(tgt)
        
        return result
    
    def rollback_to_snapshot(self, snapshot_id: str) -> bool:
        """Rollback DAG to a previous snapshot state"""
        snapshot = next((s for s in self.snapshots if s.snapshot_id == snapshot_id), None)
        if not snapshot:
            return False
        
        before_hash = self._compute_hash()
        
        # Restore nodes
        self.nodes = {}
        for node_dict in snapshot.nodes:
            node = DAGNode(
                node_id=node_dict["node_id"],
                agent_name=node_dict["agent_name"],
                description=node_dict["description"],
                dependencies=node_dict.get("dependencies", []),
                required=node_dict.get("required", True),
                cost_estimate=node_dict.get("cost_estimate", 0.0),
                latency_estimate_ms=node_dict.get("latency_estimate_ms", 1000),
                risk_level=node_dict.get("risk_level", "low"),
                status=NodeStatus(node_dict.get("status", "pending")),
                injected=node_dict.get("injected", False),
                injection_reason=node_dict.get("injection_reason"),
                skip_reason=node_dict.get("skip_reason"),
                merged_into=node_dict.get("merged_into"),
                merged_from=node_dict.get("merged_from", []),
                condition_type=node_dict.get("condition_type", "always")
            )
            self.nodes[node.node_id] = node
        
        # Restore edges
        self.edges = set(tuple(e) for e in snapshot.edges)
        
        # Record the rollback mutation
        self._record_mutation(
            MutationType.PLAN_SWITCH,
            f"rollback_to_{snapshot_id}",
            {
                "snapshot_id": snapshot_id,
                "snapshot_timestamp": snapshot.timestamp
            },
            before_hash,
            reversible=False
        )
        
        return True
    
    def save_evolution_log(self) -> str:
        """Save complete DAG evolution history to artifact"""
        log = {
            "dag_id": self.dag_id,
            "run_id": self.run_id,
            "final_state": {
                "nodes": [n.to_dict() for n in self.nodes.values()],
                "edges": list(self.edges),
                "hash": self._compute_hash()
            },
            "mutations": [m.to_dict() for m in self.mutations],
            "snapshots": [s.to_dict() for s in self.snapshots],
            "statistics": {
                "total_mutations": len(self.mutations),
                "nodes_added": sum(1 for m in self.mutations if m.mutation_type == MutationType.NODE_INJECT),
                "nodes_removed": sum(1 for m in self.mutations if m.mutation_type == MutationType.NODE_REMOVE),
                "nodes_skipped": sum(1 for m in self.mutations if m.mutation_type == MutationType.NODE_SKIP),
                "nodes_merged": sum(1 for m in self.mutations if m.mutation_type == MutationType.NODE_MERGE),
                "reorders": sum(1 for m in self.mutations if m.mutation_type == MutationType.REORDER),
                "snapshots_taken": len(self.snapshots)
            },
            "generated_at": datetime.now().isoformat()
        }
        
        log_path = os.path.join(self.artifacts_dir, f"{self.run_id}_dag_evolution.json")
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2, ensure_ascii=False)
        
        return log_path
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize DAG state"""
        return {
            "dag_id": self.dag_id,
            "run_id": self.run_id,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": list(self.edges),
            "hash": self._compute_hash(),
            "mutation_count": len(self.mutations)
        }
    
    @classmethod
    def from_template(
        cls,
        template_id: str,
        run_id: str,
        template_nodes: List[Dict[str, Any]],
        template_edges: List[Tuple[str, str]],
        artifacts_dir: str = "artifacts/dag_evolution"
    ) -> "EvolvableDAG":
        """Create EvolvableDAG from a template"""
        dag = cls(
            dag_id=f"dag_{template_id}_{run_id[:8]}",
            run_id=run_id,
            artifacts_dir=artifacts_dir
        )
        
        # Add nodes from template
        for node_dict in template_nodes:
            node = DAGNode(
                node_id=node_dict["node_id"],
                agent_name=node_dict["agent_name"],
                description=node_dict.get("description", ""),
                dependencies=node_dict.get("dependencies", []),
                required=node_dict.get("required", True),
                cost_estimate=node_dict.get("cost_estimate", 0.05),
                latency_estimate_ms=node_dict.get("latency_estimate_ms", 1000),
                risk_level=node_dict.get("risk_level", "low")
            )
            dag.nodes[node.node_id] = node
        
        # Add edges
        dag.edges = set(template_edges)
        
        # Take initial snapshot
        dag._take_snapshot()
        
        return dag


# Example: Learning-driven DAG modification
class DAGLearningIntegration:
    """
    Integrates learning signals with DAG evolution.
    Used for P0-3: Structural Learning.
    """
    
    @staticmethod
    def suggest_node_injection(
        dag: EvolvableDAG,
        learning_signal: Dict[str, Any]
    ) -> Optional[Tuple[DAGNode, str, str]]:
        """
        Suggest node injection based on learning signal.
        Returns (node_to_inject, after_node_id, reason) or None.
        """
        signal_type = learning_signal.get("type")
        
        if signal_type == "quality_degradation":
            # Inject a validation node
            node = DAGNode(
                node_id="injected_validation",
                agent_name="ValidationAgent",
                description="Runtime validation to address quality degradation",
                required=False,
                cost_estimate=0.02,
                latency_estimate_ms=500,
                risk_level="low"
            )
            # Inject after execution, before evaluation
            return node, "Execution", "quality_degradation_detected"
        
        elif signal_type == "data_issue":
            # Inject a data cleaning node
            node = DAGNode(
                node_id="injected_data_cleaning",
                agent_name="DataCleaningAgent",
                description="Runtime data cleaning to address data issues",
                required=True,
                cost_estimate=0.03,
                latency_estimate_ms=800,
                risk_level="medium"
            )
            return node, "Data", "data_issue_detected"
        
        return None
    
    @staticmethod
    def suggest_node_skip(
        dag: EvolvableDAG,
        learning_signal: Dict[str, Any]
    ) -> Optional[Tuple[str, str]]:
        """
        Suggest node skip based on learning signal.
        Returns (node_id_to_skip, reason) or None.
        """
        if learning_signal.get("type") == "cost_pressure":
            # Skip non-required nodes with high cost
            for node_id, node in dag.nodes.items():
                if not node.required and node.cost_estimate > 0.05:
                    return node_id, "cost_pressure_skip_non_essential"
        
        return None


