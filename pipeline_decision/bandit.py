"""LinUCB contextual bandit for pipeline plan selection."""

from __future__ import annotations

import json
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from typing import Dict, List, Tuple


@dataclass
class BanditDebug:
    used_bandit: bool
    top_scores: List[Tuple[str, float]]
    chosen_score: Dict[str, float]
    gap: float


class LinUCB:
    def __init__(self, arms: List[str], alpha: float, state_path: Path, context_dim: int):
        self.arms = arms
        self.alpha = alpha
        self.state_path = Path(state_path)
        self.context_dim = context_dim
        self.state = self._load_state()

    def _identity(self) -> List[List[float]]:
        return [[1.0 if i == j else 0.0 for j in range(self.context_dim)] for i in range(self.context_dim)]

    def _zeros(self) -> List[List[float]]:
        return [[0.0] for _ in range(self.context_dim)]

    def _init_state(self) -> Dict[str, Dict[str, List[List[float]]]]:
        return {arm: {"A": self._identity(), "b": self._zeros()} for arm in self.arms}

    def _load_state(self) -> Dict[str, Dict[str, List[List[float]]]]:
        if not self.state_path.exists():
            return self._init_state()
        with self.state_path.open("r") as f:
            data = json.load(f)
        for arm in self.arms:
            if arm not in data:
                data[arm] = {"A": self._identity(), "b": self._zeros()}
        return data

    def _persist(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w") as f:
            json.dump(self.state, f)

    def _mat_mul(self, A: List[List[float]], B: List[List[float]]) -> List[List[float]]:
        result = [[0.0 for _ in range(len(B[0]))] for _ in range(len(A))]
        for i in range(len(A)):
            for k in range(len(B)):
                for j in range(len(B[0])):
                    result[i][j] += A[i][k] * B[k][j]
        return result

    def _mat_inv(self, matrix: List[List[float]]) -> List[List[float]]:
        n = len(matrix)
        aug = [row[:] + eye_row[:] for row, eye_row in zip(matrix, self._identity())]
        for i in range(n):
            pivot = aug[i][i]
            if pivot == 0:
                for r in range(i + 1, n):
                    if aug[r][i] != 0:
                        aug[i], aug[r] = aug[r], aug[i]
                        pivot = aug[i][i]
                        break
            pivot = aug[i][i]
            factor = pivot if pivot != 0 else 1.0
            for j in range(2 * n):
                aug[i][j] /= factor
            for r in range(n):
                if r == i:
                    continue
                ratio = aug[r][i]
                for c in range(2 * n):
                    aug[r][c] -= ratio * aug[i][c]
        return [row[n:] for row in aug]

    def _dot(self, a: List[float], b: List[float]) -> float:
        return sum(x * y for x, y in zip(a, b))

    def _outer(self, vec: List[float]) -> List[List[float]]:
        return [[x * y for y in vec] for x in vec]

    def select_arm(self, context_vector: List[float]) -> Tuple[str, BanditDebug]:
        ucb_scores: Dict[str, float] = {}
        for arm, params in self.state.items():
            A = params["A"]
            b = params["b"]
            inv_a = self._mat_inv(A)
            theta_matrix = self._mat_mul(inv_a, b)
            theta = [row[0] for row in theta_matrix]
            exploit = float(self._dot(theta, context_vector))
            ax = [self._dot(row, context_vector) for row in inv_a]
            explore = float(self.alpha * sqrt(max(self._dot(context_vector, ax), 0.0)))
            ucb_scores[arm] = exploit + explore
            ucb_scores[f"{arm}_exploit"] = exploit
            ucb_scores[f"{arm}_explore"] = explore

        arm_scores = {arm: score for arm, score in ucb_scores.items() if not arm.endswith("_exploit") and not arm.endswith("explore")}
        sorted_scores = sorted(arm_scores.items(), key=lambda kv: kv[1], reverse=True)
        chosen_arm, chosen_value = sorted_scores[0]
        gap = chosen_value - sorted_scores[1][1] if len(sorted_scores) > 1 else chosen_value
        exploitation = ucb_scores.get(f"{chosen_arm}_exploit", chosen_value)
        exploration = ucb_scores.get(f"{chosen_arm}_explore", 0.0)
        debug = BanditDebug(
            used_bandit=self.state_path.exists(),
            top_scores=sorted_scores[:2],
            chosen_score={
                "exploration": float(exploration),
                "exploitation": float(exploitation),
                "total": float(chosen_value),
            },
            gap=float(gap),
        )
        return chosen_arm, debug

    def update(self, context_vector: List[float], arm: str, reward: float) -> None:
        params = self.state.setdefault(arm, {"A": self._identity(), "b": self._zeros()})
        A = params["A"]
        b = params["b"]
        outer = self._outer(context_vector)
        for i in range(self.context_dim):
            for j in range(self.context_dim):
                A[i][j] += outer[i][j]
        for i in range(self.context_dim):
            b[i][0] += reward * context_vector[i]
        self.state[arm] = {"A": A, "b": b}
        self._persist()
