from fastapi import APIRouter, HTTPException
from backend.schemas.delivery import DeliverySpec, DeliverySpecResponse
from backend.orchestration import orchestrator

router = APIRouter()

@router.post("/submit", response_model=DeliverySpecResponse)
async def submit_delivery_spec(spec: DeliverySpec):
    """
    接收用户提交的 Delivery Spec
    校验完整性
    触发系统执行
    """
    # 校验Spec完整性
    if not _validate_spec(spec):
        raise HTTPException(status_code=400, detail="Spec不完整")
    
    # 创建任务
    task_id = await orchestrator.create_task(spec)
    
    # 启动执行（异步，不阻塞响应）
    import asyncio
    asyncio.create_task(orchestrator.start_execution(task_id))
    
    return DeliverySpecResponse(taskId=task_id, status="accepted")

def _validate_spec(spec: DeliverySpec) -> bool:
    """
    校验Spec是否满足最小字段集要求
    最小闭环版本：允许空任务通过，所有字段均为可选
    """
    # TODO: 实现完整校验逻辑（字段含义、顺序、校验规则）
    # 当前版本：允许空任务，确保最小闭环能执行
    return True

