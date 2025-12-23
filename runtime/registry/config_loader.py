import yaml
import json
from typing import Dict, Any, List
from pathlib import Path


class ConfigRegistry:
    """Centralized registry for agents, tools, and policies"""
    
    def __init__(self, config_dir: str = "config"):
        self.config_dir = Path(config_dir)
        self.agents = {}
        self.tools = {}
        self._load_all()
    
    def _load_all(self):
        """Load all YAML configurations"""
        self._load_agents()
        self._load_tools()
    
    def _load_agents(self):
        """Load agent registry from YAML"""
        agents_file = self.config_dir / "agents.yaml"
        if agents_file.exists():
            with open(agents_file) as f:
                data = yaml.safe_load(f)
                for agent in data.get('agents', []):
                    self.agents[agent['id']] = agent
    
    def _load_tools(self):
        """Load tool registry from YAML"""
        tools_file = self.config_dir / "tools.yaml"
        if tools_file.exists():
            with open(tools_file) as f:
                data = yaml.safe_load(f)
                for tool in data.get('tools', []):
                    self.tools[tool['id']] = tool
    
    def get_agent(self, agent_id: str) -> Dict[str, Any]:
        """Get agent configuration by ID"""
        return self.agents.get(agent_id, {})
    
    def get_tool(self, tool_id: str) -> Dict[str, Any]:
        """Get tool configuration by ID"""
        return self.tools.get(tool_id, {})
    
    def list_agents(self) -> List[str]:
        """List all agent IDs"""
        return list(self.agents.keys())
    
    def list_tools(self) -> List[str]:
        """List all tool IDs"""
        return list(self.tools.keys())
    
    def validate_agent_tool_access(self, agent_id: str, tool_id: str) -> bool:
        """Check if agent has permission to use tool"""
        agent = self.get_agent(agent_id)
        if not agent:
            return False
        
        allowed_tools = agent.get('allowed_tools', [])
        return tool_id in allowed_tools or '*' in allowed_tools
    
    def export_json(self, output_dir: str = "artifacts/registry"):
        """Export registry to JSON for runtime access"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        with open(f"{output_dir}/agents.json", "w") as f:
            json.dump(self.agents, f, indent=2)
        
        with open(f"{output_dir}/tools.json", "w") as f:
            json.dump(self.tools, f, indent=2)


if __name__ == "__main__":
    registry = ConfigRegistry()
    print(f"Loaded {len(registry.agents)} agents")
    print(f"Loaded {len(registry.tools)} tools")
    registry.export_json()
    print("Registry exported to artifacts/registry/")



