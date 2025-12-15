/**
 * Replay Timeline: 事件顺序回放视图
 * 
 * 时间语义：Event-Order Replay（事件顺序回放）
 * - 横轴：event_sequence_index（逻辑顺序）
 * - 不是 wall-clock 时间
 * - 不是执行耗时比例
 * - 不是物理时间轴
 * 
 * 表示：系统在"第几个关键事件之后，状态发生了什么变化"
 */
import { useState, useEffect } from 'react'
import { spacing, colors, typography, borderRadius, shadows } from '../design/tokens'

interface TimelineEvent {
  event_id: string
  sequence_id: number
  type: string
  timestamp?: string
  payload?: any
  checkpoint?: string
}

interface ReplayTimelineProps {
  taskId: string
  onEventSelect?: (eventId: string, sequenceId: number) => void
}

function ReplayTimeline({ taskId, onEventSelect }: ReplayTimelineProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [selectedSequenceId, setSelectedSequenceId] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/trace/events?limit=1000`)
        if (response.ok) {
          const data = await response.json()
          // 添加 sequence_id（基于事件顺序）
          const eventsWithSequence = data.events.map((e: any, idx: number) => ({
            ...e,
            sequence_id: idx + 1
          }))
          setEvents(eventsWithSequence)
        }
      } catch (error) {
        console.error('Failed to fetch events:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchEvents()
  }, [taskId])

  const handleSequenceClick = (sequenceId: number) => {
    setSelectedSequenceId(sequenceId)
    const event = events.find(e => e.sequence_id === sequenceId)
    if (event && onEventSelect) {
      onEventSelect(event.event_id || event.type || `event_${sequenceId}`, sequenceId)
    }
  }

  // 识别 checkpoint（事件边界）
  const checkpoints = events
    .map((e) => {
      if (e.checkpoint || e.type === 'governance_decision') {
        return { sequence_id: e.sequence_id, label: e.checkpoint || `After ${e.type}` }
      }
      return null
    })
    .filter((c): c is { sequence_id: number; label: string } => c !== null)

  if (loading) {
    return <div style={{ padding: spacing.xl }}>加载中...</div>
  }

  const maxSequenceId = events.length > 0 ? Math.max(...events.map(e => e.sequence_id)) : 1

  return (
    <div style={{ 
      padding: spacing.xl,
      backgroundColor: colors.background,
      borderRadius: borderRadius.lg,
      boxShadow: shadows.md
    }}>
      {/* 语义声明 */}
      <div style={{
        padding: spacing.md,
        marginBottom: spacing.lg,
        backgroundColor: colors.backgroundSecondary,
        borderRadius: borderRadius.md,
        fontSize: typography.fontSize.sm,
        color: colors.textSecondary
      }}>
        <strong>时间语义说明：</strong>
        这是 <strong>逻辑执行顺序回放</strong>，用于复盘系统决策路径，而不是还原真实执行耗时。
        横轴单位为 <code>event_sequence_index</code>（事件序列索引）。
      </div>

      {/* Timeline 横轴 */}
      <div style={{
        position: 'relative',
        height: '120px',
        marginBottom: spacing.xl
      }}>
        {/* 横轴刻度 */}
        <div style={{
          position: 'absolute',
          bottom: 0,
          left: 0,
          right: 0,
          height: '2px',
          backgroundColor: colors.border
        }} />
        
        {/* 事件节点 */}
        {events.map((event) => {
          const position = (event.sequence_id / maxSequenceId) * 100
          const isSelected = selectedSequenceId === event.sequence_id
          
          return (
            <div
              key={event.event_id}
              onClick={() => handleSequenceClick(event.sequence_id)}
              style={{
                position: 'absolute',
                left: `${position}%`,
                bottom: 0,
                transform: 'translateX(-50%)',
                cursor: 'pointer',
                zIndex: isSelected ? 10 : 1
              }}
            >
              <div style={{
                width: isSelected ? '16px' : '12px',
                height: isSelected ? '16px' : '12px',
                borderRadius: borderRadius.full,
                backgroundColor: isSelected ? colors.accent : colors.borderDark,
                border: `2px solid ${colors.background}`,
                boxShadow: isSelected ? shadows.lg : shadows.sm,
                transition: 'all 0.2s ease'
              }} />
              {isSelected && (
                <div style={{
                  position: 'absolute',
                  bottom: '20px',
                  left: '50%',
                  transform: 'translateX(-50%)',
                  padding: spacing.xs,
                  backgroundColor: colors.textPrimary,
                  color: colors.textInverse,
                  borderRadius: borderRadius.sm,
                  fontSize: typography.fontSize.xs,
                  whiteSpace: 'nowrap',
                  zIndex: 20
                }}>
                  Event #{event.sequence_id}
                </div>
              )}
            </div>
          )
        })}

        {/* Checkpoint 标记 */}
        {checkpoints.map((checkpoint) => {
          const position = (checkpoint.sequence_id / maxSequenceId) * 100
          return (
            <div
              key={checkpoint.sequence_id}
              style={{
                position: 'absolute',
                left: `${position}%`,
                top: 0,
                transform: 'translateX(-50%)',
                padding: `${spacing.xs} ${spacing.sm}`,
                backgroundColor: colors.warning,
                color: colors.textInverse,
                borderRadius: borderRadius.sm,
                fontSize: typography.fontSize.xs,
                fontWeight: typography.fontWeight.semibold,
                whiteSpace: 'nowrap'
              }}
            >
              {checkpoint.label}
            </div>
          )
        })}

        {/* 横轴标签 */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: spacing.md,
          fontSize: typography.fontSize.xs,
          color: colors.textSecondary
        }}>
          <span>Event #1</span>
          <span>Event #{maxSequenceId}</span>
        </div>
      </div>

      {/* 选中事件详情 */}
      {selectedSequenceId && (
        <div style={{
          padding: spacing.lg,
          backgroundColor: colors.backgroundSecondary,
          borderRadius: borderRadius.md,
          marginTop: spacing.lg
        }}>
          <h3 style={{
            margin: `0 0 ${spacing.md} 0`,
            fontSize: typography.fontSize.lg,
            fontWeight: typography.fontWeight.semibold
          }}>
            事件详情 (Sequence #{selectedSequenceId})
          </h3>
          {(() => {
            const event = events.find(e => e.sequence_id === selectedSequenceId)
            if (!event) return null
            
            return (
              <div style={{ fontSize: typography.fontSize.sm }}>
                <p><strong>Event ID:</strong> <code>{event.event_id}</code></p>
                <p><strong>Type:</strong> {event.type}</p>
                {event.checkpoint && <p><strong>Checkpoint:</strong> {event.checkpoint}</p>}
                {event.timestamp && (
                  <p><strong>Timestamp:</strong> {new Date(event.timestamp).toLocaleString()}</p>
                )}
                {event.payload && (
                  <details style={{ marginTop: spacing.md }}>
                    <summary style={{ cursor: 'pointer', fontWeight: typography.fontWeight.medium }}>
                      Payload
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
                      {JSON.stringify(event.payload, null, 2)}
                    </pre>
                  </details>
                )}
              </div>
            )
          })()}
        </div>
      )}
    </div>
  )
}

export default ReplayTimeline

