"""
Layer 5-9 闭环验证测试
验证 Tool → Retrieval → Evidence → Generation 的因果链可被 Learning 消费
"""
import os
import json
from datetime import datetime

# Layer 5: Tooling
from runtime.tooling.tool_failure_classifier import (
    ToolFailureClassifier,
    ToolFailureType,
    ToolInvocationResult
)
from runtime.tooling.tool_metrics import (
    ToolMetricsCollector,
    get_tool_metrics_collector
)

# Layer 6: Memory
from runtime.memory.working_memory import (
    WorkingMemory,
    PatternSignature,
    get_working_memory
)

# Layer 7: Retrieval
from runtime.retrieval.retrieval_policy import (
    RetrievalPolicy,
    RetrievalResult,
    RetrievalPolicyRegistry,
    ChunkingStrategy,
    EmbeddingModel,
    RerankStrategy,
    get_retrieval_policy_registry
)

# Layer 8: Evidence
from runtime.rag_delivery.evidence_contribution import (
    EvidencePack,
    EvidenceContributionTracker,
    EvidenceStatsCollector,
    get_evidence_stats_collector
)

# Layer 9: Generation
from runtime.llm.prompt_tracking import (
    PromptVariantTracker,
    PromptComposerOutput,
    get_prompt_tracker
)


class TestLayer5Tooling:
    """Layer 5: Tooling & Environment 测试"""
    
    def test_tool_failure_classifier(self, tmp_path, monkeypatch):
        """测试工具失败分类"""
        monkeypatch.chdir(tmp_path)
        
        classifier = ToolFailureClassifier()
        
        # 成功情况
        assert classifier.classify(True) is None
        
        # 超时
        failure_type = classifier.classify(False, "Command timeout expired", -1)
        assert failure_type == ToolFailureType.TIMEOUT
        
        # 权限拒绝
        failure_type = classifier.classify(False, "Permission denied: /etc/passwd", 126)
        assert failure_type == ToolFailureType.PERMISSION_DENIED
        
        # 无效输入
        failure_type = classifier.classify(False, "Validation failed: missing required field", 2)
        assert failure_type == ToolFailureType.INVALID_INPUT
        
        # 环境错误
        failure_type = classifier.classify(False, "Docker container not found", 127)
        assert failure_type == ToolFailureType.ENVIRONMENT_ERROR
        
        print("✅ Tool failure classifier 测试通过")
    
    def test_tool_invocation_result(self, tmp_path, monkeypatch):
        """测试工具调用结果包装"""
        monkeypatch.chdir(tmp_path)
        
        classifier = ToolFailureClassifier()
        
        result = classifier.wrap_tool_result(
            tool_name="file_write",
            success=False,
            latency_ms=150.5,
            error_message="Permission denied: /etc/passwd",
            exit_code=126,
            retry_count=2,
            cost_estimate=0.001
        )
        
        assert result.tool_name == "file_write"
        assert result.success is False
        assert result.failure_type == ToolFailureType.PERMISSION_DENIED
        assert result.latency_ms == 150.5
        assert result.retry_count == 2
        
        # 验证 to_dict
        result_dict = result.to_dict()
        assert result_dict["failure_type"] == "PERMISSION_DENIED"
        
        print("✅ Tool invocation result 测试通过")
    
    def test_tool_metrics_collector(self, tmp_path, monkeypatch):
        """测试工具指标收集"""
        monkeypatch.chdir(tmp_path)
        
        stats_path = tmp_path / "artifacts" / "tool_stats.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        collector = ToolMetricsCollector(stats_path=str(stats_path))
        classifier = ToolFailureClassifier()
        
        # 记录成功调用
        result1 = classifier.wrap_tool_result(
            tool_name="file_read",
            success=True,
            latency_ms=50.0,
            cost_estimate=0.001
        )
        collector.record(result1)
        
        # 记录失败调用
        result2 = classifier.wrap_tool_result(
            tool_name="file_read",
            success=False,
            latency_ms=100.0,
            error_message="File not found",
            cost_estimate=0.001
        )
        collector.record(result2)
        
        # 验证统计
        stats = collector.get_tool_stats("file_read")
        assert stats is not None
        assert stats.total_invocations == 2
        assert stats.success_count == 1
        assert stats.failure_count == 1
        assert stats.success_rate == 0.5
        
        # 验证文件已生成
        assert stats_path.exists()
        
        # 验证 summary 格式
        summary = collector.get_summary()
        assert "tools" in summary
        assert "file_read" in summary["tools"]
        
        print("✅ Tool metrics collector 测试通过")


class TestLayer6Memory:
    """Layer 6: Memory & State 测试"""
    
    def test_working_memory_record(self, tmp_path, monkeypatch):
        """测试工作记忆记录"""
        monkeypatch.chdir(tmp_path)
        
        storage_path = tmp_path / "artifacts" / "working_memory.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        memory = WorkingMemory(storage_path=str(storage_path))
        
        # 构建模式签名
        signature = memory.build_pattern_signature_from_run(
            tool_sequence=["file_read", "embed", "retrieve"],
            planner_choice="normal",
            retrieval_strategy_id="basic_v1",
            evidence_count=5,
            generation_template_id="product_spec_v1"
        )
        
        # 记录成功
        memory.record(signature, outcome="success", cost=0.5, latency_ms=1000)
        
        # 记录失败
        memory.record(signature, outcome="failure", cost=0.3, latency_ms=800)
        
        # 验证记录
        patterns = memory.get_all_patterns()
        assert len(patterns) == 1
        
        pattern = patterns[0]
        assert pattern.success_count == 1
        assert pattern.failure_count == 1
        assert pattern.total_count == 2
        
        # 验证文件已生成
        assert storage_path.exists()
        
        print("✅ Working memory record 测试通过")
    
    def test_working_memory_decay(self, tmp_path, monkeypatch):
        """测试工作记忆衰减"""
        monkeypatch.chdir(tmp_path)
        
        storage_path = tmp_path / "artifacts" / "working_memory.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        memory = WorkingMemory(
            storage_path=str(storage_path),
            decay_factor=0.5  # 每次衰减 50%
        )
        
        # 添加一个模式
        signature = memory.build_pattern_signature_from_run(
            tool_sequence=["tool1"],
            planner_choice="normal",
            retrieval_strategy_id="basic_v1"
        )
        memory.record(signature, outcome="success")
        
        # 衰减两次
        memory.decay(threshold=0.1)  # 1.0 * 0.5 = 0.5
        memory.decay(threshold=0.1)  # 0.5 * 0.5 = 0.25
        
        # 模式应该还在（0.25 > 0.1）
        assert len(memory.get_all_patterns()) == 1
        
        # 再衰减两次
        memory.decay(threshold=0.1)  # 0.25 * 0.5 = 0.125
        memory.decay(threshold=0.1)  # 0.125 * 0.5 = 0.0625 < 0.1
        
        # 模式应该被删除
        assert len(memory.get_all_patterns()) == 0
        
        print("✅ Working memory decay 测试通过")
    
    def test_working_memory_top_k(self, tmp_path, monkeypatch):
        """测试获取 top-k 成功模式"""
        monkeypatch.chdir(tmp_path)
        
        storage_path = tmp_path / "artifacts" / "working_memory.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        memory = WorkingMemory(storage_path=str(storage_path))
        
        # 添加多个模式，不同成功率
        for i in range(5):
            signature = memory.build_pattern_signature_from_run(
                tool_sequence=[f"tool_{i}"],
                planner_choice="normal",
                retrieval_strategy_id=f"strategy_{i}"
            )
            # i 越大，成功次数越多
            for _ in range(i + 1):
                memory.record(signature, outcome="success")
            memory.record(signature, outcome="failure")
        
        # 获取 top 3
        top_patterns = memory.get_top_k_success_patterns(k=3)
        
        assert len(top_patterns) == 3
        # 最高成功率的应该排在前面
        success_rates = [
            p.success_count / p.total_count
            for p in top_patterns
        ]
        assert success_rates == sorted(success_rates, reverse=True)
        
        print("✅ Working memory top-k 测试通过")


class TestLayer7Retrieval:
    """Layer 7: Retrieval & Knowledge 测试"""
    
    def test_retrieval_policy_versioning(self, tmp_path, monkeypatch):
        """测试检索策略版本化"""
        monkeypatch.chdir(tmp_path)
        
        stats_path = tmp_path / "artifacts" / "retrieval_policy_stats.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        registry = RetrievalPolicyRegistry(stats_path=str(stats_path))
        
        # 获取默认策略
        default_policy = registry.get_default_policy()
        assert default_policy is not None
        assert default_policy.policy_id == "basic_v1"
        
        # 注册新策略
        custom_policy = RetrievalPolicy(
            policy_id="custom_v1",
            policy_version="1.0",
            chunking_strategy=ChunkingStrategy.SEMANTIC,
            embedding_model=EmbeddingModel.BGE_LARGE,
            rerank_strategy=RerankStrategy.CROSS_ENCODER,
            top_k=20
        )
        registry.register(custom_policy)
        
        # 验证策略已注册
        retrieved = registry.get("custom_v1")
        assert retrieved is not None
        assert retrieved.top_k == 20
        
        print("✅ Retrieval policy versioning 测试通过")
    
    def test_retrieval_attribution(self, tmp_path, monkeypatch):
        """测试检索归因追踪"""
        monkeypatch.chdir(tmp_path)
        
        stats_path = tmp_path / "artifacts" / "retrieval_policy_stats.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        registry = RetrievalPolicyRegistry(stats_path=str(stats_path))
        
        # 记录检索结果
        result = RetrievalResult(
            policy_id="basic_v1",
            num_docs=10,
            evidence_used_count=3,
            latency_ms=100.0,
            cost_estimate=0.01,
            doc_ids=["doc1", "doc2", "doc3"]
        )
        
        # 记录成功
        registry.record_result(result, downstream_success=True)
        
        # 验证统计
        stats = registry.get_stats("basic_v1")
        assert stats is not None
        assert stats.total_invocations == 1
        assert stats.success_count == 1
        assert stats.avg_docs_used == 3.0
        
        # 记录失败
        result2 = RetrievalResult(
            policy_id="basic_v1",
            num_docs=5,
            evidence_used_count=1,
            latency_ms=80.0,
            cost_estimate=0.005
        )
        registry.record_result(result2, downstream_success=False)
        
        # 验证统计更新
        stats = registry.get_stats("basic_v1")
        assert stats.total_invocations == 2
        assert stats.success_rate == 0.5
        
        # 验证文件已生成
        assert stats_path.exists()
        
        print("✅ Retrieval attribution 测试通过")


class TestLayer8Evidence:
    """Layer 8: Evidence & Validation 测试"""
    
    def test_evidence_contribution_tracking(self, tmp_path, monkeypatch):
        """测试证据贡献追踪"""
        monkeypatch.chdir(tmp_path)
        
        tracker = EvidenceContributionTracker(run_id="test_run_001")
        
        # 添加证据
        e1 = tracker.add_evidence(
            source_doc_id="doc1",
            chunk_id="chunk1",
            content="This is evidence 1",
            relevance_score=0.95
        )
        
        e2 = tracker.add_evidence(
            source_doc_id="doc1",
            chunk_id="chunk2",
            content="This is evidence 2",
            relevance_score=0.85
        )
        
        e3 = tracker.add_evidence(
            source_doc_id="doc2",
            chunk_id="chunk1",
            content="This is evidence 3",
            relevance_score=0.75
        )
        
        # 标记使用
        tracker.mark_used(e1.evidence_id)
        tracker.mark_used(e2.evidence_id)
        
        # 标记冲突
        tracker.mark_conflict(e2.evidence_id, e3.evidence_id)
        
        # 生成摘要
        summary = tracker.generate_usage_summary()
        
        assert summary.total_evidence == 3
        assert summary.used_evidence == 2
        assert summary.conflicting_evidence == 2  # e2 和 e3 都标记为冲突
        assert summary.usage_rate == 2 / 3
        
        print("✅ Evidence contribution tracking 测试通过")
    
    def test_evidence_stats_collector(self, tmp_path, monkeypatch):
        """测试证据统计收集"""
        monkeypatch.chdir(tmp_path)
        
        stats_path = tmp_path / "artifacts" / "evidence_stats.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        collector = EvidenceStatsCollector(stats_path=str(stats_path))
        
        # 记录多个 run 的摘要
        for i in range(10):
            tracker = EvidenceContributionTracker(run_id=f"run_{i}")
            
            # 添加证据
            for j in range(5):
                e = tracker.add_evidence(
                    source_doc_id=f"doc{j}",
                    chunk_id=f"chunk{j}",
                    content=f"Evidence {j}",
                    relevance_score=0.9 - j * 0.1
                )
                if j < 3:  # 前 3 个被使用
                    tracker.mark_used(e.evidence_id)
            
            summary = tracker.generate_usage_summary()
            collector.record(summary)
        
        # 验证聚合统计
        aggregate = collector.get_aggregate_stats()
        assert aggregate["window_size"] == 10
        assert abs(aggregate["avg_usage_rate"] - 0.6) < 0.001  # 3/5, 允许浮点误差
        
        # 验证文件已生成
        assert stats_path.exists()
        
        print("✅ Evidence stats collector 测试通过")


class TestLayer9Generation:
    """Layer 9: Generation 测试"""
    
    def test_prompt_variant_tracking(self, tmp_path, monkeypatch):
        """测试 Prompt 变体追踪"""
        monkeypatch.chdir(tmp_path)
        
        stats_path = tmp_path / "artifacts" / "prompt_stats.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        tracker = PromptVariantTracker(stats_path=str(stats_path))
        
        # 创建 composer 输出
        composer_output = tracker.compose_output(
            template_id="product_spec_interpreter",
            version="v1",
            context_size=2048,
            tool_context_included=True,
            system_prompt="You are a helpful assistant.",
            user_prompt="Analyze this document."
        )
        
        assert composer_output.prompt_template_id == "product_spec_interpreter"
        assert composer_output.tool_context_included is True
        assert len(composer_output.system_prompt_hash) == 12
        
        print("✅ Prompt variant tracking 测试通过")
    
    def test_generation_recording(self, tmp_path, monkeypatch):
        """测试生成记录"""
        monkeypatch.chdir(tmp_path)
        
        stats_path = tmp_path / "artifacts" / "prompt_stats.json"
        (tmp_path / "artifacts").mkdir(parents=True)
        
        tracker = PromptVariantTracker(stats_path=str(stats_path))
        
        composer_output = tracker.compose_output(
            template_id="test_template",
            version="v1",
            context_size=1000,
            tool_context_included=False
        )
        
        # 记录成功生成
        result1 = tracker.record_generation(
            composer_output=composer_output,
            token_count=500,
            latency_ms=200.0,
            success=True,
            cost_estimate=0.01,
            model_name="gpt-4",
            output_content="Generated output"
        )
        
        assert result1.success is True
        assert len(result1.output_hash) == 12
        
        # 记录失败生成
        result2 = tracker.record_generation(
            composer_output=composer_output,
            token_count=100,
            latency_ms=50.0,
            success=False,
            cost_estimate=0.002,
            error_message="Rate limit exceeded"
        )
        
        assert result2.success is False
        
        # 验证统计
        stats = tracker.get_stats("test_template", "v1")
        assert stats is not None
        assert stats.total_invocations == 2
        assert stats.success_count == 1
        assert stats.failure_count == 1
        assert stats.success_rate == 0.5
        
        # 验证 summary 格式
        summary = tracker.get_summary()
        assert "templates" in summary
        assert "test_template:v1" in summary["templates"]
        
        # 验证文件已生成
        assert stats_path.exists()
        
        print("✅ Generation recording 测试通过")


class TestFullCausalChain:
    """完整因果链测试：Tool → Retrieval → Evidence → Generation"""
    
    def test_full_run_signal_chain(self, tmp_path, monkeypatch):
        """测试完整 Run 的信号链"""
        monkeypatch.chdir(tmp_path)
        
        # 创建 artifacts 目录
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir(parents=True)
        
        run_id = "test_run_full_chain"
        
        # === Layer 5: Tool Execution ===
        tool_classifier = ToolFailureClassifier()
        tool_collector = ToolMetricsCollector(
            stats_path=str(artifacts_dir / "tool_stats.json")
        )
        
        tool_result = tool_classifier.wrap_tool_result(
            tool_name="document_parser",
            success=True,
            latency_ms=150.0,
            cost_estimate=0.005
        )
        tool_collector.record(tool_result)
        
        # === Layer 6: Working Memory ===
        memory = WorkingMemory(
            storage_path=str(artifacts_dir / "working_memory.json")
        )
        
        # 记录工具序列
        tool_sequence = ["document_parser", "embedder", "retriever"]
        
        # === Layer 7: Retrieval ===
        retrieval_registry = RetrievalPolicyRegistry(
            stats_path=str(artifacts_dir / "retrieval_policy_stats.json")
        )
        
        retrieval_result = RetrievalResult(
            policy_id="basic_v1",
            num_docs=10,
            evidence_used_count=4,
            latency_ms=80.0,
            cost_estimate=0.01
        )
        
        # === Layer 8: Evidence ===
        evidence_tracker = EvidenceContributionTracker(run_id=run_id)
        evidence_collector = EvidenceStatsCollector(
            stats_path=str(artifacts_dir / "evidence_stats.json")
        )
        
        # 添加检索到的证据
        for i in range(10):
            e = evidence_tracker.add_evidence(
                source_doc_id=f"doc{i}",
                chunk_id=f"chunk{i}",
                content=f"Evidence content {i}",
                relevance_score=0.9 - i * 0.05
            )
            if i < 4:  # 前 4 个被使用
                evidence_tracker.mark_used(e.evidence_id)
        
        evidence_summary = evidence_tracker.generate_usage_summary()
        evidence_collector.record(evidence_summary)
        
        # === Layer 9: Generation ===
        prompt_tracker = PromptVariantTracker(
            stats_path=str(artifacts_dir / "prompt_stats.json")
        )
        
        composer_output = prompt_tracker.compose_output(
            template_id="rag_answer",
            version="v1",
            context_size=2000,
            tool_context_included=True
        )
        
        generation_result = prompt_tracker.record_generation(
            composer_output=composer_output,
            token_count=800,
            latency_ms=300.0,
            success=True,
            cost_estimate=0.02,
            output_content="Final answer based on evidence."
        )
        
        # === 记录到 Working Memory ===
        signature = memory.build_pattern_signature_from_run(
            tool_sequence=tool_sequence,
            planner_choice="normal",
            retrieval_strategy_id="basic_v1",
            evidence_count=evidence_summary.used_evidence,
            generation_template_id="rag_answer:v1"
        )
        
        # 确定最终结果
        downstream_success = generation_result.success
        memory.record(
            signature,
            outcome="success" if downstream_success else "failure",
            cost=0.005 + 0.01 + 0.02,  # tool + retrieval + generation
            latency_ms=150 + 80 + 300  # tool + retrieval + generation
        )
        
        # 记录到 retrieval stats
        retrieval_registry.record_result(retrieval_result, downstream_success=downstream_success)
        
        # === 验证所有 artifacts 已生成 ===
        assert (artifacts_dir / "tool_stats.json").exists()
        assert (artifacts_dir / "working_memory.json").exists()
        assert (artifacts_dir / "retrieval_policy_stats.json").exists()
        assert (artifacts_dir / "evidence_stats.json").exists()
        assert (artifacts_dir / "prompt_stats.json").exists()
        
        # === 验证 Learning 可消费的信号 ===
        # Tool failure patterns
        tool_summary = tool_collector.get_summary()
        assert "document_parser" in tool_summary["tools"]
        
        # Retrieval policy effectiveness
        retrieval_summary = retrieval_registry.get_summary()
        assert "basic_v1" in retrieval_summary["policies"]
        
        # Memory success patterns
        memory_summary = memory.get_summary()
        assert memory_summary["total_patterns"] >= 1
        
        # Evidence usage
        evidence_aggregate = evidence_collector.get_aggregate_stats()
        assert evidence_aggregate["avg_usage_rate"] > 0
        
        # Prompt stats
        prompt_summary = prompt_tracker.get_summary()
        assert "rag_answer:v1" in prompt_summary["templates"]
        
        print("✅ 完整因果链测试通过")
    
    def test_artifacts_are_json_and_replayable(self, tmp_path, monkeypatch):
        """验证所有 artifacts 为 JSON 且可 replay/diff"""
        monkeypatch.chdir(tmp_path)
        
        artifacts_dir = tmp_path / "artifacts"
        artifacts_dir.mkdir(parents=True)
        
        # 创建各层收集器并记录数据
        tool_collector = ToolMetricsCollector(
            stats_path=str(artifacts_dir / "tool_stats.json")
        )
        memory = WorkingMemory(
            storage_path=str(artifacts_dir / "working_memory.json")
        )
        retrieval_registry = RetrievalPolicyRegistry(
            stats_path=str(artifacts_dir / "retrieval_policy_stats.json")
        )
        evidence_collector = EvidenceStatsCollector(
            stats_path=str(artifacts_dir / "evidence_stats.json")
        )
        prompt_tracker = PromptVariantTracker(
            stats_path=str(artifacts_dir / "prompt_stats.json")
        )
        
        # 记录一些数据
        classifier = ToolFailureClassifier()
        tool_result = classifier.wrap_tool_result("test_tool", True, 100.0)
        tool_collector.record(tool_result)
        
        signature = memory.build_pattern_signature_from_run(
            tool_sequence=["test"],
            planner_choice="normal",
            retrieval_strategy_id="default"
        )
        memory.record(signature, "success")
        
        retrieval_result = RetrievalResult(
            policy_id="basic_v1",
            num_docs=5,
            evidence_used_count=2
        )
        retrieval_registry.record_result(retrieval_result, downstream_success=True)
        
        tracker = EvidenceContributionTracker(run_id="test")
        tracker.add_evidence("doc", "chunk", "content", 0.9)
        evidence_collector.record(tracker.generate_usage_summary())
        
        composer = prompt_tracker.compose_output("test", "v1", 100, False)
        prompt_tracker.record_generation(composer, 50, 10.0, True)
        
        # 验证所有文件为有效 JSON
        artifact_files = [
            "tool_stats.json",
            "working_memory.json",
            "retrieval_policy_stats.json",
            "evidence_stats.json",
            "prompt_stats.json"
        ]
        
        for filename in artifact_files:
            filepath = artifacts_dir / filename
            assert filepath.exists(), f"{filename} 不存在"
            
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            assert isinstance(data, dict), f"{filename} 不是有效的 JSON 对象"
            assert "generated_at" in data or "summary" in data, f"{filename} 缺少时间戳"
        
        print("✅ 所有 artifacts 为 JSON 且可 replay/diff 测试通过")


class TestModulesCanBeRemoved:
    """验证模块可独立删除，不影响主系统"""
    
    def test_tooling_module_independent(self, tmp_path, monkeypatch):
        """测试 tooling 模块独立性"""
        monkeypatch.chdir(tmp_path)
        
        # 验证可以独立导入和使用
        from runtime.tooling.tool_failure_classifier import ToolFailureClassifier
        from runtime.tooling.tool_metrics import ToolMetricsCollector
        
        # 验证不依赖其他层
        classifier = ToolFailureClassifier()
        result = classifier.classify(False, "test error")
        assert result is not None
        
        print("✅ Tooling 模块独立性测试通过")
    
    def test_memory_module_independent(self, tmp_path, monkeypatch):
        """测试 memory 模块独立性"""
        monkeypatch.chdir(tmp_path)
        
        from runtime.memory.working_memory import WorkingMemory
        
        memory = WorkingMemory(
            storage_path=str(tmp_path / "test_memory.json")
        )
        assert memory is not None
        
        print("✅ Memory 模块独立性测试通过")
    
    def test_retrieval_module_independent(self, tmp_path, monkeypatch):
        """测试 retrieval 模块独立性"""
        monkeypatch.chdir(tmp_path)
        
        from runtime.retrieval.retrieval_policy import RetrievalPolicyRegistry
        
        registry = RetrievalPolicyRegistry(
            stats_path=str(tmp_path / "test_retrieval.json")
        )
        assert registry.get_default_policy() is not None
        
        print("✅ Retrieval 模块独立性测试通过")

