# 系统行为说明（给人看）

## 系统概述

Agentic AI Delivery OS 是一套多智能体 AI 工程交付系统，用于将非技术用户的需求自动交付为可运行的 RAG 工程骨架。

## 系统流程

1. **用户输入**：通过 Wizard 流程输入需求
2. **Spec 冻结**：经过 Review 页面确认后冻结规格
3. **系统执行**：多智能体按 DAG 顺序执行
4. **交付产物**：生成可运行的 RAG 工程骨架

## 系统状态

- **IDLE**: 初始状态
- **SPEC_READY**: 规格已冻结，准备执行
- **RUNNING**: 执行中
- **FAILED**: 执行失败
- **COMPLETED**: 执行完成

## Agent 职责

- **Product**: 需求澄清、Spec 验证
- **Orchestrator**: 执行顺序控制
- **Data**: 数据接入与验证
- **Execution**: 工程构建
- **Evaluation**: 质量评测
- **Cost**: 成本监控

## 失败处理

系统失败时会：
1. 记录失败原因
2. 更新任务状态为 FAILED
3. 在前端展示错误信息
4. 提供修复建议




