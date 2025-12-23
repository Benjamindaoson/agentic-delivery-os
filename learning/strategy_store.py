"""
Strategy Store - Versioned strategy storage with rollback
L5 Core Component: Policy persistence and version control
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import os
import shutil


class StrategyVersion(BaseModel):
    """Single version of a strategy"""
    version_id: str
    policy_type: str
    config: Dict[str, Any]
    created_at: datetime = Field(default_factory=datetime.now)
    created_by: str = "system"
    is_active: bool = False
    performance_metrics: Dict[str, float] = {}
    notes: str = ""


class StrategyStore:
    """
    Persistent storage for strategy versions
    Supports versioning, activation, and rollback
    """
    
    def __init__(self, store_path: str = "artifacts/learning/policy_versions"):
        self.store_path = store_path
        os.makedirs(store_path, exist_ok=True)
        
        # Track active versions
        self.active_versions: Dict[str, str] = self._load_active_versions()
    
    def save_version(
        self,
        policy_type: str,
        config: Dict[str, Any],
        version_id: Optional[str] = None,
        notes: str = ""
    ) -> StrategyVersion:
        """
        Save a new strategy version
        Args:
            policy_type: Type of policy (planner, tool_selection, etc.)
            config: Configuration dict
            version_id: Optional version ID (auto-generated if not provided)
            notes: Optional notes about this version
        Returns:
            StrategyVersion object
        """
        if version_id is None:
            # Auto-generate version ID
            existing_versions = self._get_versions_for_type(policy_type)
            version_num = len(existing_versions) + 1
            version_id = f"{policy_type}_v{version_num}"
        
        version = StrategyVersion(
            version_id=version_id,
            policy_type=policy_type,
            config=config,
            is_active=False,  # Not active by default
            notes=notes
        )
        
        # Save to disk
        self._persist_version(version)
        
        return version
    
    def activate_version(self, version_id: str) -> bool:
        """
        Activate a specific version
        Deactivates previous active version of the same type
        """
        # Load version
        version = self.load_version(version_id)
        if not version:
            return False
        
        # Deactivate current active version of this type
        current_active = self.active_versions.get(version.policy_type)
        if current_active:
            current = self.load_version(current_active)
            if current:
                current.is_active = False
                self._persist_version(current)
        
        # Activate new version
        version.is_active = True
        self._persist_version(version)
        
        # Update active versions tracker
        self.active_versions[version.policy_type] = version_id
        self._save_active_versions()
        
        return True
    
    def rollback(self, policy_type: str, target_version_id: Optional[str] = None) -> bool:
        """
        Rollback to a previous version
        If target_version_id is not specified, rollback to previous version
        """
        versions = self._get_versions_for_type(policy_type)
        if len(versions) < 2:
            return False  # Nothing to rollback to
        
        if target_version_id:
            # Rollback to specific version
            if target_version_id not in [v.version_id for v in versions]:
                return False
            return self.activate_version(target_version_id)
        else:
            # Rollback to previous version
            # Sort by creation time
            sorted_versions = sorted(versions, key=lambda v: v.created_at, reverse=True)
            if len(sorted_versions) >= 2:
                previous_version = sorted_versions[1]
                return self.activate_version(previous_version.version_id)
        
        return False
    
    def load_version(self, version_id: str) -> Optional[StrategyVersion]:
        """Load a specific version"""
        path = self._get_version_path(version_id)
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
                return StrategyVersion(**data)
        return None
    
    def get_active_version(self, policy_type: str) -> Optional[StrategyVersion]:
        """Get currently active version for a policy type"""
        active_id = self.active_versions.get(policy_type)
        if active_id:
            return self.load_version(active_id)
        return None
    
    def list_versions(self, policy_type: Optional[str] = None) -> List[StrategyVersion]:
        """List all versions, optionally filtered by type"""
        versions = []
        
        for filename in os.listdir(self.store_path):
            if filename == "active_versions.json":
                continue
            
            if filename.endswith('.json'):
                path = os.path.join(self.store_path, filename)
                with open(path) as f:
                    try:
                        version = StrategyVersion(**json.load(f))
                        if policy_type is None or version.policy_type == policy_type:
                            versions.append(version)
                    except:
                        continue
        
        return sorted(versions, key=lambda v: v.created_at, reverse=True)
    
    def compare_versions(
        self,
        version_id_1: str,
        version_id_2: str
    ) -> Dict[str, Any]:
        """Compare two versions"""
        v1 = self.load_version(version_id_1)
        v2 = self.load_version(version_id_2)
        
        if not v1 or not v2:
            return {"error": "One or both versions not found"}
        
        # Compare configs
        config_diff = self._compute_dict_diff(v1.config, v2.config)
        
        # Compare metrics
        metrics_diff = {}
        for key in set(v1.performance_metrics.keys()) | set(v2.performance_metrics.keys()):
            m1 = v1.performance_metrics.get(key, 0)
            m2 = v2.performance_metrics.get(key, 0)
            metrics_diff[key] = m2 - m1
        
        return {
            "version_1": version_id_1,
            "version_2": version_id_2,
            "config_changes": config_diff,
            "metrics_changes": metrics_diff,
            "time_difference": (v2.created_at - v1.created_at).total_seconds()
        }
    
    def update_metrics(self, version_id: str, metrics: Dict[str, float]):
        """Update performance metrics for a version"""
        version = self.load_version(version_id)
        if version:
            version.performance_metrics.update(metrics)
            self._persist_version(version)
    
    def export_config(self, version_id: str, output_path: str):
        """Export version config to a file"""
        version = self.load_version(version_id)
        if version:
            with open(output_path, 'w') as f:
                json.dump(version.config, f, indent=2)
    
    def import_config(self, policy_type: str, config_path: str, notes: str = "") -> StrategyVersion:
        """Import config from a file"""
        with open(config_path) as f:
            config = json.load(f)
        
        return self.save_version(policy_type, config, notes=notes)
    
    def _get_versions_for_type(self, policy_type: str) -> List[StrategyVersion]:
        """Get all versions for a specific policy type"""
        return self.list_versions(policy_type)
    
    def _persist_version(self, version: StrategyVersion):
        """Persist version to disk"""
        path = self._get_version_path(version.version_id)
        with open(path, 'w') as f:
            f.write(version.model_dump_json(indent=2))
    
    def _get_version_path(self, version_id: str) -> str:
        """Get file path for a version"""
        return os.path.join(self.store_path, f"{version_id}.json")
    
    def _load_active_versions(self) -> Dict[str, str]:
        """Load active versions mapping"""
        path = os.path.join(self.store_path, "active_versions.json")
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
        return {}
    
    def _save_active_versions(self):
        """Save active versions mapping"""
        path = os.path.join(self.store_path, "active_versions.json")
        with open(path, 'w') as f:
            json.dump(self.active_versions, f, indent=2)
    
    def _compute_dict_diff(self, dict1: Dict[str, Any], dict2: Dict[str, Any]) -> Dict[str, Any]:
        """Compute difference between two dicts"""
        diff = {}
        
        all_keys = set(dict1.keys()) | set(dict2.keys())
        
        for key in all_keys:
            if key not in dict1:
                diff[key] = {"added": dict2[key]}
            elif key not in dict2:
                diff[key] = {"removed": dict1[key]}
            elif dict1[key] != dict2[key]:
                diff[key] = {"from": dict1[key], "to": dict2[key]}
        
        return diff


# Singleton instance
_store = None

def get_strategy_store() -> StrategyStore:
    """Get singleton StrategyStore instance"""
    global _store
    if _store is None:
        _store = StrategyStore()
    return _store



