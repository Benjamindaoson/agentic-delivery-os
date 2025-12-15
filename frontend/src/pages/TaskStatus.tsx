import { useParams, useNavigate, Navigate } from 'react-router-dom'
import { useState, useEffect } from 'react'
import { TaskStatus as TaskStatusType } from '../types'

function TaskStatus() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [status, setStatus] = useState<TaskStatusType | null>(null)

  useEffect(() => {
    const fetchStatus = async () => {
      const response = await fetch(`/api/task/${taskId}/status`)
      if (response.ok) {
        const data = await response.json()
        setStatus(data)
        
        // 如果状态是 PAUSED，重定向到暂停页面
        if (data.state === 'PAUSED') {
          navigate(`/task/${taskId}/paused`)
        } else {
          // 否则重定向到执行总览
          navigate(`/task/${taskId}/overview`)
        }
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 2000)
    return () => clearInterval(interval)
  }, [taskId, navigate])

  if (!status) {
    return <div style={{ padding: '2rem' }}>加载中...</div>
  }

  // 默认重定向到执行总览
  return <Navigate to={`/task/${taskId}/overview`} replace />
}

export default TaskStatus

