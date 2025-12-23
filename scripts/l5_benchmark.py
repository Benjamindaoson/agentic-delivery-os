import json
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from runtime.l5_engine import L5Engine
from runtime.workbench.cli import WorkbenchCLI

def run_benchmark():
    engine = L5Engine()
    cli = WorkbenchCLI()
    
    tasks = [
        "What is machine learning?",
        "Create a marketing plan for a new EV.",
        "How to build a quantum computer?",
        "Summarize the history of AI."
    ]
    
    print(f"Starting L5 Benchmark Run at {datetime.now()}")
    for i, task in enumerate(tasks):
        print(f"[{i+1}/{len(tasks)}] Executing: {task}")
        engine.execute_run(task)
    
    print("\nBenchmark Complete.\n")
    cli.show_agent_profiles()
    cli.show_system_trends()

if __name__ == "__main__":
    run_benchmark()



