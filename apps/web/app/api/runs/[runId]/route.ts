import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

const DATA_DIR = path.join(process.cwd(), 'apps', 'web', 'data')
const RUNS_FILE = path.join(DATA_DIR, 'runs.json')

function ensureStore() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true })
  if (!fs.existsSync(RUNS_FILE)) fs.writeFileSync(RUNS_FILE, JSON.stringify({}), 'utf-8')
}

export async function GET(request: Request, { params }: { params: { runId: string } }) {
  ensureStore()
  const runs = JSON.parse(fs.readFileSync(RUNS_FILE, 'utf-8') || '{}')
  const id = params.runId
  if (!runs[id]) return NextResponse.json({ error: 'not found' }, { status: 404 })
  return NextResponse.json(runs[id])
}

export async function POST(request: Request, { params }: { params: { runId: string } }) {
  // replay endpoint - return a mocked replay report
  ensureStore()
  const report = {
    task_id: params.runId,
    replayed_at: new Date().toISOString(),
    num_agent_executions: 3,
    num_diffs: 0,
    consistent: true,
    diffs: []
  }
  return NextResponse.json(report)
}


