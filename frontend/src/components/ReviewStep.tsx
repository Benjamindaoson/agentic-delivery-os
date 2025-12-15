import { DeliverySpec } from '../types'

interface ReviewStepProps {
  spec: DeliverySpec
  onBack: () => void
  onSubmit: () => void
}

function ReviewStep({ spec, onBack, onSubmit }: ReviewStepProps) {
  return (
    <div>
      <h2>Review - 确认交付规格</h2>
      <div style={{ marginTop: '2rem', marginBottom: '2rem' }}>
        <p>关键决策项（骨架实现）</p>
        <pre style={{ background: '#f5f5f5', padding: '1rem', borderRadius: '6px' }}>
{JSON.stringify(spec, null, 2)}
        </pre>
        <p>风险与成本提示（骨架实现）</p>
        <p>上线与回滚摘要（骨架实现）</p>
      </div>
      <div style={{ display: 'flex', gap: '1rem' }}>
        <button onClick={onBack}>返回修改</button>
        <button onClick={onSubmit}>确认并提交</button>
      </div>
    </div>
  )
}

export default ReviewStep


