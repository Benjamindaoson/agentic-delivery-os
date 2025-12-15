#!/usr/bin/env python3
"""
Phase 7 Evaluation Runner
一键运行评测

Usage:
    python scripts/run_phase7_evaluation.py
"""
import sys
import os
import asyncio

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime.eval.harness import EvaluationHarness

async def main():
    """运行评测"""
    print("=" * 60)
    print("Phase 7 Evaluation Runner")
    print("=" * 60)
    
    # 初始化 harness
    harness = EvaluationHarness()
    
    # 运行评测
    run_id = await harness.run_evaluation(
        task_suite_path="runtime/eval/task_suite.json",
        system_matrix_path="runtime/eval/system_matrix.json",
        seed=42,
        model_provider="openai",
        model_version="gpt-4"
    )
    
    print(f"\n✓ Evaluation completed")
    print(f"Run ID: {run_id}")
    print(f"Results: artifacts/phase7/runs/{run_id}/")
    print(f"Summary: artifacts/phase7/summary/leaderboard_{run_id}.json")

if __name__ == "__main__":
    asyncio.run(main())

