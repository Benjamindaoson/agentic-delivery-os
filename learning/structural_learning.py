"""
Structural Learning: DAG-level learning and structural credit assignment
P0-3 Implementation: Learn DAG structures, agent combinations, and structural rewards

This module provides:
1. DAG-level reward computation
2. Structural credit assignment (which DAG structure worked best)
3. Learning which agents to use for which task types
4. Learning optimal DAG topologies
"""

import os
import json
import hashlib
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict


class StructuralFeature(str, Enum):
    """Features of DAG structure for learning"""
    DAG_DEPTH = "dag_depth"                    # Maximum path length
    DAG_WIDTH = "dag_width"                    # Maximum parallel nodes
    NODE_COUNT = "node_count"                  # Total nodes
    BRANCH_FACTOR = "branch_factor"            # Average outgoing edges
    PARALLELISM_RATIO = "parallelism_ratio"    # Parallel vs sequential ratio
    AGENT_DIVERSITY = "agent_diversity"        # Unique agent types / total
    INJECTION_COUNT = "injection_count"        # Runtime injections
    SKIP_COUNT = "skip_count"                  # Skipped nodes
    MERGE_COUNT = "merge_count"                # Merged nodes


@dataclass
class DAGStructureVector:
    """Vector representation of DAG structure for learning"""
    dag_id: str
    run_id: str
    features: Dict[str, float]
    agent_sequence: List[str]
    topology_hash: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
    
    def to_numpy(self) -> np.ndarray:
        """Convert to numpy array for ML"""
        feature_order = [f.value for f in StructuralFeature]
        return np.array([self.features.get(f, 0.0) for f in feature_order])


@dataclass
class StructuralReward:
    """Reward signal for DAG structure"""
    run_id: str
    dag_id: str
    
    # Component rewards
    task_success: float          # Did the task succeed?
    quality_score: float         # Output quality
    cost_efficiency: float       # Cost vs budget ratio
    latency_efficiency: float    # Latency vs target ratio
    
    # Structural bonuses/penalties
    minimal_structure_bonus: float  # Bonus for achieving with fewer nodes
    adaptation_bonus: float         # Bonus for successful runtime adaptation
    
    # Final combined reward
    total_reward: float
    
    # Attribution
    contributing_factors: Dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class StructuralCreditAssignment:
    """Credit assignment to structural components"""
    run_id: str
    
    # Node-level credit
    node_credits: Dict[str, float]  # node_id -> credit
    
    # Edge-level credit (which dependencies mattered)
    edge_credits: Dict[str, float]  # "src->tgt" -> credit
    
    # Agent type credit
    agent_type_credits: Dict[str, float]  # agent_type -> credit
    
    # Topology credit
    topology_credit: float  # Credit for the overall structure
    
    # Explanation
    assignment_rationale: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class StructuralFeatureExtractor:
    """Extract structural features from DAG for learning"""
    
    @staticmethod
    def extract(
        nodes: List[Dict[str, Any]],
        edges: List[Tuple[str, str]]
    ) -> DAGStructureVector:
        """Extract feature vector from DAG structure"""
        
        # Build adjacency lists
        successors: Dict[str, List[str]] = defaultdict(list)
        predecessors: Dict[str, List[str]] = defaultdict(list)
        
        for src, tgt in edges:
            successors[src].append(tgt)
            predecessors[tgt].append(src)
        
        node_ids = [n["node_id"] for n in nodes]
        
        # Compute features
        features = {}
        
        # DAG depth (longest path)
        def dfs_depth(node_id: str, memo: Dict[str, int] = {}) -> int:
            if node_id in memo:
                return memo[node_id]
            succs = successors.get(node_id, [])
            if not succs:
                memo[node_id] = 1
            else:
                memo[node_id] = 1 + max(dfs_depth(s, memo) for s in succs)
            return memo[node_id]
        
        roots = [nid for nid in node_ids if not predecessors.get(nid)]
        if roots:
            features[StructuralFeature.DAG_DEPTH.value] = float(max(dfs_depth(r) for r in roots))
        else:
            features[StructuralFeature.DAG_DEPTH.value] = float(len(nodes))
        
        # DAG width (max nodes at same depth level)
        levels: Dict[int, List[str]] = defaultdict(list)
        visited = set()
        queue = [(r, 0) for r in roots]
        while queue:
            nid, level = queue.pop(0)
            if nid in visited:
                continue
            visited.add(nid)
            levels[level].append(nid)
            for succ in successors.get(nid, []):
                queue.append((succ, level + 1))
        
        features[StructuralFeature.DAG_WIDTH.value] = float(max(len(v) for v in levels.values())) if levels else 1.0
        
        # Node count
        features[StructuralFeature.NODE_COUNT.value] = float(len(nodes))
        
        # Branch factor
        out_degrees = [len(successors.get(nid, [])) for nid in node_ids]
        features[StructuralFeature.BRANCH_FACTOR.value] = np.mean(out_degrees) if out_degrees else 0.0
        
        # Parallelism ratio (width / depth)
        depth = features[StructuralFeature.DAG_DEPTH.value]
        width = features[StructuralFeature.DAG_WIDTH.value]
        features[StructuralFeature.PARALLELISM_RATIO.value] = width / depth if depth > 0 else 0.0
        
        # Agent diversity
        agent_types = set(n.get("agent_name", "unknown") for n in nodes)
        features[StructuralFeature.AGENT_DIVERSITY.value] = len(agent_types) / len(nodes) if nodes else 0.0
        
        # Runtime adaptation counts
        features[StructuralFeature.INJECTION_COUNT.value] = float(sum(1 for n in nodes if n.get("injected", False)))
        features[StructuralFeature.SKIP_COUNT.value] = float(sum(1 for n in nodes if n.get("status") == "skipped"))
        features[StructuralFeature.MERGE_COUNT.value] = float(sum(1 for n in nodes if n.get("status") == "merged"))
        
        # Compute topology hash
        topo_str = json.dumps({
            "agents": sorted([n["agent_name"] for n in nodes]),
            "edges": sorted(edges)
        }, sort_keys=True)
        topology_hash = hashlib.sha256(topo_str.encode()).hexdigest()[:12]
        
        # Get agent sequence (execution order approximation)
        agent_sequence = [n["agent_name"] for n in sorted(nodes, key=lambda x: x["node_id"])]
        
        return DAGStructureVector(
            dag_id=nodes[0].get("dag_id", "unknown") if nodes else "unknown",
            run_id=nodes[0].get("run_id", "unknown") if nodes else "unknown",
            features=features,
            agent_sequence=agent_sequence,
            topology_hash=topology_hash
        )


class StructuralRewardComputer:
    """Compute DAG-level rewards with structural components"""
    
    def __init__(
        self,
        quality_weight: float = 0.4,
        cost_weight: float = 0.2,
        latency_weight: float = 0.2,
        structure_weight: float = 0.2
    ):
        self.quality_weight = quality_weight
        self.cost_weight = cost_weight
        self.latency_weight = latency_weight
        self.structure_weight = structure_weight
    
    def compute(
        self,
        run_id: str,
        dag_id: str,
        execution_result: Dict[str, Any],
        dag_features: DAGStructureVector,
        budget: float = 1.0,
        target_latency_ms: int = 5000
    ) -> StructuralReward:
        """Compute structural reward for a DAG execution"""
        
        contributing_factors = {}
        
        # Task success (0 or 1)
        task_success = 1.0 if execution_result.get("success", False) else 0.0
        contributing_factors["task_success"] = task_success
        
        # Quality score (0-1)
        quality_score = execution_result.get("quality_score", 0.5)
        contributing_factors["quality_score"] = quality_score
        
        # Cost efficiency (1 - cost/budget, clamped to [0, 1])
        actual_cost = execution_result.get("total_cost", 0.0)
        cost_efficiency = max(0.0, 1.0 - (actual_cost / budget)) if budget > 0 else 0.5
        contributing_factors["cost_efficiency"] = cost_efficiency
        
        # Latency efficiency (1 - latency/target, clamped to [0, 1])
        actual_latency = execution_result.get("total_latency_ms", 0)
        latency_efficiency = max(0.0, 1.0 - (actual_latency / target_latency_ms)) if target_latency_ms > 0 else 0.5
        contributing_factors["latency_efficiency"] = latency_efficiency
        
        # Minimal structure bonus (fewer nodes = better, if successful)
        # Normalize by expected node count (5 is baseline)
        node_count = dag_features.features.get(StructuralFeature.NODE_COUNT.value, 5)
        minimal_structure_bonus = 0.0
        if task_success > 0.5:
            # Bonus for achieving with fewer nodes than baseline
            minimal_structure_bonus = max(0.0, (5.0 - node_count) * 0.05)  # 0.05 per node saved
        contributing_factors["minimal_structure_bonus"] = minimal_structure_bonus
        
        # Adaptation bonus (successful runtime adaptations)
        injection_count = dag_features.features.get(StructuralFeature.INJECTION_COUNT.value, 0)
        skip_count = dag_features.features.get(StructuralFeature.SKIP_COUNT.value, 0)
        adaptation_bonus = 0.0
        if task_success > 0.5 and (injection_count > 0 or skip_count > 0):
            # Bonus for successful adaptation
            adaptation_bonus = 0.1 * (injection_count + skip_count)
        contributing_factors["adaptation_bonus"] = adaptation_bonus
        
        # Compute total reward
        base_reward = (
            task_success * 0.3 +
            quality_score * self.quality_weight +
            cost_efficiency * self.cost_weight +
            latency_efficiency * self.latency_weight
        )
        
        structure_bonus = (
            minimal_structure_bonus + adaptation_bonus
        ) * self.structure_weight
        
        total_reward = base_reward + structure_bonus
        
        return StructuralReward(
            run_id=run_id,
            dag_id=dag_id,
            task_success=task_success,
            quality_score=quality_score,
            cost_efficiency=cost_efficiency,
            latency_efficiency=latency_efficiency,
            minimal_structure_bonus=minimal_structure_bonus,
            adaptation_bonus=adaptation_bonus,
            total_reward=total_reward,
            contributing_factors=contributing_factors
        )


class StructuralCreditAssigner:
    """Assign credit to structural components based on outcomes"""
    
    def assign(
        self,
        run_id: str,
        dag_nodes: List[Dict[str, Any]],
        dag_edges: List[Tuple[str, str]],
        node_execution_results: Dict[str, Dict[str, Any]],
        final_reward: float
    ) -> StructuralCreditAssignment:
        """
        Assign credit to DAG components.
        
        Uses a combination of:
        1. Shapley-inspired credit for nodes on critical path
        2. Contribution-weighted credit based on individual node results
        3. Topology credit based on structure appropriateness
        """
        
        node_credits = {}
        edge_credits = {}
        agent_type_credits = defaultdict(float)
        
        # Build dependency graph
        successors: Dict[str, List[str]] = defaultdict(list)
        predecessors: Dict[str, List[str]] = defaultdict(list)
        
        for src, tgt in dag_edges:
            successors[src].append(tgt)
            predecessors[tgt].append(src)
        
        # Find critical path (longest path)
        def get_path_length(node_id: str, memo: Dict[str, int] = {}) -> int:
            if node_id in memo:
                return memo[node_id]
            succs = successors.get(node_id, [])
            if not succs:
                memo[node_id] = 1
            else:
                memo[node_id] = 1 + max(get_path_length(s, memo) for s in succs)
            return memo[node_id]
        
        node_ids = [n["node_id"] for n in dag_nodes]
        roots = [nid for nid in node_ids if not predecessors.get(nid)]
        
        path_lengths = {nid: get_path_length(nid) for nid in node_ids}
        max_path = max(path_lengths.values()) if path_lengths else 1
        
        # Compute node credits
        total_node_weight = 0.0
        for node in dag_nodes:
            node_id = node["node_id"]
            agent_name = node.get("agent_name", "unknown")
            
            # Base credit from path importance
            path_importance = path_lengths.get(node_id, 1) / max_path
            
            # Credit from execution result
            node_result = node_execution_results.get(node_id, {})
            node_success = 1.0 if node_result.get("success", True) else 0.0
            node_quality = node_result.get("quality", 0.5)
            
            # Combined credit
            node_credit = (path_importance * 0.5 + node_success * 0.3 + node_quality * 0.2) * final_reward
            node_credits[node_id] = node_credit
            agent_type_credits[agent_name] += node_credit
            total_node_weight += node_credit
        
        # Normalize node credits
        if total_node_weight > 0:
            node_credits = {k: v / total_node_weight * final_reward for k, v in node_credits.items()}
            agent_type_credits = {k: v / total_node_weight * final_reward for k, v in agent_type_credits.items()}
        
        # Compute edge credits (dependencies that were critical)
        for src, tgt in dag_edges:
            # Edge credit = average of connected node credits
            src_credit = node_credits.get(src, 0.0)
            tgt_credit = node_credits.get(tgt, 0.0)
            edge_credits[f"{src}->{tgt}"] = (src_credit + tgt_credit) / 2
        
        # Topology credit (how appropriate was the overall structure)
        # Higher if successful with minimal structure
        node_count = len(dag_nodes)
        success_rate = sum(1 for r in node_execution_results.values() if r.get("success", True)) / max(1, len(node_execution_results))
        topology_credit = success_rate * (5.0 / max(1, node_count))  # Favor simpler successful structures
        
        # Generate rationale
        top_nodes = sorted(node_credits.items(), key=lambda x: x[1], reverse=True)[:3]
        top_agents = sorted(agent_type_credits.items(), key=lambda x: x[1], reverse=True)[:3]
        
        rationale = f"""Structural Credit Assignment:
- Top contributing nodes: {', '.join(f'{n[0]}({n[1]:.3f})' for n in top_nodes)}
- Top contributing agent types: {', '.join(f'{a[0]}({a[1]:.3f})' for a in top_agents)}
- Topology credit: {topology_credit:.3f} (favors successful minimal structures)
- Total reward: {final_reward:.3f}"""
        
        return StructuralCreditAssignment(
            run_id=run_id,
            node_credits=node_credits,
            edge_credits=edge_credits,
            agent_type_credits=dict(agent_type_credits),
            topology_credit=topology_credit,
            assignment_rationale=rationale
        )


class StructuralLearner:
    """
    Main structural learning component.
    
    Learns:
    1. Which DAG structures work best for which task types
    2. Which agent combinations are most effective
    3. When to use complex vs simple structures
    """
    
    def __init__(self, artifacts_dir: str = "artifacts/learning/structural"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Learning state
        self.topology_rewards: Dict[str, List[float]] = defaultdict(list)  # topology_hash -> rewards
        self.agent_combo_rewards: Dict[str, List[float]] = defaultdict(list)  # sorted agents -> rewards
        self.task_type_structure_map: Dict[str, Dict[str, float]] = defaultdict(dict)  # task_type -> {topology_hash -> avg_reward}
        
        # Feature importance (learned)
        self.feature_importance: Dict[str, float] = {f.value: 1.0/len(StructuralFeature) for f in StructuralFeature}
        
        # Load existing state
        self._load_state()
    
    def record_execution(
        self,
        task_type: str,
        structure_vector: DAGStructureVector,
        reward: StructuralReward,
        credit_assignment: StructuralCreditAssignment
    ):
        """Record an execution for learning"""
        
        # Update topology rewards
        self.topology_rewards[structure_vector.topology_hash].append(reward.total_reward)
        
        # Update agent combo rewards
        agent_combo = tuple(sorted(structure_vector.agent_sequence))
        self.agent_combo_rewards[str(agent_combo)].append(reward.total_reward)
        
        # Update task type -> structure mapping
        if structure_vector.topology_hash not in self.task_type_structure_map[task_type]:
            self.task_type_structure_map[task_type][structure_vector.topology_hash] = reward.total_reward
        else:
            # Exponential moving average
            old_val = self.task_type_structure_map[task_type][structure_vector.topology_hash]
            self.task_type_structure_map[task_type][structure_vector.topology_hash] = 0.9 * old_val + 0.1 * reward.total_reward
        
        # Update feature importance based on credit assignment
        self._update_feature_importance(structure_vector, reward)
        
        # Persist
        self._save_state()
        self._save_execution_record(task_type, structure_vector, reward, credit_assignment)
        self._export_policy_files()
    
    def recommend_structure(
        self,
        task_type: str,
        available_templates: List[str],
        complexity: str
    ) -> Dict[str, Any]:
        """
        Recommend DAG structure for a new task.
        
        Returns:
            Dictionary with:
            - recommended_template: Best template ID
            - recommended_agents: Suggested agent sequence
            - confidence: Confidence in recommendation
            - rationale: Explanation
        """
        
        # Check if we have data for this task type
        task_structures = self.task_type_structure_map.get(task_type, {})
        
        if not task_structures:
            # No data, return default recommendation
            return {
                "recommended_template": "linear_simple",
                "recommended_agents": ["Product", "Data", "Execution", "Evaluation", "Cost"],
                "confidence": 0.0,
                "rationale": "No historical data for this task type, using default"
            }
        
        # Find best topology
        best_topology = max(task_structures.items(), key=lambda x: x[1])
        
        # Find best agent combo
        best_combo = None
        best_combo_reward = 0.0
        for combo, rewards in self.agent_combo_rewards.items():
            avg_reward = np.mean(rewards)
            if avg_reward > best_combo_reward:
                best_combo = combo
                best_combo_reward = avg_reward
        
        # Compute confidence
        sample_count = len(self.topology_rewards.get(best_topology[0], []))
        confidence = min(1.0, sample_count / 100)  # Full confidence at 100 samples
        
        # Generate rationale
        rationale = f"""Recommendation based on {sample_count} historical executions.
Best performing topology: {best_topology[0]} (avg reward: {best_topology[1]:.3f})
Feature importance: {json.dumps({k: f'{v:.3f}' for k, v in sorted(self.feature_importance.items(), key=lambda x: x[1], reverse=True)[:3]})}"""
        
        return {
            "recommended_template": best_topology[0],
            "recommended_agents": eval(best_combo) if best_combo else ["Product", "Data", "Execution", "Evaluation", "Cost"],
            "confidence": confidence,
            "rationale": rationale
        }
    
    def suggest_dag_modification(
        self,
        current_structure: DAGStructureVector,
        current_reward: float,
        task_type: str
    ) -> Optional[Dict[str, Any]]:
        """
        Suggest DAG modification to improve performance.
        
        Returns modification suggestion or None if no improvement expected.
        """
        
        # Compare current structure to historical best
        task_structures = self.task_type_structure_map.get(task_type, {})
        if not task_structures:
            return None
        
        best_topology_hash = max(task_structures.items(), key=lambda x: x[1])[0]
        
        if best_topology_hash == current_structure.topology_hash:
            return None  # Already using best structure
        
        best_reward = task_structures[best_topology_hash]
        
        if best_reward <= current_reward:
            return None  # Current structure is performing well
        
        # Analyze difference
        current_features = current_structure.features
        
        # Suggest modifications based on feature importance
        suggestions = []
        
        if current_features.get(StructuralFeature.NODE_COUNT.value, 0) > 5:
            if self.feature_importance.get(StructuralFeature.NODE_COUNT.value, 0) < 0.5:
                suggestions.append({
                    "type": "simplify",
                    "reason": "High node count with low feature importance",
                    "action": "Consider merging or skipping non-essential nodes"
                })
        
        if current_features.get(StructuralFeature.PARALLELISM_RATIO.value, 0) < 0.3:
            suggestions.append({
                "type": "parallelize",
                "reason": "Low parallelism ratio",
                "action": "Consider parallelizing independent nodes"
            })
        
        if not suggestions:
            return None
        
        return {
            "current_topology": current_structure.topology_hash,
            "best_topology": best_topology_hash,
            "expected_improvement": best_reward - current_reward,
            "suggestions": suggestions
        }
    
    def _update_feature_importance(
        self,
        structure_vector: DAGStructureVector,
        reward: StructuralReward
    ):
        """Update feature importance based on correlation with reward"""
        features = structure_vector.features
        reward_value = reward.total_reward
        
        # Simple update: increase importance for features correlated with high reward
        for feature_name, feature_value in features.items():
            if feature_name not in self.feature_importance:
                self.feature_importance[feature_name] = 0.1
            
            # Correlation-like update
            if reward_value > 0.7:  # High reward
                # Increase importance of features with moderate values
                if 0.2 < feature_value < 0.8:
                    self.feature_importance[feature_name] *= 1.01
            elif reward_value < 0.3:  # Low reward
                # Decrease importance of extreme features
                if feature_value < 0.1 or feature_value > 0.9:
                    self.feature_importance[feature_name] *= 0.99
        
        # Normalize
        total = sum(self.feature_importance.values())
        if total > 0:
            self.feature_importance = {k: v/total for k, v in self.feature_importance.items()}
    
    def _save_state(self):
        """Persist learning state"""
        state = {
            "topology_rewards": {k: list(v) for k, v in self.topology_rewards.items()},
            "agent_combo_rewards": {k: list(v) for k, v in self.agent_combo_rewards.items()},
            "task_type_structure_map": dict(self.task_type_structure_map),
            "feature_importance": self.feature_importance,
            "updated_at": datetime.now().isoformat()
        }
        
        path = os.path.join(self.artifacts_dir, "structural_learning_state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
    
    def _load_state(self):
        """Load learning state"""
        path = os.path.join(self.artifacts_dir, "structural_learning_state.json")
        if not os.path.exists(path):
            return
        
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            
            self.topology_rewards = defaultdict(list, {k: list(v) for k, v in state.get("topology_rewards", {}).items()})
            self.agent_combo_rewards = defaultdict(list, {k: list(v) for k, v in state.get("agent_combo_rewards", {}).items()})
            self.task_type_structure_map = defaultdict(dict, state.get("task_type_structure_map", {}))
            self.feature_importance = state.get("feature_importance", self.feature_importance)
        except Exception:
            pass
    
    def _save_execution_record(
        self,
        task_type: str,
        structure_vector: DAGStructureVector,
        reward: StructuralReward,
        credit_assignment: StructuralCreditAssignment
    ):
        """Save individual execution record for audit"""
        record = {
            "task_type": task_type,
            "structure_vector": structure_vector.to_dict(),
            "reward": reward.to_dict(),
            "credit_assignment": credit_assignment.to_dict(),
            "recorded_at": datetime.now().isoformat()
        }
        
        records_dir = os.path.join(self.artifacts_dir, "execution_records")
        os.makedirs(records_dir, exist_ok=True)
        
        path = os.path.join(records_dir, f"{reward.run_id}_structural.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
    
    def get_learning_report(self) -> Dict[str, Any]:
        """Generate learning report"""
        return {
            "unique_topologies_seen": len(self.topology_rewards),
            "unique_agent_combos_seen": len(self.agent_combo_rewards),
            "task_types_with_data": list(self.task_type_structure_map.keys()),
            "feature_importance": self.feature_importance,
            "top_topologies": sorted(
                [(k, np.mean(v)) for k, v in self.topology_rewards.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "top_agent_combos": sorted(
                [(k, np.mean(v)) for k, v in self.agent_combo_rewards.items()],
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "generated_at": datetime.now().isoformat()
        }

    def _export_policy_files(self):
        """
        Export structural policy and preference stats for consumption by execution engine.
        - structural_policy.json: best topology per task type
        - dag_preference_stats.json: summary stats
        """
        # Structural policy: best topology + suggested agents per task type
        policy = {}
        for task_type, topo_map in self.task_type_structure_map.items():
            if not topo_map:
                continue
            best_topo = max(topo_map.items(), key=lambda x: x[1])
            policy[task_type] = {
                "topology_hash": best_topo[0],
                "expected_reward": best_topo[1],
            }

        policy_path = os.path.join(self.artifacts_dir, "structural_policy.json")
        with open(policy_path, "w", encoding="utf-8") as f:
            json.dump(policy, f, indent=2, ensure_ascii=False)

        stats = self.get_learning_report()
        stats_path = os.path.join(self.artifacts_dir, "dag_preference_stats.json")
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        report_path = os.path.join("artifacts", "structural_learning_report.json")
        try:
            os.makedirs(os.path.dirname(report_path), exist_ok=True)
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        except Exception:
            pass


# Global structural learner
_structural_learner: Optional[StructuralLearner] = None

def get_structural_learner() -> StructuralLearner:
    """Get global structural learner instance"""
    global _structural_learner
    if _structural_learner is None:
        _structural_learner = StructuralLearner()
    return _structural_learner


