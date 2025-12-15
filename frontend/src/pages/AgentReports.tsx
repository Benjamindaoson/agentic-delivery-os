import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface AgentReport {
  agent_name: string
  decision: string
  status: string
  confidence: number
  risk_level: string
  cost_impact: number
  signals: Record<string, any>
  conflicts: any[]
  llm_fallback_used: boolean
  timestamp: string
}

function AgentReports() {
  const { taskId } = useParams<{ taskId: string }>()
  const [reports, setReports] = useState<AgentReport[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchReports = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/trace`)
        if (response.ok) {
          const data = await response.json()
          setReports(data.agent_reports || [])
        }
      } catch (error) {
        console.error('Failed to fetch reports:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchReports()
    const interval = setInterval(fetchReports, 2000)
    return () => clearInterval(interval)
  }, [taskId])

  if (loading) {
    return <div style={{ padding: '2rem' }}>加载中...</div>
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success':
        return '#28a745'
      case 'warning':
        return '#ffc107'
      case 'error':
        return '#dc3545'
      default:
        return '#6c757d'
    }
  }

  const getRiskColor = (risk: string) => {
    switch (risk) {
      case 'low':
        return '#28a745'
      case 'medium':
        return '#ffc107'
      case 'high':
        return '#dc3545'
      case 'critical':
        return '#721c24'
      default:
        return '#6c757d'
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h1>Agent 执行报告</h1>
      
      {reports.length === 0 ? (
        <div style={{ marginTop: '2rem', padding: '2rem', textAlign: 'center', color: '#666' }}>
          暂无 Agent 报告
        </div>
      ) : (
        <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          {reports.map((report, idx) => (
            <div
              key={idx}
              style={{
                padding: '1.5rem',
                border: '1px solid #ddd',
                borderRadius: '4px',
                backgroundColor: '#f8f9fa'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '1rem' }}>
                <h2 style={{ margin: 0 }}>{report.agent_name}</h2>
                <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
                  <span style={{
                    padding: '0.25rem 0.5rem',
                    backgroundColor: getStatusColor(report.status),
                    color: 'white',
                    borderRadius: '4px',
                    fontSize: '0.85em'
                  }}>
                    {report.status}
                  </span>
                  <span style={{
                    padding: '0.25rem 0.5rem',
                    backgroundColor: getRiskColor(report.risk_level),
                    color: 'white',
                    borderRadius: '4px',
                    fontSize: '0.85em'
                  }}>
                    {report.risk_level}
                  </span>
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
                <div>
                  <p><strong>决策:</strong> {report.decision}</p>
                  <p><strong>置信度:</strong> {(report.confidence * 100).toFixed(1)}%</p>
                </div>
                <div>
                  <p><strong>成本影响:</strong> {report.cost_impact.toFixed(2)}</p>
                  <p><strong>LLM Fallback:</strong> {report.llm_fallback_used ? '是' : '否'}</p>
                </div>
                {report.timestamp && (
                  <div>
                    <p><strong>时间:</strong> {new Date(report.timestamp).toLocaleString()}</p>
                  </div>
                )}
              </div>

              {/* 信号 */}
              {Object.keys(report.signals).length > 0 && (
                <details style={{ marginTop: '1rem' }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 'bold' }}>结构化信号</summary>
                  <pre style={{
                    marginTop: '0.5rem',
                    padding: '1rem',
                    backgroundColor: '#fff',
                    borderRadius: '4px',
                    overflow: 'auto',
                    fontSize: '0.85em'
                  }}>
                    {JSON.stringify(report.signals, null, 2)}
                  </pre>
                </details>
              )}

              {/* 冲突 */}
              {report.conflicts && report.conflicts.length > 0 && (
                <details style={{ marginTop: '1rem' }}>
                  <summary style={{ cursor: 'pointer', fontWeight: 'bold', color: '#dc3545' }}>
                    冲突 ({report.conflicts.length})
                  </summary>
                  <div style={{ marginTop: '0.5rem', padding: '1rem', backgroundColor: '#fff', borderRadius: '4px' }}>
                    {report.conflicts.map((conflict, cIdx) => (
                      <div key={cIdx} style={{ marginBottom: '0.5rem', padding: '0.5rem', backgroundColor: '#f8d7da', borderRadius: '4px' }}>
                        <pre style={{ margin: 0, fontSize: '0.85em' }}>
                          {JSON.stringify(conflict, null, 2)}
                        </pre>
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>
      )}

      <div style={{ marginTop: '2rem' }}>
        <a href={`/task/${taskId}`} style={{ padding: '0.5rem 1rem', backgroundColor: '#6c757d', color: 'white', textDecoration: 'none', borderRadius: '4px' }}>
          返回执行总览
        </a>
      </div>
    </div>
  )
}

export default AgentReports


