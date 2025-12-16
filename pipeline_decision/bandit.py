"""LinUCB contextual bandit for pipeline plan selection."""
from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class BanditDebug:
    used_bandit: bool
    scores: List[Tuple[str, float]]
    chosen: Tuple[str, float, float]


class LinUCBPolicy:
    def __init__(self, plans: List[Dict], alpha: float = 1.5, state_path: str = "artifacts/bandit_state.json"):
        self.alpha = alpha
        self.state_path = state_path
        self.plans = plans
        self.state = self._load_state()

    def _init_arm(self, d: int):
        return {
            "A": [[float(int(i == j)) for j in range(d)] for i in range(d)],
            "b": [0.0 for _ in range(d)],
        }

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_path):
            with open(self.state_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_state(self):
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump(self.state, f)

    def select_arm(self, x: List[float], risk_level: str, risk_score: float) -> Tuple[str, BanditDebug]:
        d = len(x)
        if not self.state:
            plan_id = self._cold_start_plan(risk_level, risk_score)
            return plan_id, BanditDebug(
                used_bandit=False,
                scores=[(plan_id, 0.0)],
                chosen=(plan_id, 0.0, 0.0),
            )

        scores: List[Tuple[str, float]] = []
        top_explore = 0.0
        chosen = None
        for plan in self.plans:
            pid = plan["id"]
            arm = self.state.setdefault(pid, self._init_arm(d))
            A = arm["A"]
            b = arm["b"]
            A_inv = _matrix_inverse(A)
            theta = _mat_vec_mul(A_inv, b)
            exploit = _dot(theta, x)
            explore = self.alpha * math.sqrt(_quad_form(A_inv, x))
            p = exploit + explore
            scores.append((pid, p))
            if chosen is None or p > chosen[1]:
                chosen = (pid, p, exploit)
                top_explore = explore
        scores.sort(key=lambda t: t[1], reverse=True)
        chosen_id = chosen[0]
        self.state.setdefault(chosen_id, self._init_arm(d))
        return chosen_id, BanditDebug(
            used_bandit=True,
            scores=scores[:2],
            chosen=(chosen_id, chosen[1], top_explore),
        )

    def _cold_start_plan(self, risk_level: str, risk_score: float) -> str:
        filtered = [p for p in self.plans if p.get("risk_level") == risk_level]
        if not filtered:
            filtered = self.plans
        filtered.sort(key=lambda p: abs(p.get("target_score", 50) - risk_score))
        return filtered[0]["id"]

    def update(self, x: List[float], plan_id: str, reward: float):
        d = len(x)
        arm = self.state.setdefault(plan_id, self._init_arm(d))
        A = arm["A"]
        b = arm["b"]
        for i in range(d):
            for j in range(d):
                A[i][j] += x[i] * x[j]
        for i in range(d):
            b[i] += reward * x[i]
        arm["A"] = A
        arm["b"] = b
        self.state[plan_id] = arm
        self._save_state()


def _dot(a: List[float], b: List[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _mat_vec_mul(mat: List[List[float]], vec: List[float]) -> List[float]:
    return [sum(mat[i][j] * vec[j] for j in range(len(vec))) for i in range(len(mat))]


def _quad_form(mat: List[List[float]], vec: List[float]) -> float:
    tmp = _mat_vec_mul(mat, vec)
    return sum(vec[i] * tmp[i] for i in range(len(vec)))


def _matrix_inverse(mat: List[List[float]]) -> List[List[float]]:
    n = len(mat)
    inv = [[float(int(i == j)) for j in range(n)] for i in range(n)]
    a = [row[:] for row in mat]
    for i in range(n):
        pivot = a[i][i] if a[i][i] != 0 else 1e-6
        factor = pivot
        for j in range(n):
            a[i][j] /= factor
            inv[i][j] /= factor
        for k in range(n):
            if k == i:
                continue
            ratio = a[k][i]
            for j in range(n):
                a[k][j] -= ratio * a[i][j]
                inv[k][j] -= ratio * inv[i][j]
    return inv


__all__ = ["LinUCBPolicy", "BanditDebug"]
