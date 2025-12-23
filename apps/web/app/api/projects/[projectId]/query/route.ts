import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

const DATA_DIR = path.join(process.cwd(), 'apps', 'web', 'data')
const RUNS_FILE = path.join(DATA_DIR, 'runs.json')

function ensureStore() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true })
  if (!fs.existsSync(RUNS_FILE)) fs.writeFileSync(RUNS_FILE, JSON.stringify({}), 'utf-8')
}

export async function POST(request: Request, { params }: { params: { projectId: string } }) {
  ensureStore()
  const form = await request.formData()
  const query = form.get('query') as string
  const runs = JSON.parse(fs.readFileSync(RUNS_FILE, 'utf-8') || '{}')
  const runId = `local-run-${Date.now()}`
  const evidence = [
    { id: `e-${Date.now()}`, source: 'local-doc.pdf', page: 1, snippet: '示例片段匹配查询', score: 0.9, rule_status: 'ok' }
  ]
  const run = {
    id: runId,
    project_id: params.projectId,
    type: 'query',
    status: 'completed',
    created_at: new Date().toISOString(),
    query,
    answer: '这是本地模拟的回答。',
    evidence,
    latency_ms: 75,
    cost: { estimate: 0.0 }
  }
  runs[runId] = run
  fs.writeFileSync(RUNS_FILE, JSON.stringify(runs, null, 2), 'utf-8')
  return NextResponse.json(run)
}


