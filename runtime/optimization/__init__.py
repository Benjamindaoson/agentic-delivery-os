"""
Optimization Layer: 算法级系统优化模块
- Scheduler: 确定性调度优化
- Pareto Pruner: 多目标路径剪枝
- Recovery Policy: 失败分类与恢复策略映射
- Summarizer: 分层摘要
- Salience Ranker: 显著性排序
- Cost Forecaster: 可审计成本预测

所有算法必须：
- 可配置（configs/system.yaml 或独立配置）
- 可静态审计（参数、公式、阈值写清楚）
- 输出可被 trace 审计（记录输入摘要、输出、版本号）
- 不引入在线学习/自适应黑箱
"""


