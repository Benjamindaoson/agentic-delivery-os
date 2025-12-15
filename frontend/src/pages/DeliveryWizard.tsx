import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import WizardStep from '../components/WizardStep'
import ReviewStep from '../components/ReviewStep'
import { DeliverySpec } from '../types'

const WIZARD_STEPS = [
  { id: 1, title: '场景与目标确认' },
  { id: 2, title: '数据源与范围确认' },
  { id: 3, title: '质量/成本/风险偏好' },
  { id: 4, title: '上线方式与回滚策略' }
]

function DeliveryWizard() {
  const [currentStep, setCurrentStep] = useState(0)
  const [spec, setSpec] = useState<Partial<DeliverySpec>>({})
  const [showReview, setShowReview] = useState(false)
  const navigate = useNavigate()

  const handleNext = (stepData: Partial<DeliverySpec>) => {
    setSpec({ ...spec, ...stepData })
    if (currentStep < WIZARD_STEPS.length - 1) {
      setCurrentStep(currentStep + 1)
    } else {
      setShowReview(true)
    }
  }

  const handleBack = () => {
    if (showReview) {
      setShowReview(false)
    } else if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSubmit = async () => {
    // TODO: 调用后端API提交Spec
    const response = await fetch('/api/delivery/submit', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(spec)
    })
    const result = await response.json()
    navigate(`/task/${result.taskId}`)
  }

  if (showReview) {
    return (
      <ReviewStep
        spec={spec as DeliverySpec}
        onBack={handleBack}
        onSubmit={handleSubmit}
      />
    )
  }

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>创建交付任务</h1>
      <div style={{ marginTop: '1rem', marginBottom: '2rem' }}>
        <div style={{ display: 'flex', gap: '1rem' }}>
          {WIZARD_STEPS.map((step, idx) => (
            <div
              key={step.id}
              style={{
                flex: 1,
                padding: '0.5rem',
                backgroundColor: idx <= currentStep ? '#e0e0e0' : '#f5f5f5',
                textAlign: 'center',
                borderRadius: '4px'
              }}
            >
              {step.title}
            </div>
          ))}
        </div>
      </div>
      <WizardStep
        step={currentStep}
        stepData={spec}
        onNext={handleNext}
        onBack={currentStep > 0 ? handleBack : undefined}
      />
    </div>
  )
}

export default DeliveryWizard


