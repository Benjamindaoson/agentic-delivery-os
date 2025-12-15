# Phase 8 Commercial Delivery Specification

> 本文档定义 Phase 8 商业交付规格

## 1. Customer-facing Export Bundle

### 1.1 导出包内容

客户面向导出包包含：

- **execution_result.json**: 执行结果（状态、完成时间、成本）
- **replay_view.json**: Replay 视图（event-order replay）
- **cost_summary.json**: 成本汇总

### 1.2 不含内部策略细节

导出包**不包含**：
- governance_decisions 详细内容
- 内部决策逻辑
- 系统内部配置

### 1.3 导出方法

```python
from runtime.product.customer_export import CustomerExport

export = CustomerExport()
bundle_path = export.create_customer_bundle(task_id, tenant_id)
```

---

## 2. Audit Bundle（只读）

### 2.1 审计包内容

审计包包含：

- **trace.json**: 完整 trace
- **decisions.json**: 所有治理决策
- **trace_hash.txt**: Trace hash（可验证完整性）
- **evaluation_reference.json**: 评测引用（链接到 Phase 7 证据）

### 2.2 只读属性

审计包为只读，不可修改。

### 2.3 导出方法

```python
from runtime.product.customer_export import CustomerExport

export = CustomerExport()
audit_path = export.create_audit_bundle(task_id, tenant_id)
```

---

## 3. SLA / SLO 定义

### 3.1 Service Level Objectives (SLO)

- **Availability**: 99.9% uptime
- **Success Rate**: >= 95%
- **Response Time**: p95 < 5s
- **Cost Accuracy**: Forecast vs Actual delta < 10%

### 3.2 Service Level Agreements (SLA)

- **Uptime Guarantee**: 99.9%
- **Support Response Time**: < 4 hours
- **Incident Resolution Time**: < 24 hours

---

## 4. Versioned Release Notes

### 4.1 版本号格式

遵循语义化版本：`MAJOR.MINOR.PATCH`

- **MAJOR**: 不兼容的 API 变更
- **MINOR**: 向后兼容的功能新增
- **PATCH**: 向后兼容的问题修复

### 4.2 Release Notes 内容

每个版本包含：

- **Version**: 版本号
- **Release Date**: 发布日期
- **Changes**: 变更列表（结构化）
- **Breaking Changes**: 破坏性变更（如有）
- **Upgrade Guide**: 升级指南

---

## 5. 支持周期与升级策略

### 5.1 支持周期

- **Current Version**: 完全支持
- **Previous Major Version**: 安全补丁支持（6个月）
- **Older Versions**: 不提供支持

### 5.2 升级策略

- **Minor/Patch 升级**: 向后兼容，可直接升级
- **Major 升级**: 需要迁移指南，可能包含破坏性变更

---

## 6. 交付物清单

### 6.1 客户交付物

- Customer-facing Export Bundle
- SLA / SLO 定义文档
- Versioned Release Notes
- 用户文档

### 6.2 审计交付物

- Audit Bundle（只读）
- Trace 和决策记录
- Hash 验证文件
- Evaluation reference

---

**状态**: ✅ **Phase 8 Commercial Delivery Specification 已定义**


