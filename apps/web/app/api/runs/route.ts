import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

const DATA_DIR = path.join(process.cwd(), 'apps', 'web', 'data')
const RUNS_FILE = path.join(DATA_DIR, 'runs.json')

function ensureStore() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true })
  if (!fs.existsSync(RUNS_FILE)) fs.writeFileSync(RUNS_FILE, JSON.stringify({}), 'utf-8')
}

export async function GET() {
  ensureStore()
  const runs = JSON.parse(fs.readFileSync(RUNS_FILE, 'utf-8') || '{}')
  return NextResponse.json(runs)
}


