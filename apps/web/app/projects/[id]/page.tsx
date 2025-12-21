"use client"
import { useState, useEffect } from "react"
import { Run, Project } from "../../../types"
import Link from "next/link"

export default function ProjectPage({ params }: { params: { id: string } }) {
  const projectId = params.id
  const [project, setProject] = useState<Project | null>(null)
  const [file, setFile] = useState<File | null>(null)
  const [runs, setRuns] = useState<Run[]>([])
  const [query, setQuery] = useState("")
  const [lastAnswer, setLastAnswer] = useState<any>(null)

  useEffect(() => {
    fetch("/api/workbench/projects")
      .then((r) => r.json())
      .then((data) => {
        const p = data[projectId]
        setProject(p)
      })
    fetch("/api/workbench/runs")
      .then((r) => r.json())
      .then((data) => {
        const list = data ? Object.values(data) : []
        const filtered = list.filter((x: any) => x.project_id === projectId)
        setRuns(filtered)
      })
  }, [projectId])

  async function upload() {
    if (!file) return
    const form = new FormData()
    form.append("file", file)
    const res = await fetch(`/api/workbench/projects/${projectId}/ingest`, { method: "POST", body: form })
    const r = await res.json()
    setRuns((s) => [r, ...s])
  }

  async function runQuery() {
    const form = new FormData()
    form.append("query", query)
    const res = await fetch(`/api/workbench/projects/${projectId}/query`, { method: "POST", body: form })
    const r = await res.json()
    setLastAnswer(r)
    setRuns((s) => [r, ...s])
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{project ? project.name : "Project"}</h1>
        <Link href="/">Back</Link>
      </div>

      <div className="mt-4 bg-white p-4 rounded shadow">
        <h2 className="font-medium">Upload</h2>
        <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} className="mt-2" />
        <div className="mt-2">
          <button onClick={upload} className="px-3 py-2 bg-blue-600 text-white rounded">Upload & Ingest</button>
        </div>
      </div>

      <div className="mt-4 bg-white p-4 rounded shadow">
        <h2 className="font-medium">Query</h2>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ask a question" className="border p-2 rounded w-full" />
        <div className="mt-2">
          <button onClick={runQuery} className="px-3 py-2 bg-green-600 text-white rounded">Run</button>
        </div>
        {lastAnswer && (
          <div className="mt-4">
            <h3 className="font-medium">Answer</h3>
            <div className="mt-2 p-3 bg-gray-50 rounded">{lastAnswer.answer}</div>
            <h4 className="mt-3 font-medium">Evidence</h4>
            <ul className="mt-2">
              {lastAnswer.evidence?.map((e: any) => (
                <li key={e.id} className="border p-2 rounded mb-2">
                  <div className="text-sm text-gray-600">{e.source} — page {e.page}</div>
                  <div className="mt-1">{e.snippet}</div>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="mt-4">
        <h2 className="text-lg font-medium">Runs</h2>
        <ul className="mt-2 space-y-2">
          {runs.map((r) => (
            <li key={r.id} className="bg-white p-3 rounded shadow flex justify-between">
              <div>
                <div className="font-medium">{r.type} — {r.status}</div>
                <div className="text-sm text-gray-500">{r.created_at ?? r.createdAt}</div>
              </div>
              <a className="text-blue-600" href={`/runs/${r.id}`}>Open</a>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}


