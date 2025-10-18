// Layout is now a simple container wrapper so pages control their own header/sidebar

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      {children}
    </div>
  )
}
