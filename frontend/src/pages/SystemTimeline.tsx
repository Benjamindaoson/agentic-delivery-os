import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface TimelineEvent {
  type: string
  timestamp?: string
  agent?: string
  status?: string
  decision?: string
  checkpoint?: string
  execution_mode?: string
  reasoning?: string
  selected_plan_id?: string
  path_type?: string
  trigger?: string
}

function SystemTimeline() {
  const { taskId } = useParams<{ taskId: string }>()
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/events`)
        if (response.ok) {
          const data = await response.json()
          setEvents(data.events || [])
        }
      } catch (error) {
        console.error('Failed to fetch events:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchEvents()
    const interval = setInterval(fetchEvents, 2000)
    return () => clearInterval(interval)
  }, [taskId])

  if (loading) {
    return <div style={{ padding: '2rem' }}>加载中...</div>
  }

  const getEventIcon = (type: string) => {
    switch (type) {
      case 'agent_execution':
        return '🤖'
      case 'governance_decision':
        return '⚖️'
      case 'plan_selection':
        return '📋'
      default:
        return '•'
    }
  }

  const getEventColor = (type: string) => {
    switch (type) {
      case 'agent_execution':
        return '#007bff'
      case 'governance_decision':
        return '#28a745'
      case 'plan_selection':
        return '#ffc107'
      default:
        return '#6c757d'
    }
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h1>系统时间线</h1>
      
      {events.length === 0 ? (
        <div style={{ marginTop: '2rem', padding: '2rem', textAlign: 'center', color: '#666' }}>
          暂无事件
        </div>
      ) : (
        <div style={{ marginTop: '2rem', position: 'relative' }}>
          {/* 时间线 */}
          <div style={{
            position: 'absolute',
            left: '30px',
            top: 0,
            bottom: 0,
            width: '2px',
            backgroundColor: '#ddd'
          }} />
          
          {/* 事件列表 */}
          {events.map((event, idx) => (
            <div
              key={idx}
              style={{
                position: 'relative',
                marginBottom: '2rem',
                paddingLeft: '60px'
              }}
            >
              {/* 事件图标 */}
              <div style={{
                position: 'absolute',
                left: '20px',
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                backgroundColor: getEventColor(event.type),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: 'white',
                fontSize: '12px',
                fontWeight: 'bold'
              }}>
                {getEventIcon(event.type)}
              </div>

              {/* 事件内容 */}
              <div style={{
                padding: '1rem',
                backgroundColor: '#f8f9fa',
                border: `1px solid ${getEventColor(event.type)}`,
                borderRadius: '4px',
                borderLeftWidth: '4px'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                  <div>
                    <h3 style={{ margin: 0, marginBottom: '0.5rem' }}>
                      {event.type === 'agent_execution' && `Agent 执行: ${event.agent}`}
                      {event.type === 'governance_decision' && `治理决策: ${event.checkpoint}`}
                      {event.type === 'plan_selection' && `计划选择: ${event.selected_plan_id}`}
                    </h3>
                    
                    {event.type === 'agent_execution' && (
                      <div>
                        <p><strong>状态:</strong> {event.status}</p>
                        {event.decision && <p><strong>决策:</strong> {event.decision}</p>}
                      </div>
                    )}
                    
                    {event.type === 'governance_decision' && (
                      <div>
                        <p><strong>执行模式:</strong> {event.execution_mode}</p>
                        {event.reasoning && (
                          <details style={{ marginTop: '0.5rem' }}>
                            <summary>决策理由</summary>
                            <p style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: '#fff', borderRadius: '4px' }}>
                              {event.reasoning}
                            </p>
                          </details>
                        )}
                      </div>
                    )}
                    
                    {event.type === 'plan_selection' && (
                      <div>
                        <p><strong>路径类型:</strong> {event.path_type}</p>
                        {event.trigger && <p><strong>触发:</strong> {event.trigger}</p>}
                        {event.reasoning && (
                          <details style={{ marginTop: '0.5rem' }}>
                            <summary>选择理由</summary>
                            <p style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: '#fff', borderRadius: '4px' }}>
                              {event.reasoning}
                            </p>
                          </details>
                        )}
                      </div>
                    )}
                  </div>
                  
                  {event.timestamp && (
                    <div style={{ fontSize: '0.85em', color: '#666', whiteSpace: 'nowrap' }}>
                      {new Date(event.timestamp).toLocaleString()}
                    </div>
                  )}
                </div>
              </div>
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

export default SystemTimeline


