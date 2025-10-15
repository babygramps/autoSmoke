import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { ControllerStatus } from '../types'

interface ControlsProps {
  status: ControllerStatus | null
  onStatusUpdate: (status: ControllerStatus) => void
}

export function Controls({ status, onStatusUpdate }: ControlsProps) {
  const [setpoint, setSetpoint] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [hasUserInput, setHasUserInput] = useState(false)

  // Update setpoint input when status changes, but only if user hasn't manually edited it
  useEffect(() => {
    if (status && status.setpoint_f && !hasUserInput) {
      setSetpoint(status.setpoint_f.toString())
    }
  }, [status, hasUserInput])

  const handleStart = async () => {
    try {
      setLoading(true)
      setMessage('')
      await apiClient.startController()
      setMessage('Controller started successfully')
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleStop = async () => {
    try {
      setLoading(true)
      setMessage('')
      await apiClient.stopController()
      setMessage('Controller stopped successfully')
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleSetpointChange = async () => {
    const value = parseFloat(setpoint)
    if (isNaN(value) || value < 100 || value > 400) {
      setMessage('Setpoint must be between 100°F and 400°F')
      return
    }

    try {
      setLoading(true)
      setMessage('')
      await apiClient.setSetpoint({ value, units: 'F' })
      setMessage(`Setpoint updated to ${value}°F`)
      setHasUserInput(false) // Reset flag after successful update
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handlePreset = async (presetTemp: number) => {
    setSetpoint(presetTemp.toString())
    setHasUserInput(false) // Preset is not user input, allow overwriting
    try {
      setLoading(true)
      setMessage('')
      await apiClient.setSetpoint({ value: presetTemp, units: 'F' })
      setMessage(`Setpoint updated to ${presetTemp}°F`)
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleBoost = async () => {
    try {
      setLoading(true)
      setMessage('')
      await apiClient.enableBoost()
      setMessage('Boost mode enabled for 60 seconds')
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleDisableBoost = async () => {
    try {
      setLoading(true)
      setMessage('')
      await apiClient.disableBoost()
      setMessage('Boost mode disabled')
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const presets = [
    { temp: 180, label: 'Low & Slow' },
    { temp: 225, label: 'Standard' },
    { temp: 250, label: 'Hot & Fast' },
    { temp: 275, label: 'High Heat' },
  ]

  return (
    <div className="space-y-6">
      {/* Main Controls */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Controller Controls</h3>
        
        <div className="flex items-center space-x-4 mb-6">
          <button
            onClick={handleStart}
            disabled={loading || status?.running}
            className="btn btn-success disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Starting...' : 'Start'}
          </button>
          
          <button
            onClick={handleStop}
            disabled={loading || !status?.running}
            className="btn btn-danger disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Stopping...' : 'Stop'}
          </button>
        </div>

        {/* Setpoint Control */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Setpoint Temperature
          </label>
          
          {/* Warning if phases are controlling setpoint */}
          {status?.current_phase && (
            <div className="mb-2 p-2 bg-blue-50 border border-blue-200 rounded text-sm text-blue-700">
              <span className="font-medium">⚠️ Phase Control Active:</span> Setpoint is managed by cooking phase "{status.current_phase.phase_name}" ({status.current_phase.target_temp_f}°F)
            </div>
          )}
          
          <div className="flex items-center space-x-2">
            <input
              type="number"
              value={setpoint}
              onChange={(e) => {
                setSetpoint(e.target.value)
                setHasUserInput(true)
              }}
              className="input w-32"
              min="100"
              max="400"
              step="1"
              disabled={!!status?.current_phase}
              title={status?.current_phase ? "Setpoint is controlled by active cooking phase" : ""}
            />
            <span className="text-sm text-gray-500">°F</span>
            <button
              onClick={handleSetpointChange}
              disabled={loading || !!status?.current_phase}
              className="btn btn-primary disabled:opacity-50"
              title={status?.current_phase ? "Cannot change setpoint during active cooking phase" : ""}
            >
              Update
            </button>
          </div>
        </div>

        {/* Preset Buttons */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Quick Presets
          </label>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset) => (
              <button
                key={preset.temp}
                onClick={() => handlePreset(preset.temp)}
                disabled={loading}
                className="btn btn-outline disabled:opacity-50"
              >
                {preset.temp}°F - {preset.label}
              </button>
            ))}
          </div>
        </div>

        {/* Boost Control */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Boost Mode
          </label>
          <div className="flex items-center space-x-2">
            {status?.boost_active ? (
              <button
                onClick={handleDisableBoost}
                disabled={loading}
                className="btn btn-warning disabled:opacity-50"
              >
                Disable Boost
              </button>
            ) : (
              <button
                onClick={handleBoost}
                disabled={loading || !status?.running}
                className="btn btn-warning disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Enable Boost (60s)
              </button>
            )}
            {status?.boost_active && status.boost_until && (
              <span className="text-sm text-warning-600">
                Boost active until {new Date(status.boost_until).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Message */}
        {message && (
          <div className={`mt-4 p-3 rounded-lg ${
            message.startsWith('Error') 
              ? 'bg-danger-100 text-danger-700' 
              : 'bg-success-100 text-success-700'
          }`}>
            {message}
          </div>
        )}
      </div>

      {/* Status Display */}
      {status && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Current Status</h3>
          
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div>
              <div className="text-sm text-gray-500">Temperature</div>
              <div className="text-2xl font-bold text-gray-900">
                {status.current_temp_f ? `${status.current_temp_f.toFixed(1)}°F` : 'N/A'}
              </div>
            </div>
            
            <div>
              <div className="text-sm text-gray-500">Setpoint</div>
              <div className="text-2xl font-bold text-gray-900">
                {status.setpoint_f.toFixed(1)}°F
              </div>
            </div>
            
            <div>
              <div className="text-sm text-gray-500">
                {status.control_mode === 'time_proportional' ? 'PID Output' : 'Output'}
              </div>
              <div className="text-2xl font-bold text-gray-900">
                {status.pid_output.toFixed(1)}%
              </div>
            </div>
            
            <div>
              <div className="text-sm text-gray-500">Relay</div>
              <div className={`text-2xl font-bold ${
                status.relay_state ? 'text-success-600' : 'text-gray-600'
              }`}>
                {status.relay_state ? 'ON' : 'OFF'}
              </div>
            </div>
          </div>
          
          <div className="pt-4 border-t border-gray-200">
            <div className="text-sm text-gray-500">Control Mode</div>
            <div className="text-sm font-medium text-gray-900 mt-1">
              {status.control_mode === 'thermostat' ? (
                <>🌡️ Thermostat (Simple On/Off)</>
              ) : (
                <>⚙️ Time-Proportional PID</>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
