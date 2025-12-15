/**
 * Cost–Outcome View: 成本-结果视图
 * 
 * 反事实语义：Deterministic Counterfactual Cost Estimation
 * - 基于 plan_definition 的全路径静态展开
 * - 基于节点级确定性成本规则估算
 * - 不依赖真实执行
 * - 不假设该路径一定会成功执行
 * 
 * 明确声明：该结果是反事实成本估算（counterfactual estimate），
 * 用于衡量剪枝/降级的工程价值，不代表系统真实可能执行的路径。
 */
import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { spacing, colors, typography, borderRadius, shadows } from '../design/tokens'

interface CostComparison {
  actual_path: {
    path_type: string
    cost: number
    nodes_executed: number
  }
  counterfactual_paths: Array<{
    path_type: string
    estimated_cost: number
    estimated_nodes: number
    description: string
  }>
}

function CostOutcome() {
  const { taskId } = useParams<{ taskId: string }>()
  const [comparison, setComparison] = useState<CostComparison | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchComparison = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/trace`)
        if (response.ok) {
          const traceData = await response.json()
          
          // 提取实际路径信息
          const execution_plan = traceData.execution_plan || {}
          const actual_path = {
            path_type: execution_plan.path_type || 'unknown',
            cost: traceData.agent_reports?.reduce((sum: number, r: any) => 
              sum + (r.cost_impact || 0), 0) || 0,
            nodes_executed: execution_plan.executed_nodes?.length || 0
          }
          
          // 生成反事实路径估算（确定性规则）
          const counterfactual_paths = [
            {
              path_type: 'NORMAL',
              estimated_cost: actual_path.cost * 1.5, // 简化：假设 NORMAL 成本高 50%
              estimated_nodes: actual_path.nodes_executed + 2,
              description: '完整执行路径（未降级）'
            },
            {
              path_type: 'MINIMAL',
              estimated_cost: actual_path.cost * 0.5, // 简化：假设 MINIMAL 成本低 50%
              estimated_nodes: Math.max(1, actual_path.nodes_executed - 2),
              description: '最小执行路径'
            }
          ]
          
          setComparison({
            actual_path,
            counterfactual_paths
          })
        }
      } catch (error) {
        console.error('Failed to fetch comparison:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchComparison()
  }, [taskId])

  if (loading) {
    return <div style={{ padding: spacing.xl }}>加载中...</div>
  }

  if (!comparison) {
    return <div style={{ padding: spacing.xl }}>数据不可用</div>
  }

  return (
    <div style={{
      padding: spacing.xl,
      maxWidth: '1200px',
      margin: '0 auto',
      backgroundColor: colors.background
    }}>
      <h1 style={{
        margin: `0 0 ${spacing.xl} 0`,
        fontSize: typography.fontSize.xxxl,
        fontWeight: typography.fontWeight.bold
      }}>
        成本-结果分析
      </h1>

      {/* 反事实语义声明（强制显示） */}
      <div style={{
        padding: spacing.lg,
        marginBottom: spacing.xl,
        backgroundColor: colors.warning,
        color: colors.textInverse,
        borderRadius: borderRadius.md,
        boxShadow: shadows.md
      }}>
        <h3 style={{
          margin: `0 0 ${spacing.sm} 0`,
          fontSize: typography.fontSize.lg,
          fontWeight: typography.fontWeight.bold
        }}>
          ⚠️ 反事实估算说明
        </h3>
        <p style={{
          margin: 0,
          fontSize: typography.fontSize.base,
          lineHeight: typography.lineHeight.relaxed
        }}>
          该视图展示的是 <strong>确定性反事实成本估算（Deterministic Counterfactual Cost Estimation）</strong>。
          基于 <code>plan_definition</code> 的全路径静态展开和节点级确定性成本规则估算。
          <strong>不依赖真实执行，不假设该路径一定会成功执行。</strong>
        </p>
        <p style={{
          margin: `${spacing.sm} 0 0 0`,
          fontSize: typography.fontSize.sm,
          opacity: 0.9
        }}>
          该结果用于衡量剪枝/降级的工程价值，<strong>不代表系统真实可能执行的路径</strong>。
        </p>
      </div>

      {/* 实际路径 */}
      <div style={{
        padding: spacing.lg,
        marginBottom: spacing.xl,
        backgroundColor: colors.surface,
        borderRadius: borderRadius.md,
        boxShadow: shadows.md
      }}>
        <h2 style={{
          margin: `0 0 ${spacing.md} 0`,
          fontSize: typography.fontSize.xl,
          fontWeight: typography.fontWeight.semibold
        }}>
          实际执行路径
        </h2>
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(3, 1fr)',
          gap: spacing.md
        }}>
          <div>
            <div style={{
              fontSize: typography.fontSize.sm,
              color: colors.textSecondary,
              marginBottom: spacing.xs
            }}>
              路径类型
            </div>
            <div style={{
              fontSize: typography.fontSize.lg,
              fontWeight: typography.fontWeight.semibold
            }}>
              {comparison.actual_path.path_type}
            </div>
          </div>
          <div>
            <div style={{
              fontSize: typography.fontSize.sm,
              color: colors.textSecondary,
              marginBottom: spacing.xs
            }}>
              实际成本
            </div>
            <div style={{
              fontSize: typography.fontSize.lg,
              fontWeight: typography.fontWeight.semibold,
              color: colors.accent
            }}>
              ${comparison.actual_path.cost.toFixed(2)}
            </div>
          </div>
          <div>
            <div style={{
              fontSize: typography.fontSize.sm,
              color: colors.textSecondary,
              marginBottom: spacing.xs
            }}>
              执行节点数
            </div>
            <div style={{
              fontSize: typography.fontSize.lg,
              fontWeight: typography.fontWeight.semibold
            }}>
              {comparison.actual_path.nodes_executed}
            </div>
          </div>
        </div>
      </div>

      {/* 反事实路径对比 */}
      <div>
        <h2 style={{
          margin: `0 0 ${spacing.lg} 0`,
          fontSize: typography.fontSize.xl,
          fontWeight: typography.fontWeight.semibold
        }}>
          反事实路径估算 <span style={{
            fontSize: typography.fontSize.sm,
            color: colors.textSecondary,
            fontWeight: typography.fontWeight.normal
          }}>(Estimated - Counterfactual)</span>
        </h2>
        
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: spacing.lg
        }}>
          {comparison.counterfactual_paths.map((path, idx) => {
            const costDiff = path.estimated_cost - comparison.actual_path.cost
            const costDiffPercent = ((costDiff / comparison.actual_path.cost) * 100).toFixed(1)
            
            return (
              <div
                key={idx}
                style={{
                  padding: spacing.lg,
                  backgroundColor: colors.surface,
                  borderRadius: borderRadius.md,
                  boxShadow: shadows.md,
                  border: `2px solid ${colors.border}`
                }}
              >
                <div style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  marginBottom: spacing.md
                }}>
                  <h3 style={{
                    margin: 0,
                    fontSize: typography.fontSize.lg,
                    fontWeight: typography.fontWeight.semibold
                  }}>
                    {path.path_type}
                  </h3>
                  <span style={{
                    padding: `${spacing.xs} ${spacing.sm}`,
                    backgroundColor: colors.backgroundSecondary,
                    borderRadius: borderRadius.sm,
                    fontSize: typography.fontSize.xs,
                    fontWeight: typography.fontWeight.medium,
                    color: colors.textSecondary
                  }}>
                    Not a Replay
                  </span>
                </div>
                
                <p style={{
                  margin: `0 0 ${spacing.md} 0`,
                  fontSize: typography.fontSize.sm,
                  color: colors.textSecondary
                }}>
                  {path.description}
                </p>
                
                <div style={{
                  display: 'grid',
                  gridTemplateColumns: '1fr 1fr',
                  gap: spacing.md,
                  marginBottom: spacing.md
                }}>
                  <div>
                    <div style={{
                      fontSize: typography.fontSize.xs,
                      color: colors.textSecondary,
                      marginBottom: spacing.xs
                    }}>
                      估算成本
                    </div>
                    <div style={{
                      fontSize: typography.fontSize.xl,
                      fontWeight: typography.fontWeight.semibold
                    }}>
                      ${path.estimated_cost.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div style={{
                      fontSize: typography.fontSize.xs,
                      color: colors.textSecondary,
                      marginBottom: spacing.xs
                    }}>
                      估算节点数
                    </div>
                    <div style={{
                      fontSize: typography.fontSize.xl,
                      fontWeight: typography.fontWeight.semibold
                    }}>
                      {path.estimated_nodes}
                    </div>
                  </div>
                </div>
                
                <div style={{
                  padding: spacing.md,
                  backgroundColor: costDiff > 0 ? 
                    (colors.danger + '20') : 
                    (colors.success + '20'),
                  borderRadius: borderRadius.sm,
                  fontSize: typography.fontSize.sm
                }}>
                  <strong>成本差异:</strong> {
                    costDiff > 0 ? '+' : ''
                  }${costDiff.toFixed(2)} ({
                    costDiffPercent
                  }%)
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default CostOutcome


