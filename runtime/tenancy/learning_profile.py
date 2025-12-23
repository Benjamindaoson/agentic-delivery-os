"""
TenantLearningProfile: 租户学习配置文件
定义租户级学习策略（conservative / balanced / aggressive）
"""
import os
import json
from typing import Dict, Any, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, asdict


class LearningIntensity(str, Enum):
    """学习强度"""
    CONSERVATIVE = "conservative"  # 低学习率，高稳定性
    BALANCED = "balanced"  # 平衡学习率和稳定性
    AGGRESSIVE = "aggressive"  # 高学习率，快速适应


@dataclass
class LearningProfileConfig:
    """学习配置"""
    intensity: LearningIntensity
    
    # Bandit 配置
    exploration_rate: float  # Epsilon for epsilon-greedy
    ucb_c_param: float  # UCB1 exploration parameter
    
    # Learning 触发条件
    min_runs_for_learning: int  # 最小运行次数
    learning_budget_pct: float  # 学习预算占总预算百分比 (0.0-1.0)
    
    # Policy update 策略
    update_frequency: str  # "every_N_runs" | "daily" | "weekly"
    update_interval: int  # N for every_N_runs
    
    # Exploration budget
    enable_exploration: bool
    exploration_budget_pct: float  # 探索预算占学习预算百分比
    
    # Meta-learning 参与
    contribute_to_meta_learning: bool
    accept_meta_recommendations: bool


class TenantLearningProfile:
    """
    租户学习配置文件管理器
    
    Features:
    - 租户级学习强度配置
    - 预算与学习联动
    - 动态调整学习参数
    - 学习效果跟踪
    """
    
    def __init__(self, artifacts_dir: str = "artifacts/tenants"):
        self.artifacts_dir = artifacts_dir
        os.makedirs(artifacts_dir, exist_ok=True)
        
        # Predefined profiles
        self._profile_templates = {
            LearningIntensity.CONSERVATIVE: LearningProfileConfig(
                intensity=LearningIntensity.CONSERVATIVE,
                exploration_rate=0.05,
                ucb_c_param=0.5,
                min_runs_for_learning=1000,
                learning_budget_pct=0.05,  # 5% budget for learning
                update_frequency="weekly",
                update_interval=0,
                enable_exploration=False,
                exploration_budget_pct=0.1,
                contribute_to_meta_learning=False,
                accept_meta_recommendations=True
            ),
            LearningIntensity.BALANCED: LearningProfileConfig(
                intensity=LearningIntensity.BALANCED,
                exploration_rate=0.1,
                ucb_c_param=1.0,
                min_runs_for_learning=500,
                learning_budget_pct=0.1,  # 10% budget for learning
                update_frequency="daily",
                update_interval=0,
                enable_exploration=True,
                exploration_budget_pct=0.2,
                contribute_to_meta_learning=True,
                accept_meta_recommendations=True
            ),
            LearningIntensity.AGGRESSIVE: LearningProfileConfig(
                intensity=LearningIntensity.AGGRESSIVE,
                exploration_rate=0.2,
                ucb_c_param=2.0,
                min_runs_for_learning=100,
                learning_budget_pct=0.2,  # 20% budget for learning
                update_frequency="every_N_runs",
                update_interval=50,
                enable_exploration=True,
                exploration_budget_pct=0.3,
                contribute_to_meta_learning=True,
                accept_meta_recommendations=True
            )
        }
    
    def get_profile(self, tenant_id: str) -> LearningProfileConfig:
        """获取租户学习配置"""
        profile_path = os.path.join(
            self.artifacts_dir,
            tenant_id,
            "learning_profile.json"
        )
        
        # Try to load from disk
        if os.path.exists(profile_path):
            try:
                with open(profile_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    intensity = LearningIntensity(data["intensity"])
                    config_data = data["config"]
                    config_data["intensity"] = intensity
                    return LearningProfileConfig(**config_data)
            except Exception:
                pass
        
        # Default to BALANCED
        return self._profile_templates[LearningIntensity.BALANCED]
    
    def set_profile(
        self,
        tenant_id: str,
        intensity: LearningIntensity,
        custom_config: Optional[Dict[str, Any]] = None
    ):
        """设置租户学习配置"""
        # Start with template
        if intensity in self._profile_templates:
            config = self._profile_templates[intensity]
        else:
            config = self._profile_templates[LearningIntensity.BALANCED]
        
        # Apply custom overrides
        if custom_config:
            for key, value in custom_config.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # Save
        self._save_profile(tenant_id, config)
    
    def adjust_profile_by_budget(
        self,
        tenant_id: str,
        budget_utilization: float
    ) -> LearningProfileConfig:
        """
        根据预算使用率动态调整学习配置
        
        Logic:
        - 预算紧张时降低学习强度
        - 预算充裕时可增加探索
        """
        current_profile = self.get_profile(tenant_id)
        
        # If budget is critical (>90%), reduce learning
        if budget_utilization > 0.9:
            current_profile.exploration_rate *= 0.5
            current_profile.enable_exploration = False
            current_profile.learning_budget_pct *= 0.5
        
        # If budget is healthy (<50%), can increase exploration
        elif budget_utilization < 0.5:
            current_profile.exploration_rate = min(0.3, current_profile.exploration_rate * 1.2)
            current_profile.learning_budget_pct = min(0.3, current_profile.learning_budget_pct * 1.2)
        
        # Save adjusted profile
        self._save_profile(tenant_id, current_profile)
        
        return current_profile
    
    def calculate_learning_budget(
        self,
        tenant_id: str,
        total_budget: float
    ) -> float:
        """计算租户学习预算"""
        profile = self.get_profile(tenant_id)
        return total_budget * profile.learning_budget_pct
    
    def should_trigger_learning(
        self,
        tenant_id: str,
        runs_since_last_update: int,
        days_since_last_update: int
    ) -> bool:
        """判断是否应触发学习"""
        profile = self.get_profile(tenant_id)
        
        if profile.update_frequency == "every_N_runs":
            return runs_since_last_update >= profile.update_interval
        elif profile.update_frequency == "daily":
            return days_since_last_update >= 1
        elif profile.update_frequency == "weekly":
            return days_since_last_update >= 7
        
        return False
    
    def record_learning_outcome(
        self,
        tenant_id: str,
        improvement: float,
        cost: float
    ):
        """记录学习效果"""
        history_path = os.path.join(
            self.artifacts_dir,
            tenant_id,
            "learning_history.jsonl"
        )
        os.makedirs(os.path.dirname(history_path), exist_ok=True)
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "improvement": improvement,
            "cost": cost,
            "roi": improvement / cost if cost > 0 else 0.0
        }
        
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def _save_profile(self, tenant_id: str, config: LearningProfileConfig):
        """保存学习配置"""
        profile_path = os.path.join(
            self.artifacts_dir,
            tenant_id,
            "learning_profile.json"
        )
        os.makedirs(os.path.dirname(profile_path), exist_ok=True)
        
        data = {
            "tenant_id": tenant_id,
            "intensity": config.intensity.value,
            "config": asdict(config),
            "updated_at": datetime.now().isoformat()
        }
        
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# Global instance
_global_profile_manager: Optional[TenantLearningProfile] = None


def get_tenant_learning_profile() -> TenantLearningProfile:
    """获取全局租户学习配置管理器"""
    global _global_profile_manager
    if _global_profile_manager is None:
        _global_profile_manager = TenantLearningProfile()
    return _global_profile_manager

