"""
Candidate Generator: produce candidate policies from genomes.
Artifacts: artifacts/policy/candidates/{candidate_id}.json
"""
import os
import json
import uuid
from typing import Dict, Any, List
from datetime import datetime
from runtime.artifacts.artifact_schema import compute_inputs_hash, DEFAULT_SCHEMA_VERSION
from runtime.exploration.strategy_genome import StrategyGenome, mutate_genome


class CandidateGenerator:
    def __init__(self, artifacts_dir: str = "artifacts"):
        self.artifacts_dir = artifacts_dir
        self.candidates_dir = os.path.join(artifacts_dir, "policy", "candidates")
        os.makedirs(self.candidates_dir, exist_ok=True)

    def generate_candidates(
        self,
        base_genome: StrategyGenome,
        available_retrieval: List[str],
        available_prompts: List[str],
        available_tools: List[str],
        count: int = 1,
    ) -> List[Dict[str, Any]]:
        candidates = []
        for _ in range(count):
            cid = f"cand_{uuid.uuid4().hex[:8]}"
            mutation = mutate_genome(
                genome=base_genome,
                available_retrieval=available_retrieval,
                available_prompts=available_prompts,
                available_tools=available_tools,
            )
            payload = {
                "schema_version": DEFAULT_SCHEMA_VERSION,
                "candidate_id": cid,
                "parent_id": None,
                "genome": mutation["genome"],
                "mutation": {
                    "parent_id": mutation.get("parent_id"),
                    "operators": mutation.get("mutations", []),
                    "diff": mutation["genome"],
                },
                "evaluation_plan": {
                    "shadow_runs": 50,
                    "golden_replay": 50,
                    "gate_thresholds": {
                        "min_success_rate": 0.8,
                        "max_cost_increase": 0.1,
                    },
                },
                "status": "generated",
                "timestamp": datetime.now().isoformat(),
            }
            payload["inputs_hash"] = compute_inputs_hash(payload["genome"])
            self._persist(cid, payload)
            candidates.append(payload)
        return candidates

    def _persist(self, candidate_id: str, payload: Dict[str, Any]) -> None:
        path = os.path.join(self.candidates_dir, f"{candidate_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)



