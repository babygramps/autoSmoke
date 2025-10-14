import { useState, useEffect } from 'react'
import { Charts } from '../components/Charts'
import { Controls } from '../components/Controls'
import { Alarms } from '../components/Alarms'
import { SmokeSession } from '../components/SmokeSession'
import { apiClient, useWebSocket } from '../api/client'
import { ControllerStatus, Thermocouple } from '../types'

export function Dashboard() {
  const [status, setStatus] = useState<ControllerStatus | null>(null)
  const [units, setUnits] = useState<'F' | 'C'>('F')
  const [connected, setConnected] = useState(false)
  const [thermocouples, setThermocouples] = useState<Thermocouple[]>([])

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
        const [statusData, settingsData, thermocouplesData] = await Promise.all([
          apiClient.getStatus(),
          apiClient.getSettings(),
          apiClient.getThermocouples()
        ])
        setStatus(statusData)
        setUnits(settingsData.units)
        setThermocouples(thermocouplesData.thermocouples.sort((a, b) => a.order - b.order))
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

      {/* Thermocouple Readings */}
      {status && thermocouples.length > 0 && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">🌡️ Temperature Readings</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {thermocouples
              .filter(tc => tc.enabled)
              .map(tc => {
                const reading = status.thermocouple_readings?.[tc.id]
                const isControl = tc.id === status.control_tc_id
                const temp = reading ? (units === 'F' ? reading.temp_f : reading.temp_c) : null
                
                return (
                  <div 
                    key={tc.id}
                    className={`p-4 rounded-lg border-2 ${
                      isControl 
                        ? 'border-primary-500 bg-primary-50' 
                        : 'border-gray-200 bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <div 
                          className="w-3 h-3 rounded-full" 
                          style={{ backgroundColor: tc.color }}
                        />
                        <h4 className="font-semibold text-gray-900">{tc.name}</h4>
                      </div>
                      {isControl && (
                        <span className="text-xs px-2 py-1 rounded-full bg-primary-100 text-primary-800 font-medium">
                          CONTROL
                        </span>
                      )}
                    </div>
                    
                    {reading && !reading.fault ? (
                      <div className="text-3xl font-bold text-gray-900">
                        {temp?.toFixed(1)}°{units}
                      </div>
                    ) : reading?.fault ? (
                      <div className="text-lg font-semibold text-danger-600">
                        ⚠️ FAULT
                      </div>
                    ) : (
                      <div className="text-lg text-gray-500">
                        No reading
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
          
          {/* Status Badges */}
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
            <div className="text-sm text-gray-600">
              Target: {units === 'F' ? status.setpoint_f.toFixed(1) : status.setpoint_c.toFixed(1)}°{units}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
