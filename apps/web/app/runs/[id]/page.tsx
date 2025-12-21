"use client"
import { useEffect, useState } from "react"
import { useRouter } from "next/navigation"

export default function RunPage({ params }: { params: { id: string } }) {
  const runId = params.id
  const [run, setRun] = useState<any>(null)
  const [report, setReport] = useState<any>(null)

  useEffect(() => {
    fetch(`/api/workbench/runs/${runId}`).then((r) => r.json()).then(setRun)
  }, [runId])

  async function doReplay() {
    const res = await fetch(`/api/workbench/runs/${runId}/replay`, { method: "POST" })
    const j = await res.json()
    setReport(j)
  }

  if (!run) return <div>Loading...</div>

  return (
    <div>
      <h1 className="text-xl font-semibold">Run {run.id}</h1>
      <div className="mt-3 bg-white p-4 rounded shadow">
        <div><strong>Type:</strong> {run.type}</div>
        <div><strong>Status:</strong> {run.status}</div>
        <div><strong>Created:</strong> {run.created_at ?? run.createdAt}</div>
      </div>

      <div className="mt-4">
        <button onClick={doReplay} className="px-3 py-2 bg-indigo-600 text-white rounded">Replay</button>
      </div>

      {report && (
        <div className="mt-4 bg-white p-4 rounded shadow">
          <h2 className="font-medium">Replay Report</h2>
          <pre className="mt-2 text-sm">{JSON.stringify(report, null, 2)}</pre>
        </div>
      )}
    </div>
  )
}


