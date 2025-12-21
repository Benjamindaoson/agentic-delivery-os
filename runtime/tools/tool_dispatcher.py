"""
Tool Dispatcher: 集中式工具调度入口
参数校验、权限边界、隔离执行、可审计
"""
from typing import Dict, Any, Optional, List
from enum import Enum
from datetime import datetime
import json
import os
import subprocess
import tempfile
import shutil

class ToolPermission(str, Enum):
    """工具权限级别"""
    READ_ONLY = "read_only"  # 只读
    WRITE_LOCAL = "write_local"  # 仅本地写入
    EXECUTE_SAFE = "execute_safe"  # 安全命令执行
    NETWORK_ACCESS = "network_access"  # 网络访问（受限）

class ToolResult:
    """工具执行结果"""
    def __init__(
        self,
        tool_name: str,
        success: bool,
        output: Any = None,
        error: Optional[str] = None,
        exit_code: int = 0,
        execution_time_ms: float = 0.0,
        validated: bool = True,
        degrade_triggered: bool = False,
        rollback_triggered: bool = False
    ):
        self.tool_name = tool_name
        self.success = success
        self.output = output
        self.error = error
        self.exit_code = exit_code
        self.execution_time_ms = execution_time_ms
        self.validated = validated
        self.degrade_triggered = degrade_triggered
        self.rollback_triggered = rollback_triggered
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "output_summary": str(self.output)[:200] if self.output else None,
            "error": self.error,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "validated": self.validated,
            "degrade_triggered": self.degrade_triggered,
            "rollback_triggered": self.rollback_triggered,
            "timestamp": self.timestamp
        }

class ToolDispatcher:
    """工具调度器：集中式工具调用入口"""
    
    def __init__(self, sandbox_dir: str = "runtime/tools/sandbox"):
        self.sandbox_dir = sandbox_dir
        os.makedirs(sandbox_dir, exist_ok=True)
        self.tool_registry: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """注册默认工具"""
        self.tool_registry = {
            "file_write": {
                "permission": ToolPermission.WRITE_LOCAL,
                "allowed_paths": ["artifacts/", "runtime/tools/sandbox/"],
                "image": "alpine:3.18",
                "schema": {
                    "type": "object",
                    "required": ["path", "content"],
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"}
                    },
                    "additionalProperties": False
                }
            },
            "file_read": {
                "permission": ToolPermission.READ_ONLY,
                "allowed_paths": ["artifacts/", "runtime/tools/sandbox/"],
                "image": "alpine:3.18",
                "schema": {
                    "type": "object",
                    "required": ["path"],
                    "properties": {
                        "path": {"type": "string"}
                    },
                    "additionalProperties": False
                }
            },
            "command_execute": {
                "permission": ToolPermission.EXECUTE_SAFE,
                "allowed_commands": ["mkdir", "cp", "mv", "ls", "cat", "echo"],
                "image": "alpine:3.18",
                "schema": {
                    "type": "object",
                    "required": ["command", "args"],
                    "properties": {
                        "command": {"type": "string"},
                        "args": {"type": "array", "items": {"type": "string"}}
                    },
                    "additionalProperties": False
                }
            }
        }
    
    async def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
        task_id: str
    ) -> ToolResult:
        """
        执行工具调用
        
        流程：
        1. 参数校验（schema）
        2. 权限检查
        3. 沙盒隔离执行
        4. 结果记录
        """
        import time
        start_time = time.time()
        
        # 1. 检查工具是否存在
        if tool_name not in self.tool_registry:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool {tool_name} not registered",
                validated=False
            )
        
        tool_def = self.tool_registry[tool_name]
        
        # 2. 参数校验
        validation_result = self._validate_params(params, tool_def.get("schema", {}))
        if not validation_result["valid"]:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Parameter validation failed: {validation_result['errors']}",
                validated=False
            )
        
        # 3. 权限检查
        permission_result = self._check_permission(tool_name, params, tool_def)
        if not permission_result["allowed"]:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=f"Permission denied: {permission_result['reason']}",
                validated=True
            )
        
        # 4. 沙盒隔离执行
        try:
            result = await self._execute_in_sandbox(tool_name, params, task_id, tool_def)
            execution_time = (time.time() - start_time) * 1000
            
            return ToolResult(
                tool_name=tool_name,
                success=result["success"],
                output=result.get("output"),
                error=result.get("error"),
                exit_code=result.get("exit_code", 0),
                execution_time_ms=execution_time,
                validated=True,
                degrade_triggered=result.get("degrade_triggered", False),
                rollback_triggered=result.get("rollback_triggered", False)
            )
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            return ToolResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                exit_code=1,
                execution_time_ms=execution_time,
                validated=True
            )
    
    def _validate_params(self, params: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
        """参数校验（简化版 JSON Schema）"""
        errors = []
        
        if "required" in schema:
            for field in schema["required"]:
                if field not in params:
                    errors.append(f"Missing required field: {field}")
        
        if "properties" in schema:
            for field, field_schema in schema["properties"].items():
                if field in params:
                    expected_type = field_schema.get("type")
                    if expected_type:
                        actual_type = type(params[field]).__name__
                        type_map = {
                            "string": "str",
                            "array": "list",
                            "object": "dict"
                        }
                        if expected_type in type_map and actual_type != type_map[expected_type]:
                            errors.append(f"Field {field}: expected {expected_type}, got {actual_type}")
        
        return {
            "valid": len(errors) == 0,
            "errors": errors
        }
    
    def _check_permission(
        self,
        tool_name: str,
        params: Dict[str, Any],
        tool_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """权限检查"""
        permission = tool_def.get("permission")
        
        # 文件路径检查
        if "path" in params:
            path = params["path"]
            allowed_paths = tool_def.get("allowed_paths", [])
            if allowed_paths:
                allowed = any(path.startswith(allowed) for allowed in allowed_paths)
                if not allowed:
                    return {
                        "allowed": False,
                        "reason": f"Path {path} not in allowed paths"
                    }
        
        # 命令白名单检查
        if "command" in params:
            command = params["command"]
            allowed_commands = tool_def.get("allowed_commands", [])
            if allowed_commands and command not in allowed_commands:
                return {
                    "allowed": False,
                    "reason": f"Command {command} not in allowed commands"
                }
        
        return {"allowed": True}
    
    async def _execute_in_sandbox(
        self,
        tool_name: str,
        params: Dict[str, Any],
        task_id: str,
        tool_def: Dict[str, Any]
    ) -> Dict[str, Any]:
        """在沙盒中执行工具"""
        task_sandbox = os.path.join(self.sandbox_dir, task_id)
        os.makedirs(task_sandbox, exist_ok=True)
        # Prefer docker-based sandbox if image specified and docker available
        image = tool_def.get("image")
        docker_path = shutil.which("docker")
        if image and docker_path:
            # Map params to a command inside the container based on tool_name
            container_cmd = None
            if tool_name == "file_write":
                # write content to file inside mounted workspace
                dest = os.path.basename(params["path"])
                content = params["content"].replace("'", "'\"'\"'")
                # use sh -c to write content
                container_cmd = ["sh", "-c", f"cat > /workspace/{dest} <<'EOF'\n{content}\nEOF"]
            elif tool_name == "file_read":
                dest = os.path.basename(params["path"])
                container_cmd = ["sh", "-c", f"cat /workspace/{dest} || exit 3"]
            elif tool_name == "command_execute":
                command = params["command"]
                args = params.get("args", [])
                # validate allowed commands
                allowed = tool_def.get("allowed_commands", [])
                if allowed and command not in allowed:
                    return {"success": False, "error": f"Command {command} not allowed", "exit_code": -2}
                container_cmd = [command] + args
            else:
                return {"success": False, "error": f"Unknown tool: {tool_name}"}

            # Prepare docker run args
            cpu_limit = str(tool_def.get("cpu_limit", 0.5))
            mem_limit = str(tool_def.get("memory_limit", "128m"))
            timeout_sec = int(tool_def.get("timeout_sec", 10))

            # run docker with mounted workspace
            host_workspace = task_sandbox
            try:
                start = datetime.now()
                # security: enforce non-root user inside container
                docker_cmd = [
                    docker_path, "run", "--rm",
                    "--network=none",
                    "--cpus", cpu_limit,
                    "--memory", mem_limit,
                    "--read-only",
                    "--user", "1000:1000",
                    "-v", f"{host_workspace}:/workspace:rw",
                ]
                # optional seccomp profile
                seccomp_profile = os.environ.get("SANDBOX_SECCOMP_PROFILE")
                if seccomp_profile and os.path.exists(seccomp_profile):
                    docker_cmd += ["--security-opt", f"seccomp={seccomp_profile}"]
                # image allowlist enforcement (optional)
                allowed_images_env = os.environ.get("SANDBOX_ALLOWED_IMAGES")
                if allowed_images_env:
                    allowed_images = [i.strip() for i in allowed_images_env.split(",") if i.strip()]
                    if image not in allowed_images:
                        return {"success": False, "error": f"Image {image} not allowed by SANDBOX_ALLOWED_IMAGES", "exit_code": -3}
                # optional image signature enforcement
                require_signed = os.environ.get("SANDBOX_REQUIRE_SIGNED_IMAGES", "false").lower() == "true"
                if require_signed:
                    try:
                        from runtime.tools.image_signing import verify_image_signed
                        if not verify_image_signed(image):
                            return {"success": False, "error": f"Image {image} not signed", "exit_code": -4}
                    except Exception:
                        return {"success": False, "error": "Image signing check failed", "exit_code": -5}

                docker_cmd.append(image)
                docker_cmd += (container_cmd if isinstance(container_cmd, list) else [container_cmd])
                proc = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout_sec)
                duration_ms = (datetime.now() - start).total_seconds() * 1000
                stdout = proc.stdout
                stderr = proc.stderr
                exit_code = proc.returncode
                success = exit_code == 0
                # Trim large outputs for trace
                out_summary = stdout[:2000] if stdout else ""
                err_summary = stderr[:2000] if stderr else ""
                return {
                    "success": success,
                    "output": out_summary,
                    "error": err_summary if not success else None,
                    "exit_code": exit_code,
                    "execution_time_ms": duration_ms
                }
            except subprocess.TimeoutExpired:
                # Try to best-effort kill container (best-effort)
                return {"success": False, "error": "Command timeout", "exit_code": -1}
            except Exception as e:
                return {"success": False, "error": str(e), "exit_code": -1}

        # Fallback to previous local behavior
        if tool_name == "file_write":
            path = params["path"]
            content = params["content"]
            # 确保路径在允许范围内
            full_path = os.path.join(task_sandbox, os.path.basename(path))
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "output": f"File written: {full_path}"}
        
        elif tool_name == "file_read":
            path = params["path"]
            full_path = os.path.join(task_sandbox, os.path.basename(path))
            if os.path.exists(full_path):
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return {"success": True, "output": content}
            else:
                return {"success": False, "error": f"File not found: {full_path}"}
        
        elif tool_name == "command_execute":
            command = params["command"]
            args = params.get("args", [])
            # 在沙盒目录中执行
            try:
                result = subprocess.run(
                    [command] + args,
                    cwd=task_sandbox,
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                return {
                    "success": result.returncode == 0,
                    "output": result.stdout,
                    "error": result.stderr if result.returncode != 0 else None,
                    "exit_code": result.returncode
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "Command timeout", "exit_code": -1}
            except Exception as e:
                return {"success": False, "error": str(e), "exit_code": -1}
        
        return {"success": False, "error": f"Unknown tool: {tool_name}"}
























