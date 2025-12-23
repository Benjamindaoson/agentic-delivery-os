"""
Meta-Policy - Cross-tenant learning with privacy
Upgraded to implement AbstractPolicy, cold-start warm boot, pattern embeddings, and privacy-safe aggregation.
"""

from typing import Dict, List, Any, Optional
import json
import os
import hashlib
import math
import random
from datetime import datetime
from collections import defaultdict

from learning.abstract_policy import AbstractPolicy


class MetaPolicy(AbstractPolicy):
    """
    Meta-learning across tenants
    Learns abstract patterns that can warm-start new tenants
    Respects tenant privacy and opt-in requirements
    """
    
    def __init__(self, artifacts_path: str = "artifacts/learning/meta_policy"):
        self.artifacts_path = artifacts_path
        os.makedirs(artifacts_path, exist_ok=True)
        
        # Abstract patterns (no tenant-specific data)
        self.patterns = {
            "goal_type_affinity": {},  # Which strategies work for which goals
            "cost_quality_tradeoffs": {},  # Cost vs quality curves
            "failure_signatures": {},  # Common failure patterns
            "success_recipes": {},  # High-performing configurations
            "embeddings": {},  # pattern embedding -> aggregated stats
        }
        
        # Tenant participation
        self.participating_tenants = set()
        self.tenant_contributions = {}
        
        # Statistics
        self.stats = {
            "total_patterns": 0,
            "total_contributions": 0,
            "participating_tenants": 0
        }
    
    def register_tenant(self, tenant_id: str, opt_in: bool = False):
        """Register tenant for meta-learning"""
        if opt_in:
            self.participating_tenants.add(tenant_id)
            self.tenant_contributions[tenant_id] = 0
            self.stats["participating_tenants"] = len(self.participating_tenants)
    
    def unregister_tenant(self, tenant_id: str):
        """Remove tenant from meta-learning (privacy)"""
        self.participating_tenants.discard(tenant_id)
        self.tenant_contributions.pop(tenant_id, None)
        self.stats["participating_tenants"] = len(self.participating_tenants)
    
    def contribute_patterns(
        self,
        tenant_id: str,
        tenant_data: Dict[str, Any]
    ):
        """
        Accept anonymized patterns from tenant
        Only abstract patterns, no sensitive data
        """
        if tenant_id not in self.participating_tenants:
            return
        
        # Extract abstract patterns
        goal_type = tenant_data.get("goal_type")
        strategy = tenant_data.get("strategy_used")
        success = tenant_data.get("success", False)
        quality = tenant_data.get("quality_score", 0)
        cost = tenant_data.get("cost", 0)

        # Privacy-safe hashing + noise
        pattern_embedding = self._embed_pattern(goal_type, strategy, tenant_data)
        noise = random.gauss(0, 0.01)
        
        # Update goal type affinity
        key = f"{goal_type}::{strategy}"
        if key not in self.patterns["goal_type_affinity"]:
            self.patterns["goal_type_affinity"][key] = {
                "successes": 0,
                "failures": 0,
                "avg_quality": 0.0,
                "sample_count": 0
            }
        
        pattern = self.patterns["goal_type_affinity"][key]
        if success:
            pattern["successes"] += 1
        else:
            pattern["failures"] += 1
        
        # Update avg quality (exponential moving average)
        n = pattern["sample_count"]
        pattern["avg_quality"] = (pattern["avg_quality"] * n + quality) / (n + 1)
        pattern["sample_count"] += 1
        
        # Update cost-quality tradeoffs
        cost_bucket = int(cost * 10) / 10  # Round to nearest 0.1
        if cost_bucket not in self.patterns["cost_quality_tradeoffs"]:
            self.patterns["cost_quality_tradeoffs"][cost_bucket] = {
                "avg_quality": 0.0,
                "sample_count": 0
            }
        
        cq_pattern = self.patterns["cost_quality_tradeoffs"][cost_bucket]
        n = cq_pattern["sample_count"]
        cq_pattern["avg_quality"] = (cq_pattern["avg_quality"] * n + quality) / (n + 1)
        cq_pattern["sample_count"] += 1
        
        # Update failure signatures (if failed)
        if not success:
            failure_reason = tenant_data.get("failure_reason", "unknown")
            if failure_reason not in self.patterns["failure_signatures"]:
                self.patterns["failure_signatures"][failure_reason] = {
                    "count": 0,
                    "common_contexts": []
                }
            self.patterns["failure_signatures"][failure_reason]["count"] += 1
        
        # Update success recipes (if high quality)
        if success and quality > 0.85:
            recipe = f"{goal_type}::{strategy}"
            if recipe not in self.patterns["success_recipes"]:
                self.patterns["success_recipes"][recipe] = {
                    "count": 0,
                    "avg_quality": 0.0,
                    "avg_cost": 0.0
                }
            
            recipe_pattern = self.patterns["success_recipes"][recipe]
            n = recipe_pattern["count"]
            recipe_pattern["avg_quality"] = (recipe_pattern["avg_quality"] * n + quality) / (n + 1)
            recipe_pattern["avg_cost"] = (recipe_pattern["avg_cost"] * n + cost) / (n + 1)
            recipe_pattern["count"] += 1
        
        # Update contribution tracking
        self.tenant_contributions[tenant_id] += 1
        self.stats["total_contributions"] += 1
        self.stats["total_patterns"] = (
            len(self.patterns["goal_type_affinity"]) +
            len(self.patterns["success_recipes"])
        )

        # Embedding aggregation (privacy-safe, hashed key + noise)
        embed_key = pattern_embedding["hash"]
        if embed_key not in self.patterns["embeddings"]:
            self.patterns["embeddings"][embed_key] = {
                "avg_quality": 0.0,
                "avg_cost": 0.0,
                "count": 0,
                "dim": pattern_embedding["vector"],
            }
        emb = self.patterns["embeddings"][embed_key]
        n = emb["count"]
        emb["avg_quality"] = (emb["avg_quality"] * n + quality + noise) / (n + 1)
        emb["avg_cost"] = (emb["avg_cost"] * n + cost + noise) / (n + 1)
        emb["count"] += 1
    
    def get_warm_start_policy(
        self,
        goal_type: str,
        cost_budget: float = 1.0
    ) -> Dict[str, Any]:
        """
        Generate warm-start policy for new tenant
        Based on meta-learned patterns
        """
        # Find best strategies for this goal type
        relevant_patterns = {
            k: v for k, v in self.patterns["goal_type_affinity"].items()
            if k.startswith(f"{goal_type}::")
        }
        
        if not relevant_patterns:
            # No data, return default
            return {
                "strategy": "sequential",
                "confidence": 0.0,
                "source": "default"
            }
        
        # Rank by success rate
        ranked = sorted(
            relevant_patterns.items(),
            key=lambda x: x[1]["successes"] / (x[1]["successes"] + x[1]["failures"] + 1),
            reverse=True
        )
        
        best_pattern = ranked[0]
        strategy = best_pattern[0].split("::")[-1]
        
        # Check cost-quality tradeoff
        suitable_cost = None
        for cost, cq in self.patterns["cost_quality_tradeoffs"].items():
            if cost <= cost_budget and cq["avg_quality"] > 0.7:
                suitable_cost = cost
                break
        
        return {
            "strategy": strategy,
            "recommended_cost_budget": suitable_cost or cost_budget,
            "expected_quality": best_pattern[1]["avg_quality"],
            "confidence": min(1.0, best_pattern[1]["sample_count"] / 100),
            "source": "meta_learning",
            "sample_size": best_pattern[1]["sample_count"]
        }

    # ==== AbstractPolicy interface ====
    def encode_state(self, context: Dict[str, Any]) -> Dict[str, Any]:
        return context or {}

    def select_action(self, state: Dict[str, Any], **kwargs) -> Any:
        # Use warm start policy as action recommendation
        goal_type = state.get("goal_type", "general")
        budget = state.get("cost_budget", 1.0)
        return self.get_warm_start_policy(goal_type, budget)

    def compute_reward(self, outcome: Dict[str, Any], **kwargs) -> float:
        # Meta-level reward: quality - cost tradeoff (simple)
        quality = outcome.get("quality_score", 0.5)
        cost = outcome.get("cost", 0.0)
        return max(0.0, quality - 0.1 * cost)

    def update(self, transition: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        # Meta-policy learns via contribute_patterns
        tenant_id = transition.get("tenant_id", "unknown")
        outcome = transition.get("outcome", {})
        self.contribute_patterns(tenant_id, outcome)
        return {"updated": True}

    def export_policy(self) -> Dict[str, Any]:
        return {
            "policy_id": "meta_policy",
            "version": "1.0",
            "patterns": self.patterns,
            "stats": self.stats,
        }

    # ==== Helpers ====
    def _embed_pattern(self, goal_type: str, strategy: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compute a privacy-safe embedding (hash + numeric vector).
        """
        # Hash key to avoid leaking tenant IDs
        key_str = f"{goal_type}::{strategy}::{payload.get('success', False)}"
        hash_key = hashlib.sha256(key_str.encode()).hexdigest()[:16]

        # Simple deterministic vector (length 4)
        quality = float(payload.get("quality_score", 0.5))
        cost = float(payload.get("cost", 0.0))
        success = 1.0 if payload.get("success", False) else 0.0
        # Normalize cost with log scale
        cost_norm = math.tanh(cost)
        vector = [quality, cost_norm, success, 1.0 if goal_type else 0.0]

        return {"hash": hash_key, "vector": vector}
    
    def get_failure_insights(self) -> List[Dict[str, Any]]:
        """Get common failure patterns"""
        insights = []
        
        for reason, data in self.patterns["failure_signatures"].items():
            if data["count"] >= 5:  # Only report frequent failures
                insights.append({
                    "failure_reason": reason,
                    "frequency": data["count"],
                    "severity": "high" if data["count"] > 20 else "medium"
                })
        
        return sorted(insights, key=lambda x: x["frequency"], reverse=True)
    
    def get_success_recipes(self, min_quality: float = 0.85) -> List[Dict[str, Any]]:
        """Get proven success recipes"""
        recipes = []
        
        for recipe, data in self.patterns["success_recipes"].items():
            if data["avg_quality"] >= min_quality and data["count"] >= 3:
                goal_type, strategy = recipe.split("::")
                recipes.append({
                    "goal_type": goal_type,
                    "strategy": strategy,
                    "avg_quality": data["avg_quality"],
                    "avg_cost": data["avg_cost"],
                    "sample_size": data["count"],
                    "confidence": min(1.0, data["count"] / 50)
                })
        
        return sorted(recipes, key=lambda x: x["avg_quality"], reverse=True)
    
    def save_meta_policy(self):
        """Persist meta-policy"""
        meta_policy = {
            "patterns": self.patterns,
            "stats": self.stats,
            "participating_tenants": len(self.participating_tenants),  # Count only, no IDs
            "saved_at": datetime.now().isoformat()
        }
        
        path = os.path.join(self.artifacts_path, "meta_policy.json")
        with open(path, 'w') as f:
            json.dump(meta_policy, f, indent=2)


# Global meta-policy
_meta_policy: Optional[MetaPolicy] = None

def get_meta_policy() -> MetaPolicy:
    """Get global meta-policy"""
    global _meta_policy
    if _meta_policy is None:
        _meta_policy = MetaPolicy()
    return _meta_policy



