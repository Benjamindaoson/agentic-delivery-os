# 项目结构说明

## 目录结构

```
agentic_delivery_os/
├── frontend/                 # 用户交互层（非技术用户）
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   │   ├── Home.tsx
│   │   │   ├── DeliveryWizard.tsx  # Wizard流程
│   │   │   └── TaskStatus.tsx       # 任务状态展示
│   │   ├── components/      # 通用组件
│   │   │   ├── WizardStep.tsx
│   │   │   └── ReviewStep.tsx
│   │   ├── flows/           # Wizard / 交付流程定义
│   │   │   └── deliveryFlow.ts
│   │   └── types/           # TypeScript类型定义
│   │       └── index.ts
│   ├── package.json
│   └── vite.config.ts
│
├── backend/                  # API + 调度入口
│   ├── api/                 # API路由
│   │   ├── delivery.py      # 交付Spec提交接口
│   │   └── task.py          # 任务状态查询接口
│   ├── orchestration/       # 调度层
│   │   └── orchestrator.py  # 系统入口：接收Spec、触发执行
│   ├── schemas/             # 数据模型
│   │   ├── delivery.py      # DeliverySpec定义
│   │   └── task.py          # TaskStatus定义
│   ├── main.py              # FastAPI应用入口
│   └── requirements.txt
│
├── runtime/                  # 多智能体执行与状态系统
│   ├── agents/              # 职责型Agent（非随意）
│   │   ├── base_agent.py    # Agent基类
│   │   ├── product_agent.py      # Product: 是否启动？需求是否清晰？
│   │   ├── orchestrator_agent.py # Orchestrator: 执行顺序与条件
│   │   ├── data_agent.py         # Data: 数据是否可用
│   │   ├── execution_agent.py     # Execution: 构建工程
│   │   ├── evaluation_agent.py    # Evaluation: 是否完成
│   │   └── cost_agent.py          # Cost: 是否继续
│   ├── execution_graph/      # 条件DAG / 执行图
│   │   └── execution_engine.py    # 执行引擎：DAG调度
│   ├── state/                # 状态定义与持久化
│   │   └── state_manager.py       # 状态管理：IDLE/SPEC_READY/RUNNING/FAILED/COMPLETED
│   └── tools/                # 工具封装与校验
│       ├── base_tool.py
│       ├── file_tool.py      # 文件操作工具
│       └── codegen_tool.py   # 代码生成工具
│
├── artifacts/                # 交付产物
│   └── rag_project/          # 当前阶段的交付目标
│
├── configs/
│   └── system.yaml           # 系统级配置（预算/阈值）
│
└── docs/
    └── system_contract.md    # 系统行为说明（给人看）
```

## 技术栈

- **Frontend**: React + TypeScript + Vite
- **Backend**: Python + FastAPI
- **Runtime**: Python
- **State**: SQLite + 文件系统

## 系统流程

1. 用户通过 Frontend Wizard 输入需求
2. 经过 Review 页面确认后，Spec 冻结
3. Backend 接收 Spec，创建任务
4. Runtime 执行引擎按 DAG 顺序调用各个 Agent
5. 状态通过 StateManager 持久化
6. 最终交付产物生成到 artifacts/rag_project/

## 注意事项

- 本项目为最小系统骨架，不包含具体业务逻辑实现
- 所有 Agent 的 execute 方法均为骨架实现，需要后续填充业务逻辑
- 执行图目前为顺序执行，需要后续实现完整的 DAG 逻辑
























