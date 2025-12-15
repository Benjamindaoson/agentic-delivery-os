# 执行最小闭环流程说明

## 目标

实现一次空任务能从 IDLE 走到 COMPLETED 的最小闭环。

## 执行流程

```
1. 用户提交 Spec (Frontend)
   ↓
2. Backend API 接收 Spec
   ↓
3. Orchestrator.create_task()
   - 生成 task_id
   - 状态: IDLE
   ↓
4. Orchestrator.start_execution()
   - 状态: IDLE → SPEC_READY
   - 调用 ExecutionEngine.start_execution()
   ↓
5. ExecutionEngine.start_execution()
   - 状态: SPEC_READY → RUNNING
   - 获取任务上下文
   - 执行 ProductAgent.execute()
   ↓
6. ProductAgent.execute()
   - 创建 artifacts/rag_project/{task_id}/ 目录
   - 写入 delivery_manifest.json
   - 写入 README.md
   - 返回执行结果
   ↓
7. ExecutionEngine 更新上下文
   - 状态: RUNNING → COMPLETED
   - 更新 progress 信息
```

## 状态迁移

```
IDLE → SPEC_READY → RUNNING → COMPLETED
```

如果执行失败：
```
RUNNING → FAILED
```

## 产物输出

产物写入位置：`artifacts/rag_project/{task_id}/`

包含文件：
- `delivery_manifest.json`: 交付清单
- `README.md`: 说明文档

## 验证方法

1. 启动 Backend: `python backend/main.py`
2. 通过 API 提交空 Spec
3. 查询任务状态，应看到状态从 IDLE → SPEC_READY → RUNNING → COMPLETED
4. 检查 `artifacts/rag_project/{task_id}/` 目录，应包含产物文件


