"use client"
import { useState } from "react"

export default function Upload({ projectId }: { projectId: string }) {
  const [file, setFile] = useState<File | null>(null)
  const [status, setStatus] = useState<string | null>(null)

  async function upload() {
    if (!file) return
    const form = new FormData()
    form.append("file", file)
    setStatus("Uploading...")
    const res = await fetch(`/api/projects/${projectId}/ingest`, { method: "POST", body: form })
    const j = await res.json()
    setStatus(`Completed: ${j.id}`)
  }

  return (
    <div>
      <input type="file" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
      <button onClick={upload} className="ml-2 px-2 py-1 bg-blue-600 text-white rounded">Upload</button>
      {status && <div className="mt-2 text-sm text-gray-600">{status}</div>}
    </div>
  )
}


