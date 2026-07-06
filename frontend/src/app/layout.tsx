import './globals.css'
import type { Metadata } from 'next'

export const metadata: Metadata = {
  title: 'Sonic Analytics | Discovery Overview',
  description: 'AI-Powered Feedback Dashboard',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet" />
        <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:wght,FILL@100..700,0..1&display=swap" rel="stylesheet" />
      </head>
      <body
        style={{
          display: 'flex',
          overflowY: 'auto',
          minHeight: '100vh',
          backgroundColor: 'var(--color-background)',
        }}
      >
        {children}
      </body>
    </html>
  )
}
