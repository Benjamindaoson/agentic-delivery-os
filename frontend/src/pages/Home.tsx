import { useNavigate } from 'react-router-dom'

function Home() {
  const navigate = useNavigate()

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Agentic AI Delivery OS</h1>
      <p style={{ marginTop: '1rem', marginBottom: '2rem' }}>
        多智能体 AI 工程交付系统
      </p>
      <button
        onClick={() => navigate('/wizard')}
        style={{
          padding: '0.75rem 1.5rem',
          fontSize: '1rem',
          cursor: 'pointer'
        }}
      >
        创建新任务
      </button>
    </div>
  )
}

export default Home


