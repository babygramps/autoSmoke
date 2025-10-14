import { useState, useEffect } from 'react'
import { apiClient, useWebSocket } from '../api/client'
import { ControllerStatus } from '../types'

export function Header() {
  const [status, setStatus] = useState<ControllerStatus | null>(null)
  const [connected, setConnected] = useState(false)

  // WebSocket connection for real-time updates
  const { connect } = useWebSocket((data) => {
    if (data.type === 'telemetry') {
      setStatus(data.data)
      setConnected(true)
    }
  })

  useEffect(() => {
    // Connect to WebSocket
    const ws = connect()
    
    // Also fetch initial status
    const fetchStatus = async () => {
      try {
        const initialStatus = await apiClient.getStatus()
        setStatus(initialStatus)
      } catch (error) {
        console.error('Failed to fetch initial status:', error)
      }
    }
    
    fetchStatus()

    return () => {
      ws?.close()
    }
  }, [])

  const getStatusColor = () => {
    if (!status) return 'bg-gray-500'
    if (status.running) return 'bg-success-500'
    if (status.boost_active) return 'bg-warning-500'
    return 'bg-gray-500'
  }

  const getStatusText = () => {
    if (!status) return 'Disconnected'
    if (status.boost_active) return 'Boost Active'
    if (status.running) return 'Running'
    return 'Stopped'
  }

  const getConnectionStatus = () => {
    return connected ? 'Connected' : 'Disconnected'
  }

  const getConnectionColor = () => {
    return connected ? 'text-success-600' : 'text-danger-600'
  }

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold text-gray-900">Smoker Controller</h1>
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${getStatusColor()}`}></div>
              <span className="text-sm font-medium text-gray-700">
                {getStatusText()}
              </span>
            </div>
          </div>
          
          <div className="flex items-center space-x-6">
            {/* Temperature display */}
            {status && status.current_temp_f && (
              <div className="text-right">
                <div className="text-2xl font-bold text-gray-900">
                  {status.current_temp_f.toFixed(1)}°F
                </div>
                <div className="text-sm text-gray-500">
                  Target: {status.setpoint_f.toFixed(1)}°F
                </div>
              </div>
            )}
            
            {/* Connection status */}
            <div className="text-right">
              <div className={`text-sm font-medium ${getConnectionColor()}`}>
                {getConnectionStatus()}
              </div>
              <div className="text-xs text-gray-500">
                WebSocket
              </div>
            </div>
            
            {/* Alert indicator */}
            {status && status.alert_summary.count > 0 && (
              <div className="flex items-center space-x-1">
                <div className="w-2 h-2 bg-danger-500 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-danger-600">
                  {status.alert_summary.count} alert{status.alert_summary.count !== 1 ? 's' : ''}
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
