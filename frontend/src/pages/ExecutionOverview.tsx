import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { spacing, colors, typography, borderRadius, shadows } from '../design/tokens'

interface ExecutionOverview {
  current_plan: string | null
  plan_id: string | null
  current_node: string | null
  total_cost: number
  has_degraded: boolean
  has_paused: boolean
  executed_nodes_count: number
}

interface TaskInfo {
  task_id: string
  status: {
    state: string
    error?: string
    progress?: {
      currentAgent?: string
      currentStep?: string
    }
  }
  execution_overview: ExecutionOverview
  created_at?: string
}

function ExecutionOverview() {
  const { taskId } = useParams<{ taskId: string }>()
  const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchTaskInfo = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}`)
        if (response.ok) {
          const data = await response.json()
          setTaskInfo(data)
        }
      } catch (error) {
        console.error('Failed to fetch task info:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchTaskInfo()
    const interval = setInterval(fetchTaskInfo, 2000)
    return () => clearInterval(interval)
  }, [taskId])

  if (loading) {
    return <div style={{ padding: '2rem' }}>加载中...</div>
  }

  if (!taskInfo) {
    return <div style={{ padding: '2rem' }}>任务不存在</div>
  }

  const { status, execution_overview } = taskInfo

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
        执行总览
      </h1>
      
      <div style={{
        marginTop: spacing.xl,
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))',
        gap: spacing.lg
      }}>
        {/* 基本信息 */}
        <div style={{
          padding: spacing.lg,
          border: `1px solid ${colors.border}`,
          borderRadius: borderRadius.md,
          backgroundColor: colors.surface,
          boxShadow: shadows.sm
        }}>
          <h3 style={{
            margin: `0 0 ${spacing.md} 0`,
            fontSize: typography.fontSize.lg,
            fontWeight: typography.fontWeight.semibold
          }}>
            任务信息
          </h3>
          <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
            <strong>任务ID:</strong> {taskInfo.task_id}
          </p>
          <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
            <strong>状态:</strong>{' '}
            <span style={{
              color: status.state === 'COMPLETED' ? colors.success :
                     status.state === 'FAILED' ? colors.danger :
                     status.state === 'PAUSED' ? colors.warning : colors.accent,
              fontWeight: typography.fontWeight.medium
            }}>
              {status.state}
            </span>
          </p>
          {status.error && (
            <p style={{
              margin: `${spacing.xs} 0`,
              color: colors.danger,
              fontSize: typography.fontSize.sm
            }}>
              <strong>错误:</strong> {status.error}
            </p>
          )}
          {taskInfo.created_at && (
            <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
              <strong>创建时间:</strong> {new Date(taskInfo.created_at).toLocaleString()}
            </p>
          )}
        </div>

        {/* 执行计划信息 */}
        <div style={{
          padding: spacing.lg,
          border: `1px solid ${colors.border}`,
          borderRadius: borderRadius.md,
          backgroundColor: colors.surface,
          boxShadow: shadows.sm
        }}>
          <h3 style={{
            margin: `0 0 ${spacing.md} 0`,
            fontSize: typography.fontSize.lg,
            fontWeight: typography.fontWeight.semibold
          }}>
            执行计划
          </h3>
          <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
            <strong>当前计划:</strong> {execution_overview.current_plan || 'N/A'}
          </p>
          <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
            <strong>计划ID:</strong> {execution_overview.plan_id || 'N/A'}
          </p>
          <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
            <strong>当前节点:</strong> {execution_overview.current_node || 'N/A'}
          </p>
          <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
            <strong>已执行节点数:</strong> {execution_overview.executed_nodes_count}
          </p>
        </div>

        {/* 成本与状态 */}
        <div style={{
          padding: spacing.lg,
          border: `1px solid ${colors.border}`,
          borderRadius: borderRadius.md,
          backgroundColor: colors.surface,
          boxShadow: shadows.sm
        }}>
          <h3 style={{
            margin: `0 0 ${spacing.md} 0`,
            fontSize: typography.fontSize.lg,
            fontWeight: typography.fontWeight.semibold
          }}>
            成本与状态
          </h3>
          <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
            <strong>累计成本:</strong> ${execution_overview.total_cost.toFixed(2)}
          </p>
          {execution_overview.has_degraded && (
            <p style={{
              margin: `${spacing.xs} 0`,
              color: colors.warning,
              fontSize: typography.fontSize.sm
            }}>
              ⚠️ 已发生降级
            </p>
          )}
          {execution_overview.has_paused && (
            <p style={{
              margin: `${spacing.xs} 0`,
              color: colors.warning,
              fontSize: typography.fontSize.sm
            }}>
              ⏸️ 已发生暂停
            </p>
          )}
        </div>

        {/* 当前进度 */}
        {status.progress && (
          <div style={{
            padding: spacing.lg,
            border: `1px solid ${colors.border}`,
            borderRadius: borderRadius.md,
            backgroundColor: colors.surface,
            boxShadow: shadows.sm
          }}>
            <h3 style={{
              margin: `0 0 ${spacing.md} 0`,
              fontSize: typography.fontSize.lg,
              fontWeight: typography.fontWeight.semibold
            }}>
              当前进度
            </h3>
            {status.progress.currentAgent && (
              <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
                <strong>当前Agent:</strong> {status.progress.currentAgent}
              </p>
            )}
            {status.progress.currentStep && (
              <p style={{ margin: `${spacing.xs} 0`, fontSize: typography.fontSize.sm }}>
                <strong>当前步骤:</strong> {status.progress.currentStep}
              </p>
            )}
          </div>
        )}
      </div>

      {/* 导航链接 */}
      <div style={{
        marginTop: spacing.xl,
        display: 'flex',
        flexWrap: 'wrap',
        gap: spacing.md
      }}>
        <a
          href={`/task/${taskId}/replay`}
          style={{
            padding: `${spacing.sm} ${spacing.lg}`,
            backgroundColor: colors.accent,
            color: colors.textInverse,
            textDecoration: 'none',
            borderRadius: borderRadius.md,
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            boxShadow: shadows.sm
          }}
        >
          执行回放视图
        </a>
        <a
          href={`/task/${taskId}/cost`}
          style={{
            padding: `${spacing.sm} ${spacing.lg}`,
            backgroundColor: colors.warning,
            color: colors.textPrimary,
            textDecoration: 'none',
            borderRadius: borderRadius.md,
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            boxShadow: shadows.sm
          }}
        >
          成本-结果分析
        </a>
        <a
          href={`/task/${taskId}/plan`}
          style={{
            padding: `${spacing.sm} ${spacing.lg}`,
            backgroundColor: colors.success,
            color: colors.textInverse,
            textDecoration: 'none',
            borderRadius: borderRadius.md,
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            boxShadow: shadows.sm
          }}
        >
          执行计划 DAG
        </a>
        <a
          href={`/task/${taskId}/timeline`}
          style={{
            padding: `${spacing.sm} ${spacing.lg}`,
            backgroundColor: colors.info,
            color: colors.textInverse,
            textDecoration: 'none',
            borderRadius: borderRadius.md,
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            boxShadow: shadows.sm
          }}
        >
          系统时间线
        </a>
        <a
          href={`/task/${taskId}/agents`}
          style={{
            padding: `${spacing.sm} ${spacing.lg}`,
            backgroundColor: colors.textSecondary,
            color: colors.textInverse,
            textDecoration: 'none',
            borderRadius: borderRadius.md,
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            boxShadow: shadows.sm
          }}
        >
          Agent 报告
        </a>
        <a
          href={`/task/${taskId}/tools`}
          style={{
            padding: `${spacing.sm} ${spacing.lg}`,
            backgroundColor: colors.textSecondary,
            color: colors.textInverse,
            textDecoration: 'none',
            borderRadius: borderRadius.md,
            fontSize: typography.fontSize.sm,
            fontWeight: typography.fontWeight.medium,
            boxShadow: shadows.sm
          }}
        >
          工具调用
        </a>
        {status.state === 'FAILED' && (
          <a
            href={`/task/${taskId}/failure`}
            style={{
              padding: `${spacing.sm} ${spacing.lg}`,
              backgroundColor: colors.danger,
              color: colors.textInverse,
              textDecoration: 'none',
              borderRadius: borderRadius.md,
              fontSize: typography.fontSize.sm,
              fontWeight: typography.fontWeight.medium,
              boxShadow: shadows.sm
            }}
          >
            失败解释
          </a>
        )}
      </div>
    </div>
  )
}

export default ExecutionOverview

