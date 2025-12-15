export interface DeliverySpec {
  audience?: string
  answerStyle?: 'Strict' | 'Balanced' | 'Exploratory'
  mustCite?: boolean
  dataSourceType?: string
  deploymentChannel?: 'API' | 'Web' | 'Internal'
  sloBudget?: {
    latency?: number
    cost?: number
    quality?: number
  }
}

export interface TaskStatus {
  taskId: string
  state: 'IDLE' | 'SPEC_READY' | 'RUNNING' | 'FAILED' | 'COMPLETED'
  error?: string
  progress?: {
    currentAgent?: string
    currentStep?: string
  }
}


