# Phase 8 Operational Runbook

> 本文档定义 Phase 8 运维与 SRE 能力（Runbook）

## 1. Health Check Endpoints

### 1.1 基础健康检查

```bash
curl http://localhost:8000/health
```

返回：
```json
{
  "status": "healthy",
  "timestamp": "2024-01-01T00:00:00",
  "version": "1.0"
}
```

### 1.2 详细健康检查

```bash
curl http://localhost:8000/health/detailed
```

检查项：
- artifacts_dir
- config
- database
- redis

### 1.3 健康指标

```bash
curl http://localhost:8000/health/metrics
```

指标：
- success_rate
- failure_rate
- cost_spike
- abnormal_replay_length

---

## 2. 关键指标监控

### 2.1 监控指标

- **success_rate**: 成功率（阈值: < 0.90 触发告警）
- **failure_rate**: 失败率（阈值: > 0.10 触发告警）
- **cost_spike**: 成本突增（阈值: > 1.5x average 触发告警）
- **abnormal_replay_length**: 异常回放长度（阈值: > 1000 events 触发告警）

### 2.2 告警规则

告警规则定义在 `artifacts/monitoring/alert_rules.json`：

- **rule_001**: success_rate < 0.90 → critical → pause
- **rule_002**: failure_rate > 0.10 → warning → throttle
- **rule_003**: cost_spike > 1.5x → warning → throttle
- **rule_004**: abnormal_replay_length > 1000 → info → notify

---

## 3. 告警处理流程

### 3.1 告警触发

系统自动检查指标并触发告警，告警保存在 `artifacts/monitoring/alerts.jsonl`。

### 3.2 告警动作

- **pause**: 暂停系统（停止接受新任务）
- **throttle**: 限流（降低新任务接受速率）
- **shutdown**: 安全关闭（等待任务完成，保存状态）
- **notify**: 通知（记录日志）

---

## 4. Incident Runbook

### 4.1 故障事件创建

当告警触发时，系统自动创建故障事件，保存在 `artifacts/monitoring/incidents.jsonl`。

### 4.2 故障定位

所有故障可通过以下方式定位：

1. **查看告警**: `artifacts/monitoring/alerts.jsonl`
2. **查看故障事件**: `artifacts/monitoring/incidents.jsonl`
3. **查看 trace**: `artifacts/tenants/{tenant_id}/tasks/{task_id}/system_trace.json`
4. **查看健康检查**: `http://localhost:8000/health/detailed`

### 4.3 故障解决

运行以下命令解决故障：

```python
from runtime.platform.monitoring import MonitoringSystem

monitoring = MonitoringSystem()
monitoring.resolve_incident("incident_id", "resolution_description")
```

---

## 5. Graceful Degradation

### 5.1 降级模式

- **NORMAL**: 正常运行
- **PAUSE**: 暂停（停止接受新任务）
- **THROTTLE**: 限流（降低新任务接受速率）
- **SHUTDOWN**: 安全关闭

### 5.2 降级触发

降级由告警规则自动触发，或手动触发：

```python
from runtime.platform.graceful_degradation import GracefulDegradation

degradation = GracefulDegradation()
degradation.pause()  # 或 throttle(0.5) 或 safe_shutdown()
```

---

## 6. 常见故障处理

### 6.1 成功率下降

**症状**: success_rate < 0.90

**处理**:
1. 检查健康检查端点
2. 查看最近的故障事件
3. 检查 trace 中的失败原因
4. 根据 runbook 采取相应措施

### 6.2 成本突增

**症状**: cost_spike > 1.5x average

**处理**:
1. 检查最近的 cost ledger
2. 查看 cost_outcome.json 中的偏差
3. 检查是否有异常任务
4. 考虑限流或暂停

### 6.3 系统不可用

**症状**: 健康检查返回 unhealthy

**处理**:
1. 检查 Docker 容器状态: `docker-compose ps`
2. 查看容器日志: `docker-compose logs`
3. 检查配置文件: `configs/config_snapshot.json`
4. 考虑回滚: `./scripts/rollback.sh [version]`

---

## 7. 不允许"需要作者解释"的故障

所有故障必须可通过以下方式定位：

- ✅ 健康检查端点
- ✅ 告警和故障事件日志
- ✅ Trace 和决策记录
- ✅ Runbook 文档

如果故障无法通过以上方式定位，视为系统缺陷。

---

**状态**: ✅ **Phase 8 Operational Runbook 已定义**


