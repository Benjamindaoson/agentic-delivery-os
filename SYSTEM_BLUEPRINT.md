------

# Agentic AI Delivery OS — Engineering Blueprint (Phase 1)

## 目标（Phase 1 唯一目标）

> 构建一套**多智能体 AI 工程交付系统的最小可运行骨架**，
>  支持：
>  **非技术用户 → 需求输入 → 系统自动交付一个 RAG 工程骨架**

本阶段不追求性能、不追求完整功能，只追求**系统闭环跑通一次**。

------

## 一、系统顶层目录结构（必须严格遵守）

```
agentic_delivery_os/
├── frontend/                 # 用户交互层（非技术用户）
│   ├── pages/
│   ├── components/
│   └── flows/                # Wizard / 交付流程定义
│
├── backend/                  # API + 调度入口
│   ├── api/
│   ├── orchestration/
│   └── schemas/
│
├── runtime/                  # 多智能体执行与状态系统
│   ├── agents/               # 职责型 Agent（非随意）
│   ├── execution_graph/      # 条件 DAG / 执行图
│   ├── state/                # 状态定义与持久化
│   └── tools/                # 工具封装与校验
│
├── artifacts/                # 交付产物
│   └── rag_project/          # 当前阶段的交付目标
│
├── configs/
│   └── system.yaml           # 系统级配置（预算 / 阈值）
│
└── docs/
    └── system_contract.md    # 系统行为说明（给人看）
```

**禁止：**

- 把 Agent 写在 frontend
- 把执行逻辑写成脚本
- 把系统压成一个 `main.py`

------

## 二、系统模块职责说明（不是 Agent 名字，是系统责任）

### 1️⃣ Frontend（用户侧）

**职责：**

- 为不懂 AI 的用户提供唯一入口
- 只允许通过“引导式流程”创建任务

**必须具备：**

- Wizard 形式的任务创建流程（4–6 步）
- Review 页面（冻结前确认）
- 任务状态展示（运行 / 失败 / 完成）

**禁止：**

- 让用户配置向量库、embedding、chunk size 等技术参数

------

### 2️⃣ Backend（系统入口）

**职责：**

- 接收用户提交的 Delivery Spec
- 校验完整性
- 触发系统执行

**只做三件事：**

1. 接收请求
2. 写入状态
3. 调用 runtime

------

### 3️⃣ Runtime（系统核心）

这是**整个项目的本体**。

#### Runtime 由四个子系统组成：

------

#### A. Agents（职责型，不是人格）

必须包含以下 6 类（名字可变，职责不可少）：

| Agent 职责   | 系统责任               |
| ------------ | ---------------------- |
| Product      | 是否启动？需求是否清晰 |
| Orchestrator | 执行顺序与条件         |
| Data         | 数据是否可用           |
| Execution    | 构建工程               |
| Evaluation   | 是否完成               |
| Cost         | 是否继续               |

**注意：**

- Agent ≠ 独立进程
- Agent = 有明确输入 / 输出 / 约束的职责模块

------

#### B. Execution Graph（执行图）

**形式：**

- 条件 DAG
- 明确起点、终点、失败路径

**必须支持：**

- 按条件跳过节点
- 失败回退
- 成本中断

------

#### C. State System（状态治理）

**至少包含：**

```
IDLE
SPEC_READY
RUNNING
FAILED
COMPLETED
```

**要求：**

- 所有 Agent 必须通过 state 读写交互
- 不允许通过“上下文记忆”传递关键信息

------

#### D. Tools（工具层）

**职责：**

- 封装文件操作、代码生成、命令执行
- 校验参数
- 在沙盒环境中运行

------

## 四、Artifacts（交付产物定义）

Phase 1 的唯一交付物：

```
artifacts/rag_project/
├── backend/
├── ingestion/
├── retrieval/
├── generation/
├── docker-compose.yml
└── README.md
```

这不是最终 RAG，而是**一个完整、可继续开发的工程骨架**。