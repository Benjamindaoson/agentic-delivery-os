"""
Orchestrator: 系统入口层
职责：
- 接收用户提交的 Delivery Spec
- 校验完整性
- 触发系统执行
"""
import uuid
from typing import Optional
from backend.schemas.delivery import DeliverySpec
from backend.schemas.task import TaskStatusResponse, TaskProgress
from runtime.state.state_manager import StateManager
from runtime.execution_graph.execution_engine import ExecutionEngine

class Orchestrator:
    def __init__(self):
        self.state_manager = StateManager()
        self.execution_engine = ExecutionEngine(self.state_manager)
    
    async def initialize(self):
        """初始化系统"""
        await self.state_manager.initialize()
        await self.execution_engine.initialize()
    
    async def create_task(self, spec: DeliverySpec) -> str:
        """创建任务并写入状态"""
        task_id = str(uuid.uuid4())
        await self.state_manager.create_task(task_id, spec.model_dump())
        await self.state_manager.update_task_state(
            task_id, 
            "IDLE",
            reason="Task created"
        )
        return task_id
    
    async def start_execution(self, task_id: str):
        """触发系统执行"""
        await self.state_manager.update_task_state(
            task_id, 
            "SPEC_READY",
            reason="Spec frozen, ready for execution"
        )
        # 启动执行引擎（同步执行，确保状态正确）
        await self.execution_engine.start_execution(task_id)
    
    async def get_task_status(self, task_id: str) -> Optional[TaskStatusResponse]:
        """获取任务状态"""
        state = await self.state_manager.get_task_state(task_id)
        if not state:
            return None
        return TaskStatusResponse(
            taskId=task_id,
            state=state.state.value,
            error=state.error,
            progress=TaskProgress(**state.progress) if state.progress else None
        )

