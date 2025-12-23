"""
Prompt Variant Tracking: 生成层 Prompt 变体追踪
记录每次生成的 Prompt 配置，供 Learning 评估（不做 A/B 自动切换）
"""
import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict, field


@dataclass
class PromptComposerOutput:
    """
    PromptComposer 输出：每次生成必须返回此结构。
    """
    prompt_template_id: str  # Prompt 模板 ID
    prompt_version: str  # 模板版本
    context_size: int  # 上下文大小（tokens）
    tool_context_included: bool  # 是否包含工具上下文
    system_prompt_hash: str = ""  # 系统 prompt 哈希
    user_prompt_hash: str = ""  # 用户 prompt 哈希
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GenerationResult:
    """
    生成结果（带归因信息）。
    """
    prompt_template_id: str
    prompt_version: str
    token_count: int  # 总 token 数
    input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0.0
    cost_estimate: float = 0.0
    success: bool = True
    error_message: Optional[str] = None
    output_hash: str = ""  # 输出哈希（用于去重）
    model_name: str = ""
    timestamp: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PromptStats:
    """Prompt 模板统计"""
    prompt_template_id: str
    prompt_version: str
    total_invocations: int = 0
    success_count: int = 0
    failure_count: int = 0
    success_rate: float = 0.0
    avg_token_count: float = 0.0
    avg_latency_ms: float = 0.0
    total_cost: float = 0.0
    avg_cost: float = 0.0
    last_updated: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PromptVariantTracker:
    """
    Prompt 变体追踪器：记录和统计 Prompt 使用情况。
    
    注意：此模块仅记录，不做 Prompt 自动切换（留给 L5）。
    """
    
    def __init__(
        self,
        stats_path: str = "artifacts/prompt_stats.json"
    ):
        """
        初始化追踪器。
        
        Args:
            stats_path: 统计文件路径
        """
        self.stats_path = stats_path
        self._stats: Dict[str, PromptStats] = {}
        self._results_buffer: List[GenerationResult] = []
        
        # 加载统计
        self._load_stats()
    
    def compose_output(
        self,
        template_id: str,
        version: str,
        context_size: int,
        tool_context_included: bool,
        system_prompt: str = "",
        user_prompt: str = "",
        metadata: Optional[Dict[str, Any]] = None
    ) -> PromptComposerOutput:
        """
        创建 PromptComposer 输出。
        
        Args:
            template_id: 模板 ID
            version: 版本
            context_size: 上下文大小
            tool_context_included: 是否包含工具上下文
            system_prompt: 系统 prompt
            user_prompt: 用户 prompt
            metadata: 元数据
            
        Returns:
            PromptComposerOutput
        """
        system_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:12] if system_prompt else ""
        user_hash = hashlib.sha256(user_prompt.encode()).hexdigest()[:12] if user_prompt else ""
        
        return PromptComposerOutput(
            prompt_template_id=template_id,
            prompt_version=version,
            context_size=context_size,
            tool_context_included=tool_context_included,
            system_prompt_hash=system_hash,
            user_prompt_hash=user_hash,
            metadata=metadata or {}
        )
    
    def record_generation(
        self,
        composer_output: PromptComposerOutput,
        token_count: int,
        latency_ms: float,
        success: bool,
        cost_estimate: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        model_name: str = "",
        error_message: Optional[str] = None,
        output_content: str = ""
    ) -> GenerationResult:
        """
        记录生成结果。
        
        Args:
            composer_output: PromptComposer 输出
            token_count: 总 token 数
            latency_ms: 延迟
            success: 是否成功
            cost_estimate: 成本估算
            input_tokens: 输入 token 数
            output_tokens: 输出 token 数
            model_name: 模型名称
            error_message: 错误信息
            output_content: 输出内容（用于计算哈希）
            
        Returns:
            GenerationResult
        """
        output_hash = hashlib.sha256(output_content.encode()).hexdigest()[:12] if output_content else ""
        
        result = GenerationResult(
            prompt_template_id=composer_output.prompt_template_id,
            prompt_version=composer_output.prompt_version,
            token_count=token_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            success=success,
            error_message=error_message[:500] if error_message else None,
            output_hash=output_hash,
            model_name=model_name,
            timestamp=datetime.now().isoformat()
        )
        
        # 更新统计
        self._update_stats(result)
        
        # 添加到缓冲区
        self._results_buffer.append(result)
        if len(self._results_buffer) > 10000:
            self._results_buffer = self._results_buffer[-10000:]
        
        return result
    
    def get_stats(self, template_id: str, version: str = "") -> Optional[PromptStats]:
        """
        获取 Prompt 统计。
        
        Args:
            template_id: 模板 ID
            version: 版本（可选）
            
        Returns:
            PromptStats
        """
        if version:
            key = f"{template_id}:{version}"
        else:
            # 返回该模板的最新版本统计
            matching = [k for k in self._stats.keys() if k.startswith(f"{template_id}:")]
            if not matching:
                return None
            key = sorted(matching)[-1]
        
        return self._stats.get(key)
    
    def get_all_stats(self) -> Dict[str, PromptStats]:
        """获取所有统计"""
        return self._stats.copy()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        获取生成层摘要（供 Learning 消费）。
        """
        templates = {}
        for key, stats in self._stats.items():
            templates[key] = {
                "success_rate": stats.success_rate,
                "avg_cost": stats.avg_cost,
                "failure_rate": 1.0 - stats.success_rate,
                "avg_latency_ms": stats.avg_latency_ms,
                "total_invocations": stats.total_invocations
            }
        
        return {
            "templates": templates,
            "generated_at": datetime.now().isoformat()
        }
    
    def _update_stats(self, result: GenerationResult) -> None:
        """更新统计"""
        key = f"{result.prompt_template_id}:{result.prompt_version}"
        
        if key not in self._stats:
            self._stats[key] = PromptStats(
                prompt_template_id=result.prompt_template_id,
                prompt_version=result.prompt_version
            )
        
        stats = self._stats[key]
        stats.total_invocations += 1
        
        if result.success:
            stats.success_count += 1
        else:
            stats.failure_count += 1
        
        # 更新成功率
        stats.success_rate = stats.success_count / stats.total_invocations
        
        # 更新平均值
        n = stats.total_invocations
        stats.avg_token_count = ((n - 1) * stats.avg_token_count + result.token_count) / n
        stats.avg_latency_ms = ((n - 1) * stats.avg_latency_ms + result.latency_ms) / n
        stats.total_cost += result.cost_estimate
        stats.avg_cost = stats.total_cost / n
        
        stats.last_updated = datetime.now().isoformat()
        
        # 持久化
        self._save_stats()
    
    def _load_stats(self) -> None:
        """加载统计"""
        if not os.path.exists(self.stats_path):
            return
        
        try:
            with open(self.stats_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            for key, stats_data in data.get("templates", {}).items():
                parts = key.split(":", 1)
                template_id = parts[0]
                version = parts[1] if len(parts) > 1 else "1.0"
                
                self._stats[key] = PromptStats(
                    prompt_template_id=template_id,
                    prompt_version=version,
                    total_invocations=stats_data.get("total_invocations", 0),
                    success_count=stats_data.get("success_count", 0),
                    failure_count=stats_data.get("failure_count", 0),
                    success_rate=stats_data.get("success_rate", 0.0),
                    avg_token_count=stats_data.get("avg_token_count", 0.0),
                    avg_latency_ms=stats_data.get("avg_latency_ms", 0.0),
                    total_cost=stats_data.get("total_cost", 0.0),
                    avg_cost=stats_data.get("avg_cost", 0.0),
                    last_updated=stats_data.get("last_updated", "")
                )
        except (json.JSONDecodeError, IOError):
            pass
    
    def _save_stats(self) -> None:
        """保存统计"""
        os.makedirs(os.path.dirname(self.stats_path), exist_ok=True)
        
        data = {
            "templates": {
                f"{stats.prompt_template_id}:{stats.prompt_version}": stats.to_dict()
                for stats in self._stats.values()
            },
            "generated_at": datetime.now().isoformat()
        }
        
        with open(self.stats_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


# 全局实例
_prompt_tracker: Optional[PromptVariantTracker] = None


def get_prompt_tracker() -> PromptVariantTracker:
    """获取全局 Prompt 追踪器"""
    global _prompt_tracker
    if _prompt_tracker is None:
        _prompt_tracker = PromptVariantTracker()
    return _prompt_tracker



