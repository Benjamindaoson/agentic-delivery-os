import './globals.css'

export const metadata = {
  title: 'Agentic Workbench',
  description: 'Minimal Workbench UI for Agentic Delivery OS'
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50 text-gray-900">
        <div className="max-w-5xl mx-auto p-6">{children}</div>
      </body>
    </html>
  )
}


