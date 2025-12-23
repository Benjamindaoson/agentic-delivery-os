from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import json
import os

class WorkbenchCLI:
    def __init__(self, artifacts_base: str = "artifacts"):
        self.artifacts_base = artifacts_base
        self.console = Console()

    def show_agent_profiles(self):
        table = Table(title="Agent Long-term Profiles")
        table.add_column("Agent ID", style="cyan")
        table.add_column("Success Rate", style="green")
        table.add_column("Total Runs", style="yellow")
        table.add_column("Avg Latency", style="magenta")

        path = f"{self.artifacts_base}/agent_profiles"
        if os.path.exists(path):
            for file in os.listdir(path):
                if file.endswith(".json"):
                    with open(f"{path}/{file}", "r") as f:
                        data = json.load(f)
                        # Support both new and existing schema
                        if "performance" in data and data["performance"]:
                            perf = data["performance"]
                            table.add_row(
                                data["agent_id"],
                                f"{perf['success_rate']:.2%}",
                                str(perf['total_runs']),
                                f"{perf['avg_latency']:.2f}ms"
                            )
                        else:
                            table.add_row(
                                data["agent_id"],
                                f"{data.get('success_rate', 0.0):.2%}",
                                str(data.get('total_runs', 0)),
                                f"{data.get('avg_latency_ms', 0.0):.2f}ms"
                            )
        self.console.print(table)

    def show_system_trends(self, state_path: str = "memory/global_state.json"):
        if os.path.exists(state_path):
            with open(state_path, "r") as f:
                data = json.load(f)
                metrics = data.get("metrics", data)
                version = data.get("system_version", "L5.0")
                total_runs = metrics.get("total_runs", 0)
                cost = metrics.get("cumulative_cost", metrics.get("total_cost", 0.0))
                
                self.console.print(Panel(f"System Version: {version}\nTotal Runs: {total_runs}\nCumulative Cost: ${cost:.4f}", title="System Trends"))
        else:
            self.console.print("[red]No global state found.[/red]")
