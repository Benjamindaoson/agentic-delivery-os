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
  const file = form.get('file') as any
  const runs = JSON.parse(fs.readFileSync(RUNS_FILE, 'utf-8') || '{}')
  const runId = `local-run-${Date.now()}`
  const run = {
    id: runId,
    project_id: params.projectId,
    type: 'ingest',
    status: 'completed',
    created_at: new Date().toISOString(),
    file_name: file?.name ?? 'uploaded'
  }
  runs[runId] = run
  fs.writeFileSync(RUNS_FILE, JSON.stringify(runs, null, 2), 'utf-8')
  return NextResponse.json(run)
}


