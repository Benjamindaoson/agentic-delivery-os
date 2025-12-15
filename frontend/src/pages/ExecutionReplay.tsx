/**
 * Execution Replay View: 执行回放视图
 * 
 * 页面目标：用逻辑顺序 + 证据回答：
 * - 系统走了哪条路径
 * - 哪个事件触发了裁决
 * - 哪次 Evaluation 改变了后续行为
 */
import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import ReplayTimeline from '../components/ReplayTimeline'
import { spacing, colors, typography, borderRadius, shadows } from '../design/tokens'

interface TaskInfo {
  task_id: string
  status: {
    state: string
    error?: string
  }
  execution_overview: {
    current_plan: string | null
    plan_id: string | null
    total_cost: number
    has_degraded: boolean
    has_paused: boolean
  }
}

interface EvidenceDrawerProps {
  eventId: string | null
  sequenceId: number | null
  taskId: string
}

function EvidenceDrawer({ eventId, sequenceId, taskId }: EvidenceDrawerProps) {
  const [evidence, setEvidence] = useState<any>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!eventId || !sequenceId) {
      setEvidence(null)
      return
    }

    const fetchEvidence = async () => {
      setLoading(true)
      try {
        // 从事件流中获取事件详情
        const response = await fetch(`/api/task/${taskId}/trace/events?limit=1000`)
        if (response.ok) {
          const data = await response.json()
          const event = data.events.find((e: any, idx: number) => 
            e.event_id === eventId || (idx + 1) === sequenceId
          )
          
          if (event) {
            // 从完整 trace 获取更多上下文
            const traceResponse = await fetch(`/api/task/${taskId}/trace`)
            if (traceResponse.ok) {
              const traceData = await traceResponse.json()
              
              // 查找对应的 agent_execution 或 governance_decision
              let traceEvent = null
              let traceLocation = ''
              
              if (event.type === 'agent_report' || event.type === 'agent_execution') {
                traceEvent = traceData.agent_executions?.find((e: any) => 
                  e.agent === event.payload?.agent_name
                )
                traceLocation = `trace.agent_executions[${traceData.agent_executions?.indexOf(traceEvent) || 0}]`
              } else if (event.type === 'governance_decision') {
                traceEvent = traceData.governance_decisions?.find((e: any) => 
                  e.checkpoint === event.payload?.checkpoint
                )
                traceLocation = `trace.governance_decisions[${traceData.governance_decisions?.indexOf(traceEvent) || 0}]`
              }
              
              setEvidence({
                event_id: event.event_id,
                sequence_id: sequenceId,
                trace_location: traceLocation || `trace.events[${sequenceId - 1}]`,
                data: traceEvent || event.payload || event
              })
            }
          }
        }
      } catch (error) {
        console.error('Failed to fetch evidence:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchEvidence()
  }, [eventId, sequenceId, taskId])

  if (!eventId) {
    return (
      <div style={{
        padding: spacing.xl,
        backgroundColor: colors.backgroundSecondary,
        borderRadius: borderRadius.md,
        textAlign: 'center',
        color: colors.textSecondary
      }}>
        选择事件查看证据
      </div>
    )
  }

  if (loading) {
    return <div style={{ padding: spacing.xl }}>加载中...</div>
  }

  if (!evidence) {
    return (
      <div style={{ padding: spacing.xl, color: colors.textSecondary }}>
        未找到证据
      </div>
    )
  }

  return (
    <div style={{
      padding: spacing.lg,
      backgroundColor: colors.background,
      borderRadius: borderRadius.md,
      boxShadow: shadows.md
    }}>
      <h3 style={{
        margin: `0 0 ${spacing.md} 0`,
        fontSize: typography.fontSize.lg,
        fontWeight: typography.fontWeight.semibold
      }}>
        证据抽屉
      </h3>
      
      <div style={{ fontSize: typography.fontSize.sm, marginBottom: spacing.md }}>
        <p><strong>Event ID:</strong> <code>{evidence.event_id}</code></p>
        <p><strong>Sequence ID:</strong> {evidence.sequence_id}</p>
        <p><strong>Trace Location:</strong> <code>{evidence.trace_location}</code></p>
      </div>

      <details style={{ marginTop: spacing.md }}>
        <summary style={{
          cursor: 'pointer',
          fontWeight: typography.fontWeight.medium,
          marginBottom: spacing.sm
        }}>
          完整证据数据
        </summary>
        <pre style={{
          marginTop: spacing.sm,
          padding: spacing.md,
          backgroundColor: colors.surface,
          borderRadius: borderRadius.sm,
          overflow: 'auto',
          fontSize: typography.fontSize.xs,
          fontFamily: typography.fontFamily.mono
        }}>
          {JSON.stringify(evidence.data, null, 2)}
        </pre>
      </details>
    </div>
  )
}

function ExecutionReplay() {
  const { taskId } = useParams<{ taskId: string }>()
  const [taskInfo, setTaskInfo] = useState<TaskInfo | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null)
  const [selectedSequenceId, setSelectedSequenceId] = useState<number | null>(null)

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
      }
    }
    fetchTaskInfo()
  }, [taskId])

  const handleEventSelect = (eventId: string, sequenceId: number) => {
    setSelectedEventId(eventId)
    setSelectedSequenceId(sequenceId)
  }

  if (!taskInfo) {
    return <div style={{ padding: spacing.xl }}>加载中...</div>
  }

  return (
    <div style={{
      padding: spacing.xl,
      maxWidth: '1400px',
      margin: '0 auto',
      backgroundColor: colors.background
    }}>
      <h1 style={{
        margin: `0 0 ${spacing.xl} 0`,
        fontSize: typography.fontSize.xxxl,
        fontWeight: typography.fontWeight.bold
      }}>
        执行回放视图
      </h1>

      {/* A. 顶栏 KPI */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: spacing.lg,
        marginBottom: spacing.xl
      }}>
        <div style={{
          padding: spacing.lg,
          backgroundColor: colors.surface,
          borderRadius: borderRadius.md,
          boxShadow: shadows.sm
        }}>
          <div style={{
            fontSize: typography.fontSize.sm,
            color: colors.textSecondary,
            marginBottom: spacing.xs
          }}>
            Task Status
          </div>
          <div style={{
            fontSize: typography.fontSize.xl,
            fontWeight: typography.fontWeight.semibold,
            color: taskInfo.status.state === 'COMPLETED' ? colors.success :
                   taskInfo.status.state === 'FAILED' ? colors.danger : colors.accent
          }}>
            {taskInfo.status.state}
          </div>
        </div>

        <div style={{
          padding: spacing.lg,
          backgroundColor: colors.surface,
          borderRadius: borderRadius.md,
          boxShadow: shadows.sm
        }}>
          <div style={{
            fontSize: typography.fontSize.sm,
            color: colors.textSecondary,
            marginBottom: spacing.xs
          }}>
            Execution Mode
          </div>
          <div style={{
            fontSize: typography.fontSize.xl,
            fontWeight: typography.fontWeight.semibold
          }}>
            {taskInfo.execution_overview.current_plan || 'N/A'}
          </div>
        </div>

        <div style={{
          padding: spacing.lg,
          backgroundColor: colors.surface,
          borderRadius: borderRadius.md,
          boxShadow: shadows.sm
        }}>
          <div style={{
            fontSize: typography.fontSize.sm,
            color: colors.textSecondary,
            marginBottom: spacing.xs
          }}>
            Accumulated Cost
          </div>
          <div style={{
            fontSize: typography.fontSize.xl,
            fontWeight: typography.fontWeight.semibold
          }}>
            ${taskInfo.execution_overview.total_cost.toFixed(2)}
          </div>
        </div>

        <div style={{
          padding: spacing.lg,
          backgroundColor: colors.surface,
          borderRadius: borderRadius.md,
          boxShadow: shadows.sm
        }}>
          <div style={{
            fontSize: typography.fontSize.sm,
            color: colors.textSecondary,
            marginBottom: spacing.xs
          }}>
            Key Events
          </div>
          <div style={{
            fontSize: typography.fontSize.xl,
            fontWeight: typography.fontWeight.semibold
          }}>
            {taskInfo.execution_overview.has_degraded && '⚠️ Degraded'}
            {taskInfo.execution_overview.has_paused && '⏸️ Paused'}
          </div>
        </div>
      </div>

      {/* B. Replay Timeline（逻辑序列） */}
      <div style={{ marginBottom: spacing.xl }}>
        <h2 style={{
          margin: `0 0 ${spacing.lg} 0`,
          fontSize: typography.fontSize.xxl,
          fontWeight: typography.fontWeight.semibold
        }}>
          逻辑执行顺序回放
        </h2>
        <ReplayTimeline
          taskId={taskId!}
          onEventSelect={handleEventSelect}
        />
      </div>

      {/* C. Evidence Drawer（证据抽屉） */}
      <div>
        <h2 style={{
          margin: `0 0 ${spacing.lg} 0`,
          fontSize: typography.fontSize.xxl,
          fontWeight: typography.fontWeight.semibold
        }}>
          证据抽屉
        </h2>
        <EvidenceDrawer
          eventId={selectedEventId}
          sequenceId={selectedSequenceId}
          taskId={taskId!}
        />
      </div>
    </div>
  )
}

export default ExecutionReplay

