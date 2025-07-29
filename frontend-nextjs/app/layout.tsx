import type { Metadata, Viewport } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'YouTube Summary Bot',
  description: 'AI-powered YouTube video summarization with Discord integration',
  keywords: ['youtube', 'ai', 'summarization', 'discord', 'automation'],
  authors: [{ name: 'YouTube Summary Bot' }],
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background font-sans antialiased">
        <div id="root" className="min-h-screen">
          {children}
        </div>
      </body>
    </html>
  )
}
