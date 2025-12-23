"""
Tool Failure Classifier: 工具失败分类器
为每次工具调用提供结构化的失败类型分类
"""
from enum import Enum
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict


class ToolFailureType(str, Enum):
    """工具失败类型分类"""
    TIMEOUT = "TIMEOUT"  # 执行超时
    PERMISSION_DENIED = "PERMISSION_DENIED"  # 权限被拒绝
    INVALID_INPUT = "INVALID_INPUT"  # 输入参数无效
    ENVIRONMENT_ERROR = "ENVIRONMENT_ERROR"  # 环境错误（容器、依赖等）
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"  # 资源耗尽（内存、磁盘等）
    NETWORK_ERROR = "NETWORK_ERROR"  # 网络错误
    NOT_FOUND = "NOT_FOUND"  # 资源不存在
    UNKNOWN = "UNKNOWN"  # 未知错误


@dataclass
class ToolInvocationResult:
    """
    工具调用结果（Learning 可消费格式）
    
    每次工具调用必须返回此结构，供 TraceStore 记录。
    """
    tool_name: str
    success: bool
    failure_type: Optional[ToolFailureType]
    latency_ms: float
    cost_estimate: float
    retry_count: int
    # 额外上下文
    error_message: Optional[str] = None
    input_hash: Optional[str] = None
    output_hash: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        result = asdict(self)
        if result["failure_type"]:
            result["failure_type"] = result["failure_type"].value
        return result


class ToolFailureClassifier:
    """
    工具失败分类器：基于错误信息和退出码分类失败类型
    """
    
    # 错误关键词 -> 失败类型映射
    ERROR_PATTERNS = {
        ToolFailureType.TIMEOUT: [
            "timeout", "timed out", "deadline exceeded", "TimeoutExpired"
        ],
        ToolFailureType.PERMISSION_DENIED: [
            "permission denied", "access denied", "unauthorized", "forbidden",
            "not allowed", "EACCES", "EPERM"
        ],
        ToolFailureType.INVALID_INPUT: [
            "invalid", "validation failed", "missing required", "bad request",
            "type error", "schema", "parameter"
        ],
        ToolFailureType.ENVIRONMENT_ERROR: [
            "container", "docker", "image", "environment", "not found",
            "no such file", "command not found", "ENOENT"
        ],
        ToolFailureType.RESOURCE_EXHAUSTED: [
            "memory", "disk full", "quota exceeded", "resource exhausted",
            "ENOMEM", "ENOSPC", "out of memory"
        ],
        ToolFailureType.NETWORK_ERROR: [
            "network", "connection refused", "unreachable", "dns",
            "ECONNREFUSED", "ENETUNREACH", "socket"
        ],
        ToolFailureType.NOT_FOUND: [
            "not found", "does not exist", "no such", "404"
        ]
    }
    
    def classify(
        self,
        success: bool,
        error_message: Optional[str] = None,
        exit_code: int = 0
    ) -> Optional[ToolFailureType]:
        """
        分类工具失败类型。
        
        Args:
            success: 是否成功
            error_message: 错误信息
            exit_code: 退出码
            
        Returns:
            ToolFailureType 或 None（如果成功）
        """
        if success:
            return None
        
        if not error_message:
            # 只有退出码，基于常见退出码分类
            return self._classify_by_exit_code(exit_code)
        
        # 基于错误信息分类
        error_lower = error_message.lower()
        
        for failure_type, patterns in self.ERROR_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in error_lower:
                    return failure_type
        
        # 未匹配到任何模式
        return ToolFailureType.UNKNOWN
    
    def _classify_by_exit_code(self, exit_code: int) -> ToolFailureType:
        """基于退出码分类"""
        # 常见 Unix 退出码
        EXIT_CODE_MAP = {
            -1: ToolFailureType.TIMEOUT,
            1: ToolFailureType.UNKNOWN,
            2: ToolFailureType.INVALID_INPUT,
            126: ToolFailureType.PERMISSION_DENIED,
            127: ToolFailureType.ENVIRONMENT_ERROR,
            128: ToolFailureType.UNKNOWN,
            137: ToolFailureType.RESOURCE_EXHAUSTED,  # SIGKILL (OOM)
            139: ToolFailureType.UNKNOWN,  # SIGSEGV
        }
        
        return EXIT_CODE_MAP.get(exit_code, ToolFailureType.UNKNOWN)
    
    def wrap_tool_result(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float,
        error_message: Optional[str] = None,
        exit_code: int = 0,
        retry_count: int = 0,
        cost_estimate: float = 0.0,
        input_hash: Optional[str] = None,
        output_hash: Optional[str] = None
    ) -> ToolInvocationResult:
        """
        将原始工具执行结果包装为 Learning 可消费的格式。
        
        Args:
            tool_name: 工具名称
            success: 是否成功
            latency_ms: 执行延迟（毫秒）
            error_message: 错误信息
            exit_code: 退出码
            retry_count: 重试次数
            cost_estimate: 成本估算
            input_hash: 输入哈希（用于去重）
            output_hash: 输出哈希（用于验证）
            
        Returns:
            ToolInvocationResult
        """
        failure_type = self.classify(success, error_message, exit_code)
        
        return ToolInvocationResult(
            tool_name=tool_name,
            success=success,
            failure_type=failure_type,
            latency_ms=latency_ms,
            cost_estimate=cost_estimate,
            retry_count=retry_count,
            error_message=error_message[:500] if error_message else None,
            input_hash=input_hash,
            output_hash=output_hash
        )



