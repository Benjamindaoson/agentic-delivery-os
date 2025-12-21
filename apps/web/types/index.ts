export type Project = {
  id: string
  name: string
  created_at?: string
}

export type EvidenceItem = {
  id: string
  source: string
  page: number
  snippet: string
  score?: number
  rule_status?: string
}

export type Run = {
  id: string
  project_id: string
  type: string
  status: string
  created_at?: string
  answer?: string
  evidence?: EvidenceItem[]
}


