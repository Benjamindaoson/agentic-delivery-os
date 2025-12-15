import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface ToolExecution {
  tool_name: string
  success: boolean
  output_summary?: string
  error?: string
  exit_code: number
  execution_time_ms: number
  validated: boolean
  degrade_triggered: boolean
  rollback_triggered: boolean
  timestamp: string
}

interface TraceData {
  tool_executions: ToolExecution[]
  agent_executions: Array<{
    agent: string
    tool_executions?: ToolExecution[]
  }>
}

function ToolExecutions() {
  const { taskId } = useParams<{ taskId: string }>()
  const [toolExecutions, setToolExecutions] = useState<ToolExecution[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchToolExecutions = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/trace`)
        if (response.ok) {
          const data: TraceData = await response.json()
          // 合并全局工具执行和 Agent 中的工具执行
          const allTools: ToolExecution[] = []
          if (data.tool_executions) {
            allTools.push(...data.tool_executions)
          }
          if (data.agent_executions) {
            data.agent_executions.forEach(agentExec => {
              if (agentExec.tool_executions) {
                allTools.push(...agentExec.tool_executions)
              }
            })
          }
          setToolExecutions(allTools)
        }
      } catch (error) {
        console.error('Failed to fetch tool executions:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchToolExecutions()
    const interval = setInterval(fetchToolExecutions, 2000)
    return () => clearInterval(interval)
  }, [taskId])

  if (loading) {
    return <div style={{ padding: '2rem' }}>加载中...</div>
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h1>工具调用与沙盒执行</h1>
      
      {toolExecutions.length === 0 ? (
        <div style={{ marginTop: '2rem', padding: '2rem', textAlign: 'center', color: '#666' }}>
          暂无工具调用记录
        </div>
      ) : (
        <div style={{ marginTop: '2rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {toolExecutions.map((tool, idx) => (
            <div
              key={idx}
              style={{
                padding: '1rem',
                border: `2px solid ${tool.success ? '#28a745' : '#dc3545'}`,
                borderRadius: '4px',
                backgroundColor: tool.success ? '#d4edda' : '#f8d7da'
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '0.5rem' }}>
                <h3 style={{ margin: 0 }}>{tool.tool_name}</h3>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                  {tool.success ? (
                    <span style={{ color: 'green', fontWeight: 'bold' }}>✓ 成功</span>
                  ) : (
                    <span style={{ color: 'red', fontWeight: 'bold' }}>✗ 失败</span>
                  )}
                  {tool.validated ? (
                    <span style={{ fontSize: '0.85em', color: '#666' }}>✓ 已验证</span>
                  ) : (
                    <span style={{ fontSize: '0.85em', color: '#dc3545' }}>✗ 未验证</span>
                  )}
                </div>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem', marginTop: '0.5rem', fontSize: '0.9em' }}>
                <p><strong>退出码:</strong> {tool.exit_code}</p>
                <p><strong>执行时间:</strong> {tool.execution_time_ms.toFixed(2)} ms</p>
                {tool.degrade_triggered && (
                  <p style={{ color: 'orange' }}><strong>⚠️ 触发降级</strong></p>
                )}
                {tool.rollback_triggered && (
                  <p style={{ color: 'red' }}><strong>⚠️ 触发回滚</strong></p>
                )}
                {tool.timestamp && (
                  <p><strong>时间:</strong> {new Date(tool.timestamp).toLocaleString()}</p>
                )}
              </div>

              {tool.output_summary && (
                <details style={{ marginTop: '0.5rem' }}>
                  <summary style={{ cursor: 'pointer' }}>输出摘要</summary>
                  <pre style={{
                    marginTop: '0.5rem',
                    padding: '0.5rem',
                    backgroundColor: '#fff',
                    borderRadius: '4px',
                    fontSize: '0.85em',
                    overflow: 'auto'
                  }}>
                    {tool.output_summary}
                  </pre>
                </details>
              )}

              {tool.error && (
                <div style={{
                  marginTop: '0.5rem',
                  padding: '0.5rem',
                  backgroundColor: '#f8d7da',
                  borderRadius: '4px',
                  color: '#721c24'
                }}>
                  <strong>错误:</strong> {tool.error}
                </div>
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

export default ToolExecutions


