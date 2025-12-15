import { DeliverySpec } from '../types'

interface WizardStepProps {
  step: number
  stepData: Partial<DeliverySpec>
  onNext: (data: Partial<DeliverySpec>) => void
  onBack?: () => void
}

function WizardStep({ step, stepData, onNext, onBack }: WizardStepProps) {
  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    const data: Partial<DeliverySpec> = {}
    // TODO: 根据step收集对应字段
    onNext(data)
  }

  return (
    <form onSubmit={handleSubmit}>
      <div style={{ marginBottom: '1rem' }}>
        <p>步骤 {step + 1} 的内容（骨架实现）</p>
        <pre style={{ background: '#f5f5f5', padding: '0.75rem', borderRadius: '6px' }}>
{JSON.stringify(stepData || {}, null, 2)}
        </pre>
      </div>
      <div style={{ display: 'flex', gap: '1rem', marginTop: '2rem' }}>
        {onBack && (
          <button type="button" onClick={onBack}>
            上一步
          </button>
        )}
        <button type="submit">
          {step === 3 ? '下一步（Review）' : '下一步'}
        </button>
      </div>
    </form>
  )
}

export default WizardStep


