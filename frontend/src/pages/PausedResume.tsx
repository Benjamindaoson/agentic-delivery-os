import { useParams, useNavigate } from 'react-router-dom'
import { useState, useEffect } from 'react'

interface TaskStatus {
  state: string
  error?: string
}

function PausedResume() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [status, setStatus] = useState<TaskStatus | null>(null)
  const [inputData, setInputData] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(false)
  const [trace, setTrace] = useState<any>(null)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/status`)
        if (response.ok) {
          const data = await response.json()
          setStatus(data)
          
          // 如果状态不是 PAUSED，重定向到总览页
          if (data.state !== 'PAUSED') {
            navigate(`/task/${taskId}`)
          }
        }
      } catch (error) {
        console.error('Failed to fetch status:', error)
      }
    }
    fetchStatus()
    
    // 获取 trace 以了解暂停原因
    const fetchTrace = async () => {
      try {
        const response = await fetch(`/api/task/${taskId}/trace`)
        if (response.ok) {
          const data = await response.json()
          setTrace(data)
        }
      } catch (error) {
        console.error('Failed to fetch trace:', error)
      }
    }
    fetchTrace()
  }, [taskId, navigate])

  const handleInputChange = (key: string, value: any) => {
    setInputData({ ...inputData, [key]: value })
  }

  const handleSubmitInput = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/task/${taskId}/input`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(inputData)
      })
      if (response.ok) {
        alert('输入已提交')
        setInputData({})
      } else {
        alert('提交失败')
      }
    } catch (error) {
      console.error('Failed to submit input:', error)
      alert('提交失败')
    } finally {
      setLoading(false)
    }
  }

  const handleResume = async () => {
    setLoading(true)
    try {
      const response = await fetch(`/api/task/${taskId}/resume`, {
        method: 'POST'
      })
      if (response.ok) {
        navigate(`/task/${taskId}`)
      } else {
        alert('恢复失败')
      }
    } catch (error) {
      console.error('Failed to resume:', error)
      alert('恢复失败')
    } finally {
      setLoading(false)
    }
  }

  if (!status || status.state !== 'PAUSED') {
    return <div style={{ padding: '2rem' }}>加载中...</div>
  }

  // 从 trace 中提取暂停原因
  const lastGovDecision = trace?.governance_decisions?.slice(-1)[0]
  const pauseReason = lastGovDecision?.reasoning || status.error || '未知原因'

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>任务已暂停</h1>
      
      <div style={{ marginTop: '2rem', padding: '1.5rem', backgroundColor: '#fff3cd', border: '1px solid #ffc107', borderRadius: '4px' }}>
        <h2>暂停原因</h2>
        <p>{pauseReason}</p>
        
        {lastGovDecision && (
          <details style={{ marginTop: '1rem' }}>
            <summary>详细信息</summary>
            <pre style={{ marginTop: '0.5rem', padding: '1rem', backgroundColor: '#fff', borderRadius: '4px', overflow: 'auto' }}>
              {JSON.stringify(lastGovDecision, null, 2)}
            </pre>
          </details>
        )}
      </div>

      <div style={{ marginTop: '2rem' }}>
        <h2>补充信息</h2>
        <p>请提供以下信息以继续执行：</p>
        
        <div style={{ marginTop: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div>
            <label>
              <strong>缺失字段 1:</strong>
              <input
                type="text"
                value={inputData.field1 || ''}
                onChange={(e) => handleInputChange('field1', e.target.value)}
                style={{ width: '100%', padding: '0.5rem', marginTop: '0.5rem', border: '1px solid #ddd', borderRadius: '4px' }}
                placeholder="请输入..."
              />
            </label>
          </div>
          
          <div>
            <label>
              <strong>缺失字段 2:</strong>
              <input
                type="text"
                value={inputData.field2 || ''}
                onChange={(e) => handleInputChange('field2', e.target.value)}
                style={{ width: '100%', padding: '0.5rem', marginTop: '0.5rem', border: '1px solid #ddd', borderRadius: '4px' }}
                placeholder="请输入..."
              />
            </label>
          </div>
        </div>

        <div style={{ marginTop: '1.5rem', display: 'flex', gap: '1rem' }}>
          <button
            onClick={handleSubmitInput}
            disabled={loading || Object.keys(inputData).length === 0}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#007bff',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: loading || Object.keys(inputData).length === 0 ? 'not-allowed' : 'pointer',
              opacity: loading || Object.keys(inputData).length === 0 ? 0.5 : 1
            }}
          >
            提交输入
          </button>
        </div>
      </div>

      <div style={{ marginTop: '2rem', padding: '1.5rem', backgroundColor: '#f8f9fa', border: '1px solid #ddd', borderRadius: '4px' }}>
        <h2>恢复执行</h2>
        <p>补充信息后，点击下方按钮恢复任务执行：</p>
        <button
          onClick={handleResume}
          disabled={loading}
          style={{
            marginTop: '1rem',
            padding: '0.75rem 1.5rem',
            backgroundColor: '#28a745',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: loading ? 'not-allowed' : 'pointer',
            fontSize: '1em',
            fontWeight: 'bold'
          }}
        >
          {loading ? '处理中...' : '恢复执行'}
        </button>
      </div>

      <div style={{ marginTop: '2rem' }}>
        <a href={`/task/${taskId}`} style={{ padding: '0.5rem 1rem', backgroundColor: '#6c757d', color: 'white', textDecoration: 'none', borderRadius: '4px' }}>
          返回执行总览
        </a>
      </div>
    </div>
  )
}

export default PausedResume


