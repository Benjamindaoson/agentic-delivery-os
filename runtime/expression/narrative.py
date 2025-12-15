"""
Narrative Layer: 确定映射（无自由生成）
Narrative 是 GovernanceDecision → 模板 的确定映射
模板必须版本化
不允许默认分支
不可命中即失败
"""
import hashlib
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
# ExecutionMode 不需要导入，直接使用字符串匹配

@dataclass
class NarrativeInput:
    """Narrative 输入"""
    governance_decision: str  # ExecutionMode value
    trigger: Optional[str] = None

@dataclass
class NarrativeTemplate:
    """Narrative 模板（静态定义）"""
    id: str
    allowed_decisions: List[str]
    allowed_triggers: List[str]
    text: str

@dataclass
class NarrativeOutput:
    """Narrative 输出"""
    narrative_id: str
    text: str
    narrative_version: str
    narrative_hash: str

class NarrativeEngine:
    """叙事引擎（确定映射，无自由生成）"""
    
    def __init__(self):
        self.version = "1.0"
        # 静态模板定义（不允许默认分支）
        self.templates = [
            NarrativeTemplate(
                id="DEGRADED_BUDGET",
                allowed_decisions=["degraded"],
                allowed_triggers=["BUDGET_EXCEEDED", "budget_or_governance_change"],
                text="系统因预算超限自动降级执行"
            ),
            NarrativeTemplate(
                id="DEGRADED_RISK",
                allowed_decisions=["degraded"],
                allowed_triggers=["HIGH_RISK", "risk_check"],
                text="系统因检测到高风险自动降级执行"
            ),
            NarrativeTemplate(
                id="MINIMAL_CONFLICT",
                allowed_decisions=["minimal"],
                allowed_triggers=["SOFT_CONFLICT", "conflict"],
                text="系统因检测到软冲突切换到最小执行模式"
            ),
            NarrativeTemplate(
                id="PAUSED_HARD_CONFLICT",
                allowed_decisions=["paused"],
                allowed_triggers=["HARD_CONFLICT", "hard_conflicts"],
                text="系统因检测到硬冲突暂停执行，需要人工介入"
            ),
            NarrativeTemplate(
                id="PAUSED_SPEC",
                allowed_decisions=["paused"],
                allowed_triggers=["SPEC_ISSUE", "spec_issue"],
                text="系统因需求不明确暂停执行，需要用户补充信息"
            ),
            NarrativeTemplate(
                id="NORMAL_SUCCESS",
                allowed_decisions=["normal"],
                allowed_triggers=[None, ""],
                text="系统正常执行完成"
            )
        ]
    
    def generate(self, input_data: NarrativeInput) -> NarrativeOutput:
        """
        生成叙事（确定映射）
        
        规则：必须匹配模板，无匹配即失败
        """
        # 查找匹配模板（确定性规则）
        matched_template = None
        
        for template in self.templates:
            # 检查决策匹配
            if input_data.governance_decision not in template.allowed_decisions:
                continue
            
            # 检查触发匹配（如果指定）
            if input_data.trigger:
                if input_data.trigger not in template.allowed_triggers:
                    continue
            else:
                # 如果没有指定 trigger，只匹配允许 None/空字符串的模板
                if None not in template.allowed_triggers and "" not in template.allowed_triggers:
                    continue
            
            matched_template = template
            break
        
        # 无匹配即失败（不允许默认分支）
        if not matched_template:
            raise ValueError(
                f"No narrative template matched for decision={input_data.governance_decision}, "
                f"trigger={input_data.trigger}"
            )
        
        # 计算 hash（确定性）
        input_json = json.dumps(asdict(input_data), sort_keys=True)
        template_json = json.dumps({
            "id": matched_template.id,
            "text": matched_template.text
        }, sort_keys=True)
        combined = input_json + template_json + self.version
        narrative_hash = hashlib.sha256(combined.encode()).hexdigest()
        
        return NarrativeOutput(
            narrative_id=matched_template.id,
            text=matched_template.text,
            narrative_version=self.version,
            narrative_hash=narrative_hash
        )

