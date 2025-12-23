import { NextResponse } from 'next/server'
import fs from 'fs'
import path from 'path'

const DATA_DIR = path.join(process.cwd(), 'apps', 'web', 'data')
const PROJECTS_FILE = path.join(DATA_DIR, 'projects.json')

function ensureStore() {
  if (!fs.existsSync(DATA_DIR)) fs.mkdirSync(DATA_DIR, { recursive: true })
  if (!fs.existsSync(PROJECTS_FILE)) fs.writeFileSync(PROJECTS_FILE, JSON.stringify({}), 'utf-8')
}

export async function GET() {
  ensureStore()
  const raw = fs.readFileSync(PROJECTS_FILE, 'utf-8')
  const data = JSON.parse(raw || '{}')
  return NextResponse.json(data)
}

export async function POST(request: Request) {
  ensureStore()
  const form = await request.formData()
  const name = form.get('name') || `project-${Date.now()}`
  const projects = JSON.parse(fs.readFileSync(PROJECTS_FILE, 'utf-8') || '{}')
  const id = `local-${Date.now()}`
  projects[id] = { id, name, created_at: new Date().toISOString() }
  fs.writeFileSync(PROJECTS_FILE, JSON.stringify(projects, null, 2), 'utf-8')
  return NextResponse.json(projects[id])
}


