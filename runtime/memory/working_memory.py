"""
Working Memory: 跨-Run 工作记忆
记录成功/失败模式，供 Learning 在训练阶段读取
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field
from collections import defaultdict


@dataclass
class PatternSignature:
    """
    模式签名：唯一标识一种执行模式
    """
    tool_sequence_hash: str  # 工具调用序列的哈希
    planner_choice: str  # 计划选择（normal / degraded / minimal）
    retrieval_strategy_id: str  # 检索策略 ID
    evidence_count: int = 0  # 使用的证据数量
    generation_template_id: str = ""  # 生成模板 ID
    
    def to_hash(self) -> str:
        """生成模式签名的唯一哈希"""
        content = json.dumps(asdict(self), sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PatternEntry:
    """
    模式记录条目
    """
    pattern_hash: str
    signature: PatternSignature
    outcome: str  # "success" | "failure" | "degraded"
    success_count: int = 0
    failure_count: int = 0
    total_count: int = 0
    last_seen: str = ""
    first_seen: str = ""
    avg_cost: float = 0.0
    avg_latency_ms: float = 0.0
    decay_weight: float = 1.0  # 衰减权重（越新越高）
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        result["signature"] = self.signature.to_dict()
        return result


class WorkingMemory:
    """
    跨-Run 工作记忆。
    
    功能：
    - record(pattern_signature, outcome): 记录执行模式和结果
    - decay(old_entries): 衰减旧条目
    - get_top_k_success_patterns(k): 获取成功率最高的 K 个模式
    
    存储：artifacts/working_memory.json
    """
    
    def __init__(
        self,
        storage_path: str = "artifacts/working_memory.json",
        max_patterns: int = 1000,
        decay_factor: float = 0.95
    ):
        """
        初始化工作记忆。
        
        Args:
            storage_path: 存储路径
            max_patterns: 最大模式数量
            decay_factor: 每次 decay 的衰减因子
        """
        self.storage_path = storage_path
        self.max_patterns = max_patterns
        self.decay_factor = decay_factor
        self._patterns: Dict[str, PatternEntry] = {}
        
        # 加载现有记忆
        self._load()
    
    def record(
        self,
        signature: PatternSignature,
        outcome: str,
        cost: float = 0.0,
        latency_ms: float = 0.0
    ) -> None:
        """
        记录执行模式和结果。
        
        Args:
            signature: 模式签名
            outcome: 结果（"success" | "failure" | "degraded"）
            cost: 成本
            latency_ms: 延迟
        """
        pattern_hash = signature.to_hash()
        now = datetime.now().isoformat()
        
        if pattern_hash not in self._patterns:
            # 新模式
            self._patterns[pattern_hash] = PatternEntry(
                pattern_hash=pattern_hash,
                signature=signature,
                outcome=outcome,
                success_count=1 if outcome == "success" else 0,
                failure_count=1 if outcome == "failure" else 0,
                total_count=1,
                first_seen=now,
                last_seen=now,
                avg_cost=cost,
                avg_latency_ms=latency_ms,
                decay_weight=1.0
            )
        else:
            # 更新现有模式
            entry = self._patterns[pattern_hash]
            entry.total_count += 1
            
            if outcome == "success":
                entry.success_count += 1
            elif outcome == "failure":
                entry.failure_count += 1
            
            entry.last_seen = now
            entry.outcome = outcome  # 更新为最新结果
            entry.decay_weight = 1.0  # 重置衰减权重
            
            # 更新平均成本和延迟（移动平均）
            n = entry.total_count
            entry.avg_cost = ((n - 1) * entry.avg_cost + cost) / n
            entry.avg_latency_ms = ((n - 1) * entry.avg_latency_ms + latency_ms) / n
        
        # 限制模式数量
        self._enforce_limit()
        
        # 持久化
        self._save()
    
    def decay(self, threshold: float = 0.1) -> int:
        """
        衰减旧条目。
        
        Args:
            threshold: 衰减阈值（低于此值的条目将被删除）
            
        Returns:
            int: 被删除的条目数
        """
        to_remove = []
        
        for pattern_hash, entry in self._patterns.items():
            entry.decay_weight *= self.decay_factor
            if entry.decay_weight < threshold:
                to_remove.append(pattern_hash)
        
        for pattern_hash in to_remove:
            del self._patterns[pattern_hash]
        
        self._save()
        return len(to_remove)
    
    def get_top_k_success_patterns(self, k: int = 10) -> List[PatternEntry]:
        """
        获取成功率最高的 K 个模式。
        
        Args:
            k: 返回数量
            
        Returns:
            List[PatternEntry]: 排序后的模式列表
        """
        patterns = list(self._patterns.values())
        
        # 按成功率 * 衰减权重排序
        def score(entry: PatternEntry) -> float:
            if entry.total_count == 0:
                return 0.0
            success_rate = entry.success_count / entry.total_count
            return success_rate * entry.decay_weight
        
        patterns.sort(key=score, reverse=True)
        return patterns[:k]
    
    def get_pattern(self, pattern_hash: str) -> Optional[PatternEntry]:
        """获取特定模式"""
        return self._patterns.get(pattern_hash)
    
    def get_all_patterns(self) -> List[PatternEntry]:
        """获取所有模式"""
        return list(self._patterns.values())
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取记忆摘要（供 Learning 消费）。
        """
        total_patterns = len(self._patterns)
        total_success = sum(e.success_count for e in self._patterns.values())
        total_failure = sum(e.failure_count for e in self._patterns.values())
        total_runs = sum(e.total_count for e in self._patterns.values())
        
        # 按计划类型统计
        by_planner = defaultdict(lambda: {"success": 0, "failure": 0, "total": 0})
        for entry in self._patterns.values():
            choice = entry.signature.planner_choice
            by_planner[choice]["success"] += entry.success_count
            by_planner[choice]["failure"] += entry.failure_count
            by_planner[choice]["total"] += entry.total_count
        
        return {
            "total_patterns": total_patterns,
            "total_runs": total_runs,
            "total_success": total_success,
            "total_failure": total_failure,
            "success_rate": total_success / total_runs if total_runs > 0 else 0.0,
            "by_planner_choice": dict(by_planner),
            "top_success_patterns": [
                e.to_dict() for e in self.get_top_k_success_patterns(5)
            ],
            "generated_at": datetime.now().isoformat()
        }
    
    def build_pattern_signature_from_run(
        self,
        tool_sequence: List[str],
        planner_choice: str,
        retrieval_strategy_id: str = "default",
        evidence_count: int = 0,
        generation_template_id: str = ""
    ) -> PatternSignature:
        """
        从 Run 信息构建模式签名。
        
        Args:
            tool_sequence: 工具调用序列
            planner_choice: 计划选择
            retrieval_strategy_id: 检索策略 ID
            evidence_count: 证据数量
            generation_template_id: 生成模板 ID
            
        Returns:
            PatternSignature
        """
        # 计算工具序列哈希
        tool_str = "|".join(tool_sequence)
        tool_hash = hashlib.sha256(tool_str.encode()).hexdigest()[:12]
        
        return PatternSignature(
            tool_sequence_hash=tool_hash,
            planner_choice=planner_choice,
            retrieval_strategy_id=retrieval_strategy_id,
            evidence_count=evidence_count,
            generation_template_id=generation_template_id
        )
    
    def _enforce_limit(self) -> None:
        """限制模式数量"""
        if len(self._patterns) <= self.max_patterns:
            return
        
        # 按衰减权重排序，删除最低的
        patterns = sorted(
            self._patterns.items(),
            key=lambda x: x[1].decay_weight
        )
        
        to_remove = len(patterns) - self.max_patterns
        for pattern_hash, _ in patterns[:to_remove]:
            del self._patterns[pattern_hash]
    
    def _load(self) -> None:
        """从文件加载"""
        if not os.path.exists(self.storage_path):
            return
        
        try:
            with open(self.storage_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for pattern_data in data.get("patterns", []):
                sig_data = pattern_data.get("signature", {})
                signature = PatternSignature(
                    tool_sequence_hash=sig_data.get("tool_sequence_hash", ""),
                    planner_choice=sig_data.get("planner_choice", ""),
                    retrieval_strategy_id=sig_data.get("retrieval_strategy_id", ""),
                    evidence_count=sig_data.get("evidence_count", 0),
                    generation_template_id=sig_data.get("generation_template_id", "")
                )
                
                entry = PatternEntry(
                    pattern_hash=pattern_data.get("pattern_hash", signature.to_hash()),
                    signature=signature,
                    outcome=pattern_data.get("outcome", "unknown"),
                    success_count=pattern_data.get("success_count", 0),
                    failure_count=pattern_data.get("failure_count", 0),
                    total_count=pattern_data.get("total_count", 0),
                    last_seen=pattern_data.get("last_seen", ""),
                    first_seen=pattern_data.get("first_seen", ""),
                    avg_cost=pattern_data.get("avg_cost", 0.0),
                    avg_latency_ms=pattern_data.get("avg_latency_ms", 0.0),
                    decay_weight=pattern_data.get("decay_weight", 1.0)
                )
                
                self._patterns[entry.pattern_hash] = entry
        except (json.JSONDecodeError, IOError):
            pass
    
    def _save(self) -> None:
        """保存到文件"""
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        
        data = {
            "patterns": [e.to_dict() for e in self._patterns.values()],
            "summary": {
                "total_patterns": len(self._patterns),
                "total_runs": sum(e.total_count for e in self._patterns.values())
            },
            "generated_at": datetime.now().isoformat()
        }
        
        with open(self.storage_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全局实例
_working_memory: Optional[WorkingMemory] = None


def get_working_memory() -> WorkingMemory:
    """获取全局工作记忆"""
    global _working_memory
    if _working_memory is None:
        _working_memory = WorkingMemory()
    return _working_memory



