"""
Strategy Genome and mutation operators.
"""
import random
from dataclasses import dataclass, asdict
from typing import Dict, Any, List
from runtime.artifacts.artifact_schema import DEFAULT_SCHEMA_VERSION


@dataclass
class StrategyGenome:
    schema_version: str
    retrieval_policy_id: str
    prompt_template_id: str
    tool_chain_id: str
    planner_mode: str
    params: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def mutate_genome(
    genome: StrategyGenome,
    available_retrieval: List[str],
    available_prompts: List[str],
    available_tools: List[str],
    seed: int = 42,
) -> Dict[str, Any]:
    random.seed(seed)
    mutations = []
    new_genome = genome.to_dict()
    params = dict(genome.params)

    # 1) retrieval policy switch
    if available_retrieval:
        cand = random.choice(available_retrieval)
        if cand != genome.retrieval_policy_id:
            new_genome["retrieval_policy_id"] = cand
            mutations.append("retrieval_switch")

    # 2) prompt template variant
    if available_prompts:
        cand = random.choice(available_prompts)
        if cand != genome.prompt_template_id:
            new_genome["prompt_template_id"] = cand
            mutations.append("prompt_variant")

    # 3) tool chain swap
    if available_tools:
        cand = random.choice(available_tools)
        if cand != genome.tool_chain_id:
            new_genome["tool_chain_id"] = cand
            mutations.append("tool_swap")

    # 4) param perturbation
    if "top_k" in params:
        params["top_k"] = max(1, params["top_k"] + random.choice([-2, -1, 1, 2]))
        mutations.append("param_perturb_top_k")
    if "tool_timeout" in params:
        params["tool_timeout"] = max(1, params["tool_timeout"] + random.choice([-200, -100, 100, 200]))
        mutations.append("param_perturb_timeout")

    new_genome["params"] = params
    return {
        "schema_version": DEFAULT_SCHEMA_VERSION,
        "parent_id": genome.to_dict().get("parent_id", None),
        "genome": new_genome,
        "mutations": mutations,
    }



