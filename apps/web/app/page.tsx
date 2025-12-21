import Link from 'next/link'

export default function Page() {
  return (
    <main>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Agentic Workbench</h1>
        <nav className="space-x-4">
          <Link href="/projects" className="text-blue-600">Projects</Link>
          <Link href="/runs/"><span className="text-blue-600">Runs</span></Link>
        </nav>
      </div>

      <section className="mt-8 bg-white p-6 rounded shadow">
        <h2 className="text-lg font-medium">Quick actions</h2>
        <div className="mt-4 space-x-3">
          <Link href="/projects">
            <button className="px-4 py-2 bg-blue-600 text-white rounded">Create / Select Project</button>
          </Link>
          <Link href="/runs/">
            <button className="px-4 py-2 border rounded">View Runs</button>
          </Link>
        </div>
      </section>
    </main>
  )
}


