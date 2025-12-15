"""
Operational Readiness & SRE 能力
监控、告警、Runbook
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

@dataclass
class AlertRule:
    """告警规则（明确阈值，非模糊）"""
    rule_id: str
    metric_name: str
    threshold: float
    operator: str  # gt, lt, eq
    severity: str  # critical, warning, info
    action: str  # pause, throttle, shutdown, notify

@dataclass
class Alert:
    """告警"""
    alert_id: str
    rule_id: str
    metric_name: str
    metric_value: float
    threshold: float
    severity: str
    timestamp: str
    resolved: bool
    resolution: Optional[str]

@dataclass
class Incident:
    """故障事件"""
    incident_id: str
    alert_id: str
    severity: str
    description: str
    timestamp: str
    resolved: bool
    resolution: Optional[str]
    runbook_ref: str

class MonitoringSystem:
    """监控系统"""
    
    def __init__(self, base_dir: str = "artifacts/monitoring"):
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        self.alerts_file = os.path.join(base_dir, "alerts.jsonl")
        self.incidents_file = os.path.join(base_dir, "incidents.jsonl")
        self.alert_rules = self._load_alert_rules()
    
    def _load_alert_rules(self) -> List[AlertRule]:
        """加载告警规则"""
        rules_file = os.path.join(self.base_dir, "alert_rules.json")
        if os.path.exists(rules_file):
            with open(rules_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [AlertRule(**rule) for rule in data.get("rules", [])]
        
        # 默认规则
        default_rules = [
            AlertRule(
                rule_id="rule_001",
                metric_name="success_rate",
                threshold=0.90,
                operator="lt",
                severity="critical",
                action="pause"
            ),
            AlertRule(
                rule_id="rule_002",
                metric_name="failure_rate",
                threshold=0.10,
                operator="gt",
                severity="warning",
                action="throttle"
            ),
            AlertRule(
                rule_id="rule_003",
                metric_name="cost_spike",
                threshold=1.5,  # 1.5x average
                operator="gt",
                severity="warning",
                action="throttle"
            ),
            AlertRule(
                rule_id="rule_004",
                metric_name="abnormal_replay_length",
                threshold=1000,  # events
                operator="gt",
                severity="info",
                action="notify"
            )
        ]
        self._save_alert_rules(default_rules)
        return default_rules
    
    def _save_alert_rules(self, rules: List[AlertRule]):
        """保存告警规则"""
        rules_file = os.path.join(self.base_dir, "alert_rules.json")
        data = {
            "version": "1.0",
            "rules": [asdict(rule) for rule in rules]
        }
        with open(rules_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def check_metrics(self, metrics: Dict[str, Any]) -> List[Alert]:
        """检查指标并生成告警"""
        alerts = []
        
        for rule in self.alert_rules:
            metric_value = metrics.get(rule.metric_name)
            if metric_value is None:
                continue
            
            triggered = False
            if rule.operator == "gt" and metric_value > rule.threshold:
                triggered = True
            elif rule.operator == "lt" and metric_value < rule.threshold:
                triggered = True
            elif rule.operator == "eq" and metric_value == rule.threshold:
                triggered = True
            
            if triggered:
                alert = Alert(
                    alert_id=f"alert_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{rule.rule_id}",
                    rule_id=rule.rule_id,
                    metric_name=rule.metric_name,
                    metric_value=metric_value,
                    threshold=rule.threshold,
                    severity=rule.severity,
                    timestamp=datetime.now().isoformat(),
                    resolved=False,
                    resolution=None
                )
                alerts.append(alert)
                
                # 保存告警
                with open(self.alerts_file, "a", encoding="utf-8") as f:
                    f.write(json.dumps(asdict(alert), ensure_ascii=False) + "\n")
                
                # 执行动作
                self._execute_alert_action(rule, alert)
        
        return alerts
    
    def _execute_alert_action(self, rule: AlertRule, alert: Alert):
        """执行告警动作"""
        if rule.action == "pause":
            # 暂停系统（简化）
            print(f"ALERT: Pausing system due to {rule.metric_name}")
        elif rule.action == "throttle":
            # 限流（简化）
            print(f"ALERT: Throttling system due to {rule.metric_name}")
        elif rule.action == "shutdown":
            # 安全关闭（简化）
            print(f"ALERT: Shutting down system due to {rule.metric_name}")
        elif rule.action == "notify":
            # 通知（简化）
            print(f"ALERT: Notifying due to {rule.metric_name}")
    
    def create_incident(self, alert: Alert, description: str, runbook_ref: str) -> Incident:
        """创建故障事件"""
        incident = Incident(
            incident_id=f"incident_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            alert_id=alert.alert_id,
            severity=alert.severity,
            description=description,
            timestamp=datetime.now().isoformat(),
            resolved=False,
            resolution=None,
            runbook_ref=runbook_ref
        )
        
        # 保存故障事件
        with open(self.incidents_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(incident), ensure_ascii=False) + "\n")
        
        return incident
    
    def resolve_incident(self, incident_id: str, resolution: str):
        """解决故障事件"""
        # 读取所有故障事件
        incidents = []
        if os.path.exists(self.incidents_file):
            with open(self.incidents_file, "r", encoding="utf-8") as f:
                for line in f:
                    incidents.append(json.loads(line))
        
        # 更新故障事件
        for incident in incidents:
            if incident["incident_id"] == incident_id:
                incident["resolved"] = True
                incident["resolution"] = resolution
        
        # 重写文件
        with open(self.incidents_file, "w", encoding="utf-8") as f:
            for incident in incidents:
                f.write(json.dumps(incident, ensure_ascii=False) + "\n")


