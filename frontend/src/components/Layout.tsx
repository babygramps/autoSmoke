import { Link, useLocation } from 'react-router-dom'

interface LayoutProps {
  children: React.ReactNode
}

export function Layout({ children }: LayoutProps) {
  const location = useLocation()
  const navItems = [
    { path: '/', label: 'Dashboard', icon: '📊' },
    { path: '/settings', label: 'Settings', icon: '⚙️' },
    { path: '/history', label: 'History', icon: '📈' },
  ]

  return (
    <div className="min-h-screen bg-gray-50 flex">
      {/* Left Nav Sidebar (sticky and persistent across all pages) */}
      <nav className="w-64 bg-white shadow-sm sticky top-0 h-screen overflow-y-auto">
        <div className="p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-6">PiTmaster</h2>
          <ul className="space-y-2">
            {navItems.map((item) => (
              <li key={item.path}>
                <Link
                  to={item.path}
                  className={`flex items-center px-4 py-2 rounded-lg transition-colors ${
                    location.pathname === item.path
                      ? 'bg-primary-100 text-primary-700 font-medium'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  <span className="mr-3">{item.icon}</span>
                  {item.label}
                </Link>
              </li>
            ))}
          </ul>
        </div>
      </nav>

      {/* Main content area */}
      <div className="flex-1">
        {children}
      </div>
    </div>
  )
}
