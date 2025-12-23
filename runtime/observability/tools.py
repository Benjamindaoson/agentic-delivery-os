"""
Advanced Observability Module - Timeline, DAG, and Artifact Browser
Provides structured access to execution history with replay capabilities
"""

import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path


class ExecutionTimeline:
    """Reconstructs execution timeline from artifacts"""
    
    def __init__(self, artifacts_base: str = "artifacts"):
        self.artifacts_base = artifacts_base
    
    def get_timeline(self, run_id: str) -> List[Dict[str, Any]]:
        """Get chronological timeline of events for a run"""
        timeline = []
        
        # Load all artifacts for this run
        goals_dir = Path(self.artifacts_base) / "goals"
        if goals_dir.exists():
            for file in sorted(goals_dir.iterdir()):
                if file.name.startswith(run_id) and file.suffix == '.json':
                    with open(file) as f:
                        data = json.load(f)
                        artifact_type = file.name.replace(f"{run_id}_", "").replace(".json", "")
                        # Normalize timestamp to float
                        ts = data.get('timestamp', file.stat().st_mtime)
                        if isinstance(ts, str):
                            try:
                                ts = datetime.fromisoformat(ts).timestamp()
                            except:
                                ts = file.stat().st_mtime
                        
                        timeline.append({
                            "timestamp": ts,
                            "type": artifact_type,
                            "artifact_path": str(file),
                            "summary": self._summarize_artifact(artifact_type, data)
                        })
        
        # Add eval result
        eval_path = Path(self.artifacts_base) / "eval" / f"{run_id}.json"
        if eval_path.exists():
            with open(eval_path) as f:
                data = json.load(f)
                ts = data.get('timestamp', eval_path.stat().st_mtime)
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts).timestamp()
                    except:
                        ts = eval_path.stat().st_mtime
                
                timeline.append({
                    "timestamp": ts,
                    "type": "evaluation",
                    "artifact_path": str(eval_path),
                    "summary": f"Quality: {data['quality_score']:.1%}, Cost: ${data['cost']:.4f}"
                })
        
        return sorted(timeline, key=lambda x: x['timestamp'])
    
    def _summarize_artifact(self, artifact_type: str, data: Dict[str, Any]) -> str:
        """Generate human-readable summary of artifact"""
        if artifact_type == "goal_interpretation":
            return f"Goal: {data.get('primary_goal', 'N/A')}"
        elif artifact_type == "high_level_plan":
            return f"Strategy: {data.get('strategy_selected', 'N/A')}"
        elif artifact_type == "task_decomposition":
            return f"Steps: {data.get('total_estimated_steps', 0)}"
        elif artifact_type == "dependency_graph":
            return f"Nodes: {len(data.get('nodes', []))}, Edges: {len(data.get('edges', []))}"
        else:
            return artifact_type.replace("_", " ").title()


class DAGVisualizer:
    """Visualizes execution DAG from planning artifacts"""
    
    def __init__(self, artifacts_base: str = "artifacts"):
        self.artifacts_base = artifacts_base
    
    def get_dag(self, run_id: str) -> Dict[str, Any]:
        """Extract DAG structure from artifacts"""
        graph_path = Path(self.artifacts_base) / "goals" / f"{run_id}_dependency_graph.json"
        decomp_path = Path(self.artifacts_base) / "goals" / f"{run_id}_task_decomposition.json"
        
        if not graph_path.exists():
            return {"nodes": [], "edges": [], "error": "DAG not found"}
        
        with open(graph_path) as f:
            graph = json.load(f)
        
        steps = {}
        if decomp_path.exists():
            with open(decomp_path) as f:
                decomp = json.load(f)
                for step in decomp.get('steps', []):
                    steps[step['step_id']] = step
        
        # Enrich nodes with step details
        enriched_nodes = []
        for node in graph.get('nodes', []):
            node_id = node.get('id')
            step_detail = steps.get(node_id, {})
            enriched_nodes.append({
                **node,
                "description": step_detail.get('description', ''),
                "role": step_detail.get('assigned_role', 'unknown')
            })
        
        return {
            "nodes": enriched_nodes,
            "edges": graph.get('edges', []),
            "run_id": run_id
        }
    
    def export_mermaid(self, run_id: str) -> str:
        """Export DAG as Mermaid diagram"""
        dag = self.get_dag(run_id)
        
        lines = ["graph TD"]
        for node in dag['nodes']:
            node_id = node['id']
            label = node.get('label', f"Node{node_id}")
            lines.append(f"    {node_id}[\"{label}\"]")
        
        for edge in dag['edges']:
            from_node = edge['from']
            to_node = edge['to']
            lines.append(f"    {from_node} --> {to_node}")
        
        return "\n".join(lines)


class ArtifactBrowser:
    """Browse and search artifacts across all runs"""
    
    def __init__(self, artifacts_base: str = "artifacts"):
        self.artifacts_base = Path(artifacts_base)
    
    def search_artifacts(
        self, 
        artifact_type: Optional[str] = None,
        run_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Search artifacts with filters"""
        results = []
        
        for root, dirs, files in os.walk(self.artifacts_base):
            for file in files:
                if not file.endswith('.json'):
                    continue
                
                # Apply filters
                if run_id and run_id not in file:
                    continue
                
                if artifact_type:
                    artifact_dir = os.path.basename(root)
                    if artifact_type not in artifact_dir and artifact_type not in file:
                        continue
                
                file_path = Path(root) / file
                with open(file_path) as f:
                    try:
                        data = json.load(f)
                        results.append({
                            "path": str(file_path.relative_to(self.artifacts_base)),
                            "type": os.path.basename(root),
                            "file": file,
                            "size_bytes": file_path.stat().st_size,
                            "modified": datetime.fromtimestamp(file_path.stat().st_mtime).isoformat(),
                            "preview": str(data)[:200] + "..." if len(str(data)) > 200 else str(data)
                        })
                    except json.JSONDecodeError:
                        continue
                
                if len(results) >= limit:
                    break
        
        return results
    
    def get_artifact_stats(self) -> Dict[str, Any]:
        """Get statistics about all artifacts"""
        stats = {
            "total_artifacts": 0,
            "by_type": {},
            "total_size_mb": 0.0,
            "oldest": None,
            "newest": None
        }
        
        timestamps = []
        for root, dirs, files in os.walk(self.artifacts_base):
            artifact_type = os.path.basename(root)
            for file in files:
                if file.endswith('.json'):
                    stats["total_artifacts"] += 1
                    stats["by_type"][artifact_type] = stats["by_type"].get(artifact_type, 0) + 1
                    
                    file_path = Path(root) / file
                    stats["total_size_mb"] += file_path.stat().st_size / (1024 * 1024)
                    timestamps.append(file_path.stat().st_mtime)
        
        if timestamps:
            stats["oldest"] = datetime.fromtimestamp(min(timestamps)).isoformat()
            stats["newest"] = datetime.fromtimestamp(max(timestamps)).isoformat()
        
        return stats


# CLI interface for observability tools
def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python -m runtime.observability.tools [timeline|dag|browse|stats] <run_id>")
        return
    
    command = sys.argv[1]
    
    if command == "timeline":
        if len(sys.argv) < 3:
            print("Usage: ... timeline <run_id>")
            return
        run_id = sys.argv[2]
        timeline = ExecutionTimeline()
        events = timeline.get_timeline(run_id)
        print(f"\n⏱️  Timeline for {run_id}:\n")
        for event in events:
            print(f"  [{event['timestamp']}] {event['type']}: {event['summary']}")
    
    elif command == "dag":
        if len(sys.argv) < 3:
            print("Usage: ... dag <run_id>")
            return
        run_id = sys.argv[2]
        visualizer = DAGVisualizer()
        print(f"\n📊 DAG for {run_id}:\n")
        print(visualizer.export_mermaid(run_id))
    
    elif command == "browse":
        browser = ArtifactBrowser()
        artifacts = browser.search_artifacts(limit=20)
        print(f"\n📁 Recent Artifacts:\n")
        for artifact in artifacts:
            print(f"  {artifact['path']} ({artifact['size_bytes']} bytes)")
    
    elif command == "stats":
        browser = ArtifactBrowser()
        stats = browser.get_artifact_stats()
        print(f"\n📈 Artifact Statistics:\n")
        print(f"  Total: {stats['total_artifacts']}")
        print(f"  Size: {stats['total_size_mb']:.2f} MB")
        print(f"  By Type: {stats['by_type']}")
    
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()

