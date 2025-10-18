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
  
  // Auto-tune state
  const [showAutoTune, setShowAutoTune] = useState(false)
  const [autoTuneRule, setAutoTuneRule] = useState('tyreus_luyben')
  const [autoTuneOutputStep, setAutoTuneOutputStep] = useState('50')
  const [autoTuneMessage, setAutoTuneMessage] = useState('')

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

  const handleStartAutoTune = async () => {
    try {
      setLoading(true)
      setAutoTuneMessage('')
      await apiClient.startAutoTune({
        tuning_rule: autoTuneRule,
        output_step: parseFloat(autoTuneOutputStep),
      })
      setAutoTuneMessage('Auto-tune started! This will take 10-20 minutes. Monitor progress below.')
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

  const handleApplyAutoTune = async () => {
    if (!confirm('Apply auto-tuned PID gains? This will replace your current PID settings.')) {
      return
    }
    try {
      setLoading(true)
      setAutoTuneMessage('')
      const result = await apiClient.applyAutoTuneGains()
      setAutoTuneMessage(`✅ Gains applied! Kp=${result.gains.kp.toFixed(3)}, Ki=${result.gains.ki.toFixed(3)}, Kd=${result.gains.kd.toFixed(3)}`)
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

      {/* Auto-Tune PID */}
      {status?.control_mode === 'time_proportional' && !status?.active_smoke_id && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h3 className="text-lg font-semibold text-gray-900">🎯 PID Auto-Tuner</h3>
              <p className="text-sm text-gray-600 mt-1">
                Automatically calculate optimal PID gains for your smoker
              </p>
            </div>
            <button
              onClick={() => setShowAutoTune(!showAutoTune)}
              className="btn btn-outline text-sm"
            >
              {showAutoTune ? 'Hide' : 'Show'} Auto-Tune
            </button>
          </div>

          {showAutoTune && (
            <>
              {/* Prerequisites Check */}
              {!status.running && (
                <div className="mb-4 p-3 bg-warning-100 border border-warning-300 rounded-lg text-warning-800">
                  ⚠️ Controller must be running to start auto-tune
                </div>
              )}

              {/* Auto-tune Settings */}
              {!status.autotune_active && (
                <div className="space-y-4 mb-4">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Tuning Rule
                      </label>
                      <select
                        value={autoTuneRule}
                        onChange={(e) => setAutoTuneRule(e.target.value)}
                        className="input"
                        disabled={loading}
                      >
                        <option value="tyreus_luyben">Tyreus-Luyben (Conservative - Recommended)</option>
                        <option value="no_overshoot">No Overshoot (Very Conservative)</option>
                        <option value="some_overshoot">Some Overshoot (Balanced)</option>
                        <option value="ziegler_nichols_pid">Ziegler-Nichols PID (Standard)</option>
                        <option value="ziegler_nichols_pi">Ziegler-Nichols PI (No Derivative)</option>
                        <option value="ciancone_marlin">Ciancone-Marlin (For Lag)</option>
                        <option value="pessen_integral">Pessen Integral (Aggressive)</option>
                      </select>
                      <p className="text-xs text-gray-500 mt-1">
                        Start with conservative rules for first-time tuning
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-2">
                        Output Step (%)
                      </label>
                      <input
                        type="number"
                        value={autoTuneOutputStep}
                        onChange={(e) => setAutoTuneOutputStep(e.target.value)}
                        className="input"
                        min="30"
                        max="70"
                        step="5"
                        disabled={loading}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        30-60% recommended. Higher = faster tuning, more oscillation
                      </p>
                    </div>
                  </div>

                  <button
                    onClick={handleStartAutoTune}
                    disabled={loading || !status.running}
                    className="btn btn-primary disabled:opacity-50 w-full"
                  >
                    {loading ? 'Starting...' : '🚀 Start Auto-Tune (10-20 min)'}
                  </button>

                  <div className="p-3 bg-blue-50 border border-blue-200 rounded-lg">
                    <p className="text-sm text-blue-800">
                      <strong>How it works:</strong> The auto-tuner will apply relay control to create temperature oscillations, 
                      then calculate optimal PID gains based on your smoker's response characteristics.
                      <br /><br />
                      <strong>Before starting:</strong> Make sure temperature is near your target setpoint (±10°F).
                    </p>
                  </div>
                </div>
              )}

              {/* Auto-tune Status */}
              {status.autotune_active && status.autotune_status && (
                <div className="space-y-4">
                  <div className="p-4 bg-primary-50 border-2 border-primary-300 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary-600"></div>
                        <span className="font-semibold text-primary-900">Auto-Tune Running</span>
                      </div>
                      <span className="text-sm text-primary-700">
                        {status.autotune_status.status?.elapsed_time 
                          ? `${Math.floor(status.autotune_status.status.elapsed_time / 60)}:${Math.floor(status.autotune_status.status.elapsed_time % 60).toString().padStart(2, '0')}`
                          : '0:00'}
                      </span>
                    </div>

                    <div className="grid grid-cols-3 gap-4 mt-4">
                      <div>
                        <div className="text-xs text-primary-600">State</div>
                        <div className="font-medium text-primary-900">
                          {status.autotune_status.status?.state?.replace('_', ' ').toUpperCase() || 'UNKNOWN'}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-primary-600">Cycles</div>
                        <div className="font-medium text-primary-900">
                          {status.autotune_status.status?.cycle_count || 0} / {status.autotune_status.status?.min_cycles || 3}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-primary-600">Output</div>
                        <div className="font-medium text-primary-900">
                          {status.autotune_status.status?.output || 0}%
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={handleCancelAutoTune}
                      disabled={loading}
                      className="btn btn-danger mt-4 w-full text-sm"
                    >
                      Cancel Auto-Tune
                    </button>
                  </div>
                </div>
              )}

              {/* Auto-tune Results */}
              {!status.autotune_active && status.autotune_status?.status?.results && (
                <div className="space-y-4">
                  <div className="p-4 bg-success-50 border-2 border-success-300 rounded-lg">
                    <div className="flex items-center space-x-2 mb-3">
                      <span className="text-2xl">✅</span>
                      <span className="font-semibold text-success-900">Auto-Tune Complete!</span>
                    </div>

                    <div className="grid grid-cols-2 gap-4 mb-4">
                      <div>
                        <div className="text-sm font-semibold text-success-800 mb-2">Calculated Gains:</div>
                        <div className="space-y-1 text-sm">
                          <div><span className="font-medium">Kp:</span> {status.autotune_status.status.results.kp?.toFixed(4)}</div>
                          <div><span className="font-medium">Ki:</span> {status.autotune_status.status.results.ki?.toFixed(4)}</div>
                          <div><span className="font-medium">Kd:</span> {status.autotune_status.status.results.kd?.toFixed(4)}</div>
                        </div>
                      </div>
                      <div>
                        <div className="text-sm font-semibold text-success-800 mb-2">System Info:</div>
                        <div className="space-y-1 text-sm">
                          <div><span className="font-medium">Ku:</span> {status.autotune_status.status.results.ku?.toFixed(2)}</div>
                          <div><span className="font-medium">Pu:</span> {status.autotune_status.status.results.pu?.toFixed(1)}s</div>
                          <div><span className="font-medium">Rule:</span> {status.autotune_status.status.tuning_rule?.replace('_', ' ')}</div>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={handleApplyAutoTune}
                      disabled={loading}
                      className="btn btn-success w-full disabled:opacity-50"
                    >
                      Apply These Gains
                    </button>
                  </div>
                </div>
              )}

              {/* Auto-tune Message */}
              {autoTuneMessage && (
                <div className={`mt-4 p-3 rounded-lg ${
                  autoTuneMessage.startsWith('Error') 
                    ? 'bg-danger-100 text-danger-700' 
                    : autoTuneMessage.includes('✅')
                    ? 'bg-success-100 text-success-700'
                    : 'bg-blue-100 text-blue-700'
                }`}>
                  {autoTuneMessage}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Info for why auto-tune is not available */}
      {status?.control_mode === 'thermostat' && (
        <div className="card bg-gray-50">
          <div className="flex items-center space-x-3">
            <span className="text-2xl">ℹ️</span>
            <div>
              <div className="font-semibold text-gray-900">PID Auto-Tune Not Available</div>
              <p className="text-sm text-gray-600 mt-1">
                Auto-tune requires Time-Proportional PID mode. Switch to PID mode in Settings to use auto-tune.
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
