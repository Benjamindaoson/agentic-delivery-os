\"use client\"
import { useState, useEffect } from 'react'
import { Project } from '../../types'

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([])
  const [name, setName] = useState('')

  useEffect(() => {
    fetch('/api/workbench/projects')
      .then((r) => r.json())
      .then((data) => {
        // data currently stored as object map
        const list = data && typeof data === 'object' ? Object.values(data) : []
        setProjects(list)
      })
  }, [])

  async function createProject() {
    const form = new FormData()
    form.append('name', name)
    const res = await fetch('/api/workbench/projects', { method: 'POST', body: form })
    const p = await res.json()
    setProjects((s) => [...s, p])
    setName('')
  }

  return (
    <div>
      <h1 className=\"text-xl font-semibold\">Projects</h1>
      <div className=\"mt-4\">
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder=\"Project name\" className=\"border p-2 rounded mr-2\" />
        <button onClick={createProject} className=\"px-3 py-2 bg-green-600 text-white rounded\">Create</button>
      </div>
      <ul className=\"mt-6 space-y-3\">
        {projects.map((p) => (
          <li key={p.id} className=\"bg-white p-4 rounded shadow flex justify-between items-center\">
            <div>
              <div className=\"font-medium\">{p.name}</div>
              <div className=\"text-sm text-gray-500\">{p.created_at}</div>
            </div>
            <a className=\"text-blue-600\" href={`/projects/${p.id}`}>Open</a>
          </li>
        ))}
      </ul>
    </div>
  )
}


