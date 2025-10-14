import { useState, useEffect } from 'react'
import { Charts } from '../components/Charts'
import { Controls } from '../components/Controls'
import { Alarms } from '../components/Alarms'
import { SmokeSession } from '../components/SmokeSession'
import { apiClient, useWebSocket } from '../api/client'
import { ControllerStatus } from '../types'

export function Dashboard() {
  const [status, setStatus] = useState<ControllerStatus | null>(null)
  const [units, setUnits] = useState<'F' | 'C'>('F')
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
    
    // Fetch initial status and settings
    const fetchInitialData = async () => {
      try {
        const [statusData, settingsData] = await Promise.all([
          apiClient.getStatus(),
          apiClient.getSettings()
        ])
        setStatus(statusData)
        setUnits(settingsData.units)
      } catch (error) {
        console.error('Failed to fetch initial data:', error)
      }
    }
    
    fetchInitialData()

    return () => {
      ws?.close()
    }
  }, [])

  const handleStatusUpdate = (newStatus: ControllerStatus) => {
    setStatus(newStatus)
  }

  const handleAlertUpdate = () => {
    // Refresh status to get updated alert summary
    apiClient.getStatus().then(setStatus).catch(console.error)
  }

  const handleSessionChange = () => {
    // Refresh status when session changes
    apiClient.getStatus().then(setStatus).catch(console.error)
  }

  return (
    <div className="space-y-6">
      {/* Connection Status */}
      <div className="card">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className={`w-3 h-3 rounded-full ${connected ? 'bg-success-500' : 'bg-danger-500'}`}></div>
            <span className="text-sm font-medium text-gray-700">
              {connected ? 'Connected' : 'Disconnected'}
            </span>
          </div>
          <div className="text-sm text-gray-500">
            Last updated: {status ? new Date().toLocaleTimeString() : 'Never'}
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Controls and Session */}
        <div className="space-y-6">
          <Controls status={status} onStatusUpdate={handleStatusUpdate} />
          <SmokeSession onSessionChange={handleSessionChange} />
        </div>

        {/* Middle Column - Chart */}
        <div className="lg:col-span-2">
          <Charts status={status} units={units} smokeId={status?.active_smoke_id || undefined} />
        </div>
      </div>

      {/* Alarms Row */}
      <Alarms alertSummary={status?.alert_summary || null} onAlertUpdate={handleAlertUpdate} />

      {/* Temperature Display */}
      {status && status.current_temp_f && (
        <div className="card">
          <div className="text-center">
            <div className="text-6xl font-bold text-gray-900 mb-2">
              {units === 'F' ? status.current_temp_f.toFixed(1) : status.current_temp_c?.toFixed(1)}°
              {units}
            </div>
            <div className="text-xl text-gray-600">
              Target: {units === 'F' ? status.setpoint_f.toFixed(1) : status.setpoint_c.toFixed(1)}°{units}
            </div>
            <div className="mt-4 flex items-center justify-center space-x-4">
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                status.running 
                  ? 'bg-success-100 text-success-800' 
                  : 'bg-gray-100 text-gray-800'
              }`}>
                {status.running ? 'Running' : 'Stopped'}
              </div>
              <div className={`px-3 py-1 rounded-full text-sm font-medium ${
                status.relay_state 
                  ? 'bg-warning-100 text-warning-800' 
                  : 'bg-gray-100 text-gray-800'
              }`}>
                Relay {status.relay_state ? 'ON' : 'OFF'}
              </div>
              {status.boost_active && (
                <div className="px-3 py-1 rounded-full text-sm font-medium bg-orange-100 text-orange-800">
                  Boost Active
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
