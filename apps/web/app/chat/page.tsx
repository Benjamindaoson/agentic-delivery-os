"use client"
import { useState } from "react"

export default function ChatPage() {
  const [projectId, setProjectId] = useState("")
  const [query, setQuery] = useState("")
  const [answer, setAnswer] = useState<any>(null)

  async function run() {
    const form = new FormData()
    form.append("query", query)
    const res = await fetch(`/api/workbench/projects/${projectId}/query`, { method: "POST", body: form })
    const j = await res.json()
    setAnswer(j)
  }

  return (
    <div>
      <h1 className="text-xl font-semibold">Chat</h1>
      <div className="mt-3 bg-white p-4 rounded shadow">
        <input placeholder="Project ID" value={projectId} onChange={(e) => setProjectId(e.target.value)} className="border p-2 rounded w-full" />
        <textarea placeholder="Ask a question..." value={query} onChange={(e) => setQuery(e.target.value)} className="border p-2 rounded w-full mt-2" />
        <div className="mt-2">
          <button onClick={run} className="px-3 py-2 bg-green-600 text-white rounded">Ask</button>
        </div>
      </div>

      {answer && (
        <div className="mt-4 bg-white p-4 rounded shadow">
          <h3 className="font-medium">Answer</h3>
          <div className="mt-2">{answer.answer}</div>
          <h4 className="mt-3 font-medium">Evidence</h4>
          <ul>
            {answer.evidence?.map((e: any) => (
              <li key={e.id} className="border p-2 rounded mb-2">
                <div className="text-sm text-gray-600">{e.source} - page {e.page}</div>
                <div>{e.snippet}</div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}


