import { useState, useEffect, useRef } from 'react'
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
  
  // Auto-tune state
  const [autoTuneMessage, setAutoTuneMessage] = useState('')
  const lastAutotuneActive = useRef<boolean | null>(null)

  // Update setpoint input when status changes, but only if user hasn't manually edited it
  useEffect(() => {
    if (status && status.setpoint_f && !hasUserInput) {
      setSetpoint(status.setpoint_f.toString())
    }
  }, [status, hasUserInput])

  // Watch for auto-tune completion (only show message once when transitioning from active to complete)
  useEffect(() => {
    if (!status) return
    
    // Detect transition from active to inactive
    if (lastAutotuneActive.current === true && !status.autotune_active) {
      // Auto-tune just completed - check if it succeeded
      if (status.autotune_status?.results) {
        const results = status.autotune_status.results
        setAutoTuneMessage(`✅ Auto-tune complete! Optimized gains applied: Kp=${results.kp?.toFixed(3)}, Ki=${results.ki?.toFixed(3)}, Kd=${results.kd?.toFixed(3)}`)
        // Clear message after 10 seconds
        setTimeout(() => setAutoTuneMessage(''), 10000)
      }
    }
    
    // Update the ref for next comparison
    lastAutotuneActive.current = status.autotune_active
  }, [status?.autotune_active])

  // Log adaptive PID status changes
  useEffect(() => {
    if (!status) return
    
    console.log('📊 Status Update - Adaptive PID:', {
      enabled: status.adaptive_pid?.enabled,
      adjustment_count: status.adaptive_pid?.adjustment_count,
      data_points: status.adaptive_pid?.data_points,
      control_mode: status.control_mode,
      timestamp: new Date().toISOString()
    })
  }, [status?.adaptive_pid?.enabled, status?.control_mode])

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

  const handleStartAutoTune = async () => {
    if (!confirm('Start PID auto-tune? This will take 10-20 minutes. The controller will continue running and automatically apply optimized gains when complete.')) {
      return
    }
    try {
      setLoading(true)
      setAutoTuneMessage('')
      await apiClient.startAutoTune()  // Use all defaults
      setAutoTuneMessage('Auto-tune started! The system will tune itself and automatically apply the optimized gains.')
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setAutoTuneMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleCancelAutoTune = async () => {
    try {
      setLoading(true)
      setAutoTuneMessage('')
      await apiClient.cancelAutoTune()
      setAutoTuneMessage('Auto-tune cancelled')
      // Refresh status
      const newStatus = await apiClient.getStatus()
      onStatusUpdate(newStatus)
    } catch (error) {
      setAutoTuneMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
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

      {/* Auto-Tune PID - Simplified */}
      {status?.control_mode === 'time_proportional' && !status?.active_smoke_id && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-2">🎯 PID Auto-Tuner</h3>
          <p className="text-sm text-gray-600 mb-4">
            Automatically optimize PID gains for your smoker
          </p>

          {/* Auto-tune Running */}
          {status.autotune_active && status.autotune_status && (
            <div className="p-4 bg-primary-50 border-2 border-primary-300 rounded-lg">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center space-x-2">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-600"></div>
                  <span className="font-semibold text-primary-900">Auto-Tuning in Progress</span>
                </div>
                <span className="text-sm text-primary-700 font-medium">
                  {status.autotune_status.elapsed_time 
                    ? `${Math.floor(status.autotune_status.elapsed_time / 60)}:${Math.floor(status.autotune_status.elapsed_time % 60).toString().padStart(2, '0')}`
                    : '0:00'}
                </span>
              </div>

              <div className="flex items-center justify-between text-sm mb-4">
                <span className="text-primary-700">
                  Peaks detected: {status.autotune_status.peaks_detected || 0}
                </span>
                <span className="text-primary-700">
                  {status.autotune_status.state?.replace('_', ' ') || 'unknown'}
                </span>
              </div>

              <p className="text-sm text-primary-800 mb-3">
                The system is analyzing your smoker's response. Gains will be automatically applied when complete.
              </p>

              <button
                onClick={handleCancelAutoTune}
                disabled={loading}
                className="btn btn-danger w-full text-sm disabled:opacity-50"
              >
                Cancel Auto-Tune
              </button>
            </div>
          )}

          {/* Start Button */}
          {!status.autotune_active && (
            <div>
              <button
                onClick={handleStartAutoTune}
                disabled={loading || !status.running}
                className="btn btn-primary disabled:opacity-50 w-full mb-3"
              >
                {loading ? 'Starting...' : '🚀 Auto-Tune PID (10-20 min)'}
              </button>
              
              <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg text-sm text-blue-800">
                <strong>How it works:</strong> The system will automatically measure your smoker's behavior and calculate 
                optimal PID gains. The gains will be applied automatically when complete. Just click and wait!
              </div>
            </div>
          )}

          {/* Message */}
          {autoTuneMessage && (
            <div className={`mt-3 p-3 rounded-lg ${
              autoTuneMessage.startsWith('Error') 
                ? 'bg-danger-100 text-danger-700' 
                : autoTuneMessage.includes('✅')
                ? 'bg-success-100 text-success-700'
                : 'bg-blue-100 text-blue-700'
            }`}>
              {autoTuneMessage}
            </div>
          )}
        </div>
      )}

      {/* Adaptive PID Toggle */}
      {status?.control_mode === 'time_proportional' && (
        <div className="card">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
                🧠 Adaptive PID
                {status.adaptive_pid?.enabled && (
                  <span className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-800 font-medium">
                    ACTIVE
                  </span>
                )}
              </h3>
              <p className="text-sm text-gray-600 mt-1">
                Continuously optimizes PID gains in the background
              </p>
            </div>
            
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={status.adaptive_pid?.enabled || false}
                onChange={async (e) => {
                  console.log('🎛️ Adaptive PID Toggle Clicked:', {
                    newCheckedState: e.target.checked,
                    currentStatus: status.adaptive_pid,
                    controlMode: status.control_mode,
                    timestamp: new Date().toISOString()
                  })
                  
                  try {
                    if (e.target.checked) {
                      console.log('📤 Calling enableAdaptivePID API...')
                      const response = await apiClient.enableAdaptivePID()
                      console.log('✅ enableAdaptivePID response:', response)
                      setMessage('Adaptive PID enabled')
                    } else {
                      console.log('📤 Calling disableAdaptivePID API...')
                      const response = await apiClient.disableAdaptivePID()
                      console.log('✅ disableAdaptivePID response:', response)
                      setMessage('Adaptive PID disabled')
                    }
                    
                    console.log('📤 Fetching updated status...')
                    const newStatus = await apiClient.getStatus()
                    console.log('✅ New status received:', {
                      adaptive_pid: newStatus.adaptive_pid,
                      control_mode: newStatus.control_mode
                    })
                    
                    onStatusUpdate(newStatus)
                    setTimeout(() => setMessage(''), 3000)
                  } catch (error) {
                    console.error('❌ Adaptive PID toggle error:', error)
                    setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
                  }
                }}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
            </label>
          </div>
          
          {status.adaptive_pid?.enabled && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              {/* Status Overview */}
              <div className="bg-gradient-to-r from-primary-50 to-blue-50 rounded-lg p-3 mb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    {status.adaptive_pid.data_points >= 240 ? (
                      <>
                        <div className="relative mr-2">
                          <div className="w-2 h-2 bg-green-500 rounded-full"></div>
                          <div className="absolute top-0 left-0 w-2 h-2 bg-green-500 rounded-full animate-ping"></div>
                        </div>
                        <span className="text-sm font-medium text-gray-900">
                          Actively Monitoring
                        </span>
                        <span className="ml-2 text-xs text-gray-600">
                          (5-min rolling window)
                        </span>
                      </>
                    ) : (
                      <>
                        <div className="relative mr-2">
                          <div className="w-2 h-2 bg-yellow-500 rounded-full"></div>
                          <div className="absolute top-0 left-0 w-2 h-2 bg-yellow-500 rounded-full animate-ping"></div>
                        </div>
                        <span className="text-sm font-medium text-gray-900">
                          Warming Up
                        </span>
                        <span className="ml-2 text-xs text-gray-600">
                          ({status.adaptive_pid.data_points}/240 samples)
                        </span>
                      </>
                    )}
                  </div>
                  
                  <div className="text-right">
                    {status.adaptive_pid.cooldown_remaining > 0 ? (
                      <div className="text-xs">
                        <span className="text-gray-600">Next evaluation in</span>
                        <span className="ml-1 font-semibold text-primary-600">
                          {Math.ceil(status.adaptive_pid.cooldown_remaining / 60)} min
                        </span>
                      </div>
                    ) : status.adaptive_pid.data_points >= 240 ? (
                      <div className="flex items-center text-xs font-medium text-green-600">
                        <svg className="w-3 h-3 mr-1" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                        Ready to evaluate
                      </div>
                    ) : (
                      <div className="text-xs text-gray-500 italic">
                        Collecting data...
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Stats Grid */}
              <div className="grid grid-cols-2 gap-3 text-sm mb-3">
                <div className="bg-gray-50 rounded p-2">
                  <div className="text-xs text-gray-600 mb-1">Total Adjustments</div>
                  <div className="text-lg font-bold text-gray-900">
                    {status.adaptive_pid.adjustment_count || 0}
                  </div>
                </div>
                <div className="bg-gray-50 rounded p-2">
                  <div className="text-xs text-gray-600 mb-1">Buffer Status</div>
                  <div className="text-lg font-bold text-gray-900">
                    {status.adaptive_pid.data_points >= 300 
                      ? 'Full ✓' 
                      : `${Math.round((status.adaptive_pid.data_points / 300) * 100)}%`
                    }
                  </div>
                </div>
              </div>
              
              {/* Recent Adjustments */}
              {status.adaptive_pid.recent_adjustments && status.adaptive_pid.recent_adjustments.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs font-semibold text-gray-700 mb-2 flex items-center">
                    <svg className="w-4 h-4 mr-1 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                    Recent Adjustments
                  </div>
                  <div className="space-y-2">
                    {status.adaptive_pid.recent_adjustments.slice(-3).reverse().map((adj: any, i: number) => (
                      <div key={i} className="text-xs bg-white border border-gray-200 p-2.5 rounded-lg shadow-sm">
                        <div className="font-medium text-gray-900 mb-1">{adj.reason}</div>
                        <div className="text-gray-600 font-mono text-xs space-y-0.5">
                          <div>Kp: {adj.old_kp?.toFixed(2)} → <span className="text-primary-600 font-semibold">{adj.new_kp?.toFixed(2)}</span></div>
                          <div>Ki: {adj.old_ki?.toFixed(3)} → <span className="text-primary-600 font-semibold">{adj.new_ki?.toFixed(3)}</span></div>
                          <div>Kd: {adj.old_kd?.toFixed(1)} → <span className="text-primary-600 font-semibold">{adj.new_kd?.toFixed(1)}</span></div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Info Message */}
              <div className="mt-3 flex items-start text-xs text-gray-500 bg-blue-50 rounded p-2">
                <svg className="w-4 h-4 mr-1.5 mt-0.5 text-blue-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
                </svg>
                <span>
                  Continuously analyzes performance and fine-tunes PID gains for optimal temperature control
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Info for why auto-tune is not available */}
      {status?.control_mode === 'thermostat' && (
        <div className="card bg-gray-50">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">ℹ️</span>
            <div>
              <div className="font-semibold text-gray-900">PID Features Not Available</div>
              <p className="text-sm text-gray-600 mt-1">
                Auto-tune and Adaptive PID require Time-Proportional PID mode. Switch to PID mode in Settings to use these features.
              </p>
            </div>
          </div>
        </div>
      )}

      {status?.active_smoke_id && status?.control_mode === 'time_proportional' && (
        <div className="card bg-gray-50">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">ℹ️</span>
            <div>
              <div className="font-semibold text-gray-900">PID Auto-Tune Not Available</div>
              <p className="text-sm text-gray-600 mt-1">
                Cannot auto-tune during an active smoke session. End the current session first.
              </p>
            </div>
          </div>
        </div>
      )}

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
