/**
 * Failure Explain View: 失败解释视图
 * 
 * 目标：用证据解释失败原因
 */
import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { spacing, colors, typography, borderRadius, shadows } from '../design/tokens'

interface FailureInfo {
  failure_type: string | null
  blame_hint: string | null
  evaluation_feedback: any
  governance_decisions: any[]
  evidence_events: string[]
}

function FailureExplain() {
  const { taskId } = useParams<{ taskId: string }>()
  const [failureInfo, setFailureInfo] = useState<FailureInfo | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchFailureInfo = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/trace`)
        if (response.ok) {
          const traceData = await response.json()
          
          const eval_feedback = traceData.evaluation_feedback_flow || {}
          const gov_decisions = traceData.governance_decisions || []
          
          setFailureInfo({
            failure_type: eval_feedback.last_failure_type,
            blame_hint: eval_feedback.last_blame_hint,
            evaluation_feedback: eval_feedback,
            governance_decisions: gov_decisions.filter((d: any) => 
              d.execution_mode !== 'normal'
            ),
            evidence_events: traceData.agent_reports?.map((_r: any, idx: number) => 
              `agent_report_${idx}`
            ) || []
          })
        }
      } catch (error) {
        console.error('Failed to fetch failure info:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchFailureInfo()
  }, [taskId])

  if (loading) {
    return <div style={{ padding: spacing.xl }}>加载中...</div>
  }

  if (!failureInfo) {
    return (
      <div style={{ padding: spacing.xl }}>
        <h1>失败解释</h1>
        <p>未检测到失败</p>
      </div>
    )
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
        失败解释
      </h1>

      {/* 失败类型 */}
      {failureInfo.failure_type && (
        <div style={{
          padding: spacing.lg,
          marginBottom: spacing.lg,
          backgroundColor: colors.danger + '20',
          border: `2px solid ${colors.danger}`,
          borderRadius: borderRadius.md
        }}>
          <h2 style={{
            margin: `0 0 ${spacing.sm} 0`,
            fontSize: typography.fontSize.xl,
            fontWeight: typography.fontWeight.semibold,
            color: colors.danger
          }}>
            失败类型
          </h2>
          <p style={{
            margin: 0,
            fontSize: typography.fontSize.lg,
            fontWeight: typography.fontWeight.medium
          }}>
            {failureInfo.failure_type}
          </p>
          {failureInfo.blame_hint && (
            <p style={{
              margin: `${spacing.sm} 0 0 0`,
              fontSize: typography.fontSize.base,
              color: colors.textSecondary
            }}>
              <strong>归因线索:</strong> {failureInfo.blame_hint}
            </p>
          )}
        </div>
      )}

      {/* 治理决策 */}
      {failureInfo.governance_decisions.length > 0 && (
        <div style={{
          padding: spacing.lg,
          marginBottom: spacing.lg,
          backgroundColor: colors.surface,
          borderRadius: borderRadius.md,
          boxShadow: shadows.md
        }}>
          <h2 style={{
            margin: `0 0 ${spacing.md} 0`,
            fontSize: typography.fontSize.xl,
            fontWeight: typography.fontWeight.semibold
          }}>
            相关治理决策
          </h2>
          {failureInfo.governance_decisions.map((decision, idx) => (
            <div
              key={idx}
              style={{
                padding: spacing.md,
                marginBottom: spacing.sm,
                backgroundColor: colors.backgroundSecondary,
                borderRadius: borderRadius.sm
              }}
            >
              <div style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                marginBottom: spacing.xs
              }}>
                <strong>{decision.execution_mode}</strong>
                {decision.checkpoint && (
                  <span style={{
                    fontSize: typography.fontSize.xs,
                    color: colors.textSecondary
                  }}>
                    {decision.checkpoint}
                  </span>
                )}
              </div>
              {decision.reasoning && (
                <p style={{
                  margin: 0,
                  fontSize: typography.fontSize.sm,
                  color: colors.textSecondary
                }}>
                  {decision.reasoning}
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* 证据事件 */}
      <div style={{
        padding: spacing.lg,
        backgroundColor: colors.surface,
        borderRadius: borderRadius.md,
        boxShadow: shadows.md
      }}>
        <h2 style={{
          margin: `0 0 ${spacing.md} 0`,
          fontSize: typography.fontSize.xl,
          fontWeight: typography.fontWeight.semibold
        }}>
          证据事件
        </h2>
        <div style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: spacing.sm
        }}>
          {failureInfo.evidence_events.map((eventId, idx) => (
            <code
              key={idx}
              style={{
                padding: `${spacing.xs} ${spacing.sm}`,
                backgroundColor: colors.backgroundSecondary,
                borderRadius: borderRadius.sm,
                fontSize: typography.fontSize.xs,
                fontFamily: typography.fontFamily.mono
              }}
            >
              {eventId}
            </code>
          ))}
        </div>
      </div>
    </div>
  )
}

export default FailureExplain


