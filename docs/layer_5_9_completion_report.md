# Layer 5-9 Learning 闭环工程报告

## 概述

本次实现将 Layer 5-9（Tooling / Memory / Retrieval / Evidence / Generation）从"可运行模块"升级为"Learning 可消费的闭环系统"。

所有新增模块满足以下约束：
- ✅ 不新增用户 API / CLI / 前端
- ✅ 不破坏现有 ExecutionEngine / Planner / Learning v1 行为
- ✅ 所有新能力通过 TraceStore 或 Artifact 暴露为结构化信号
- ✅ 所有模块可独立删除，不影响主系统运行
- ✅ 所有输出为 JSON / dataclass / 明确 schema

---

## Layer 5: Tooling & Environment

### 目标
让系统知道"哪个工具为什么失败/成功"，并为 Learning 提供信号。

### 实现

| 文件 | 功能 |
|------|------|
| `runtime/tooling/tool_failure_classifier.py` | 工具失败分类器 |
| `runtime/tooling/tool_metrics.py` | 工具可靠性追踪 |

### 关键数据结构

```python
@dataclass
class ToolInvocationResult:
    tool_name: str
    success: bool
    failure_type: Optional[ToolFailureType]  # TIMEOUT / PERMISSION_DENIED / INVALID_INPUT / ENVIRONMENT_ERROR / UNKNOWN
    latency_ms: float
    cost_estimate: float
    retry_count: int
```

### Artifacts

- `artifacts/tool_stats.json`: 工具统计（success_rate, avg_latency, failure_type_distribution）

---

## Layer 6: Memory & State

### 目标
补齐跨-run Working Memory，防止系统重复犯错。

### 实现

| 文件 | 功能 |
|------|------|
| `runtime/memory/working_memory.py` | 跨-Run 工作记忆 |

### 关键数据结构

```python
@dataclass
class PatternSignature:
    tool_sequence_hash: str
    planner_choice: str
    retrieval_strategy_id: str
    evidence_count: int
    generation_template_id: str

@dataclass
class PatternEntry:
    pattern_hash: str
    signature: PatternSignature
    outcome: str  # "success" | "failure" | "degraded"
    success_count: int
    failure_count: int
    decay_weight: float
```

### 功能

- `record(pattern_signature, outcome)`: 记录执行模式和结果
- `decay(old_entries)`: 衰减旧条目
- `get_top_k_success_patterns(k)`: 获取成功率最高的 K 个模式

### Artifacts

- `artifacts/working_memory.json`: 模式记忆存储

---

## Layer 7: Retrieval & Knowledge

### 目标
让 Retrieval 变成策略对象，而不是写死逻辑。

### 实现

| 文件 | 功能 |
|------|------|
| `runtime/retrieval/retrieval_policy.py` | 检索策略版本化 + 归因 |

### 关键数据结构

```python
@dataclass
class RetrievalPolicy:
    policy_id: str
    chunking_strategy: ChunkingStrategy
    embedding_model: EmbeddingModel
    rerank_strategy: RerankStrategy
    top_k: int
    min_similarity: float

@dataclass
class RetrievalResult:
    policy_id: str
    num_docs: int
    evidence_used_count: int
    downstream_success: Optional[bool]
```

### 默认策略

| Policy ID | Chunking | Embedding | Rerank |
|-----------|----------|-----------|--------|
| `basic_v1` | fixed_size | openai_ada | none |
| `semantic_rerank_v1` | semantic | openai_3_small | cross_encoder |
| `hybrid_v1` | paragraph | bge_large | bm25_hybrid |

### Artifacts

- `artifacts/retrieval_policy_stats.json`: 策略成功率、贡献度统计

---

## Layer 8: Evidence & Validation

### 目标
补齐 Evidence Contribution Signal。

### 实现

| 文件 | 功能 |
|------|------|
| `runtime/rag_delivery/evidence_contribution.py` | 证据贡献追踪 |

### 关键数据结构

```python
@dataclass
class EvidencePack:
    evidence_id: str
    source_doc_id: str
    chunk_id: str
    relevance_score: float
    used_in_final_output: bool
    conflict_with: List[str]

@dataclass
class EvidenceUsageSummary:
    run_id: str
    total_evidence: int
    used_evidence: int
    conflicting_evidence: int
    usage_rate: float
    conflict_rate: float
```

### Artifacts

- `artifacts/evidence_stats.json`: 证据使用统计

---

## Layer 9: Generation

### 目标
让 Generation 可评估、可对比，但不引入 prompt chaos。

### 实现

| 文件 | 功能 |
|------|------|
| `runtime/llm/prompt_tracking.py` | Prompt 变体追踪 |

### 关键数据结构

```python
@dataclass
class PromptComposerOutput:
    prompt_template_id: str
    prompt_version: str
    context_size: int
    tool_context_included: bool
    system_prompt_hash: str
    user_prompt_hash: str

@dataclass
class GenerationResult:
    prompt_template_id: str
    token_count: int
    latency_ms: float
    cost_estimate: float
    success: bool
```

### Artifacts

- `artifacts/prompt_stats.json`: Prompt 模板统计（success_rate, avg_cost, failure_rate）

---

## 集成：Signal Collector

### 文件

`runtime/learning/signal_collector.py`

### 功能

在每次 Run 完成后，收集并记录完整因果链信号：

```
Tool → Retrieval → Evidence → Generation
```

### 关键数据结构

```python
@dataclass
class RunSignalSummary:
    run_id: str
    timestamp: str
    
    # Layer 5: Tooling
    tool_calls: int
    tool_success_rate: float
    tool_failure_types: Dict[str, int]
    
    # Layer 6: Memory
    pattern_hash: str
    pattern_is_new: bool
    pattern_historical_success_rate: float
    
    # Layer 7: Retrieval
    retrieval_policy_id: str
    retrieval_num_docs: int
    
    # Layer 8: Evidence
    evidence_total: int
    evidence_used: int
    evidence_usage_rate: float
    
    # Layer 9: Generation
    generation_template_id: str
    generation_token_count: int
    generation_cost: float
    
    # 最终结果
    run_success: bool
    total_cost: float
```

### Artifacts

- `artifacts/run_signals.json`: 所有 Run 的信号摘要

---

## 验收条件达成情况

### 1. 单次 Run 结束后，TraceStore 中能完整还原因果链

✅ **达成**

通过 `SignalCollector.collect_run_signals()` 收集：
- Tool 调用序列和失败类型
- Retrieval 策略和文档数
- Evidence 使用和冲突
- Generation 模板和成本

### 2. Learning v1 能从 TraceStore / artifacts 中读取信号

✅ **达成**

Learning 可消费的信号：
- `artifacts/tool_stats.json`: 工具失败模式
- `artifacts/retrieval_policy_stats.json`: 策略效果
- `artifacts/working_memory.json`: 成功模式
- `artifacts/run_signals.json`: 完整因果链

### 3. 删除新代码后系统仍可正常运行

✅ **达成**

所有新模块通过全局实例懒加载，不注入核心路径：
- `runtime/tooling/` - 独立
- `runtime/memory/` - 独立
- `runtime/retrieval/` - 独立
- `runtime/rag_delivery/evidence_contribution.py` - 独立
- `runtime/llm/prompt_tracking.py` - 独立

### 4. 所有新增 artifacts 均为 JSON，可 replay / diff

✅ **达成**

| Artifact | Schema | Replay | Diff |
|----------|--------|--------|------|
| `tool_stats.json` | ✅ | ✅ | ✅ |
| `working_memory.json` | ✅ | ✅ | ✅ |
| `retrieval_policy_stats.json` | ✅ | ✅ | ✅ |
| `evidence_stats.json` | ✅ | ✅ | ✅ |
| `prompt_stats.json` | ✅ | ✅ | ✅ |
| `run_signals.json` | ✅ | ✅ | ✅ |

---

## 测试覆盖

```
tests/test_layer_5_9_signals.py ......................... 17 passed

测试类:
- TestLayer5Tooling (3 tests)
- TestLayer6Memory (3 tests)
- TestLayer7Retrieval (2 tests)
- TestLayer8Evidence (2 tests)
- TestLayer9Generation (2 tests)
- TestFullCausalChain (2 tests)
- TestModulesCanBeRemoved (3 tests)
```

---

## 文件清单

### 新增文件

| 文件 | 行数 | 功能 |
|------|------|------|
| `runtime/tooling/__init__.py` | 5 | 模块初始化 |
| `runtime/tooling/tool_failure_classifier.py` | 145 | 工具失败分类 |
| `runtime/tooling/tool_metrics.py` | 210 | 工具指标收集 |
| `runtime/memory/__init__.py` | 5 | 模块初始化 |
| `runtime/memory/working_memory.py` | 295 | 跨-Run 工作记忆 |
| `runtime/retrieval/__init__.py` | 5 | 模块初始化 |
| `runtime/retrieval/retrieval_policy.py` | 310 | 检索策略版本化 |
| `runtime/rag_delivery/evidence_contribution.py` | 280 | 证据贡献追踪 |
| `runtime/llm/prompt_tracking.py` | 275 | Prompt 变体追踪 |
| `runtime/learning/signal_collector.py` | 260 | 信号收集器 |
| `tests/test_layer_5_9_signals.py` | 580 | 测试用例 |

**总计**: ~2,370 行新代码

---

## 使用示例

### 记录工具调用

```python
from runtime.tooling.tool_failure_classifier import ToolFailureClassifier
from runtime.tooling.tool_metrics import get_tool_metrics_collector

classifier = ToolFailureClassifier()
collector = get_tool_metrics_collector()

result = classifier.wrap_tool_result(
    tool_name="file_read",
    success=False,
    latency_ms=100.0,
    error_message="File not found",
    exit_code=1
)
collector.record(result)
```

### 记录到 Working Memory

```python
from runtime.memory.working_memory import get_working_memory

memory = get_working_memory()
signature = memory.build_pattern_signature_from_run(
    tool_sequence=["parse", "embed", "retrieve"],
    planner_choice="normal",
    retrieval_strategy_id="basic_v1"
)
memory.record(signature, outcome="success", cost=0.5)
```

### 收集完整 Run 信号

```python
from runtime.learning.signal_collector import get_signal_collector

collector = get_signal_collector()
summary = collector.collect_run_signals(
    run_id="run_001",
    tool_sequence=["parse", "embed", "retrieve"],
    planner_choice="normal",
    retrieval_policy_id="basic_v1",
    evidence_summary={"total_evidence": 10, "used_evidence": 4},
    generation_info={"template_id": "rag_v1", "cost": 0.02},
    run_success=True
)
collector.record_run_signals(summary)
```

---

## 结论

Layer 5-9 闭环实现完成，所有验收条件满足。系统现在具备：

1. **可归因信号**: 每层都能产生 Learning 可用的结构化信号
2. **版本化接口**: 每层都有策略/版本化支持
3. **失败可追踪**: 每层失败都能被分类、统计、回放
4. **非侵入性**: 所有模块可独立删除，不影响主系统

测试覆盖：92 个测试全部通过（含新增 17 个 Layer 5-9 测试）



