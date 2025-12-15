import { useParams } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface PlanNode {
  node_id: string
  agent_name: string
  description: string
  condition_type: string
  condition_rule: string
  required: boolean
  cost_estimate: number
  risk_level: string
}

interface ExecutionPlan {
  plan_id: string
  plan_version: string
  path_type: string
  description: string
  nodes: PlanNode[]
}

interface ExecutedNode {
  node_id: string
  agent_name: string
  timestamp?: string
}

interface PlanSelection {
  selected_plan_id: string
  selected_plan_version: string
  path_type: string
  reasoning: string
  governance_mode: string
  signals_used: Record<string, any>
  trigger?: string
}

interface TraceData {
  execution_plan: {
    plan_id: string
    plan_version: string
    path_type: string
    plan_definition?: ExecutionPlan
    plan_selection_history: PlanSelection[]
    executed_nodes: ExecutedNode[]
    conditions_evidence: Record<string, any>
  }
}

function ExecutionPlanDAG() {
  const { taskId } = useParams<{ taskId: string }>()
  const [traceData, setTraceData] = useState<TraceData | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchTrace = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/trace`)
        if (response.ok) {
          const data = await response.json()
          setTraceData(data)
        }
      } catch (error) {
        console.error('Failed to fetch trace:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchTrace()
  }, [taskId])

  if (loading) {
    return <div style={{ padding: '2rem' }}>加载中...</div>
  }

  if (!traceData || !traceData.execution_plan) {
    return <div style={{ padding: '2rem' }}>执行计划数据不存在</div>
  }

  const { execution_plan } = traceData
  const planDef = execution_plan.plan_definition
  const executedNodeIds = new Set(execution_plan.executed_nodes.map(n => n.node_id))
  const conditionsEvidence = execution_plan.conditions_evidence || {}

  return (
    <div style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      <h1>执行计划 DAG 可视化</h1>
      
      {/* 计划选择历史 */}
      <div style={{ marginTop: '2rem', marginBottom: '2rem' }}>
        <h2>计划选择历史</h2>
        {execution_plan.plan_selection_history.map((selection, idx) => (
          <div key={idx} style={{ 
            padding: '1rem', 
            marginBottom: '1rem', 
            border: '1px solid #ddd', 
            borderRadius: '4px',
            backgroundColor: selection.trigger ? '#fff3cd' : '#f8f9fa'
          }}>
            <p><strong>选择 #{idx + 1}:</strong> {selection.selected_plan_id} ({selection.path_type})</p>
            <p><strong>理由:</strong> {selection.reasoning}</p>
            {selection.trigger && (
              <p><strong>触发:</strong> {selection.trigger}</p>
            )}
            <p><strong>治理模式:</strong> {selection.governance_mode}</p>
            {Object.keys(selection.signals_used).length > 0 && (
              <details style={{ marginTop: '0.5rem' }}>
                <summary>使用的信号</summary>
                <pre style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: '#f0f0f0', borderRadius: '4px' }}>
                  {JSON.stringify(selection.signals_used, null, 2)}
                </pre>
              </details>
            )}
          </div>
        ))}
      </div>

      {/* DAG 可视化 */}
      {planDef && (
        <div style={{ marginTop: '2rem' }}>
          <h2>执行计划 DAG: {planDef.plan_id} ({planDef.path_type})</h2>
          <p>{planDef.description}</p>
          
          <div style={{ 
            marginTop: '2rem', 
            display: 'grid', 
            gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', 
            gap: '1rem' 
          }}>
            {planDef.nodes.map((node) => {
              const isExecuted = executedNodeIds.has(node.node_id)
              const evidence = conditionsEvidence[node.agent_name] || {}
              
              return (
                <div
                  key={node.node_id}
                  style={{
                    padding: '1rem',
                    border: `2px solid ${isExecuted ? '#28a745' : '#dc3545'}`,
                    borderRadius: '4px',
                    backgroundColor: isExecuted ? '#d4edda' : '#f8d7da',
                    opacity: isExecuted ? 1 : 0.6
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0 }}>{node.agent_name}</h3>
                    {isExecuted ? (
                      <span style={{ color: 'green', fontWeight: 'bold' }}>✓ 已执行</span>
                    ) : (
                      <span style={{ color: 'red', fontWeight: 'bold' }}>✗ 未执行</span>
                    )}
                  </div>
                  <p style={{ marginTop: '0.5rem', fontSize: '0.9em', color: '#666' }}>
                    {node.description}
                  </p>
                  
                  <div style={{ marginTop: '0.5rem', fontSize: '0.85em' }}>
                    <p><strong>节点ID:</strong> {node.node_id}</p>
                    <p><strong>条件类型:</strong> {node.condition_type}</p>
                    <p><strong>条件规则:</strong> {node.condition_rule}</p>
                    <p><strong>必需:</strong> {node.required ? '是' : '否'}</p>
                    <p><strong>成本估算:</strong> {node.cost_estimate}</p>
                    <p><strong>风险级别:</strong> {node.risk_level}</p>
                  </div>

                  {/* 条件证据 */}
                  {Object.keys(evidence).length > 0 && (
                    <details style={{ marginTop: '0.5rem' }}>
                      <summary>条件证据</summary>
                      <pre style={{ marginTop: '0.5rem', padding: '0.5rem', backgroundColor: '#f0f0f0', borderRadius: '4px', fontSize: '0.8em' }}>
                        {JSON.stringify(evidence, null, 2)}
                      </pre>
                    </details>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* 执行节点序列 */}
      <div style={{ marginTop: '2rem' }}>
        <h2>实际执行序列</h2>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '1rem' }}>
          {execution_plan.executed_nodes.map((node, idx) => (
            <div
              key={idx}
              style={{
                padding: '0.5rem 1rem',
                backgroundColor: '#007bff',
                color: 'white',
                borderRadius: '4px',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              <span>{idx + 1}.</span>
              <span>{node.agent_name}</span>
              {node.timestamp && (
                <span style={{ fontSize: '0.8em', opacity: 0.8 }}>
                  ({new Date(node.timestamp).toLocaleTimeString()})
                </span>
              )}
            </div>
          ))}
        </div>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <a href={`/task/${taskId}`} style={{ padding: '0.5rem 1rem', backgroundColor: '#6c757d', color: 'white', textDecoration: 'none', borderRadius: '4px' }}>
          返回执行总览
        </a>
      </div>
    </div>
  )
}

export default ExecutionPlanDAG


