# Phase 8 Tenant & Billing Specification

> 本文档定义 Phase 8 多租户与计费规格

## 1. Multi-Tenant & Access Control

### 1.1 Tenant 隔离

- **逻辑隔离**: 每个 tenant 的数据存储在独立目录
- **物理隔离**: 通过文件系统路径隔离（`artifacts/tenants/{tenant_id}/`）
- **API 隔离**: 所有 API 请求必须包含 tenant_id，系统自动验证隔离

### 1.2 Tenant 生命周期管理

- **创建**: 通过 `TenantManager.create_tenant()` 创建
- **删除**: 保留数据，标记为已删除（不可物理删除，用于审计）
- **更新**: 仅允许更新配额和元数据

### 1.3 API Key / Token 机制

- 每个 tenant 拥有唯一的 API key
- API key 以 hash 形式存储（不可逆）
- 所有 API 请求必须包含有效的 API key

### 1.4 Rate Limit / Quota

- **Rate Limit**: 按 tenant 限制请求速率（requests per minute）
- **Quota**: 按 tenant 限制资源使用量：
  - task_count
  - token_usage
  - tool_calls

### 1.5 权限模型

- **Owner**: 完全控制权限
- **Operator**: 可执行任务，不可修改配置
- **Viewer**: 只读权限

---

## 2. Usage Metering & Billing Foundation

### 2.1 确定性计量体系

所有计量数据来源于系统证据（trace / metric），不允许人工修正。

### 2.2 计量维度

- **task_count**: 任务数量
- **token_usage**: Token 使用量
- **tool_calls**: 工具调用次数
- **actual_cost**: 实际成本
- **forecast_cost**: 预测成本

### 2.3 Cost Ledger

- 按 tenant / task 记录成本
- 每个条目包含：
  - entry_id
  - tenant_id
  - task_id
  - timestamp
  - cost_type (actual / forecast)
  - amount
  - currency
  - evidence_ref
  - hash

### 2.4 Forecast vs Actual 对账

- 自动计算偏差（delta）
- 偏差来源必须可定位（trace / metric reference）
- 对账记录包含 reconciliation_hash

---

## 3. 访问审计日志

### 3.1 审计日志要求

- 所有访问写入审计日志
- 审计日志不可被 tenant 修改
- 审计日志按日期分文件存储

### 3.2 审计日志内容

- log_id
- tenant_id
- user_id
- api_key (已脱敏)
- endpoint
- method
- timestamp
- status_code
- response_time_ms

---

## 4. 计费数据来源

明确声明：

> **计费数据来源于系统证据（trace / metric），不允许人工修正账目。**

所有计费数据：
- 可追溯（evidence_ref）
- 可审计（hash）
- 可复现（基于 trace）

---

**状态**: ✅ **Phase 8 Tenant & Billing Specification 已定义**


