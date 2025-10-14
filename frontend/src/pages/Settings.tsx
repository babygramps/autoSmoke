import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { Settings as SettingsType, Thermocouple, ThermocoupleCreate } from '../types'

// Temperature conversion helpers
const cToF = (c: number): number => (c * 9/5) + 32
const fToC = (f: number): number => (f - 32) * 5/9

export function Settings() {
  const [settings, setSettings] = useState<SettingsType | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  // Form state
  const [formData, setFormData] = useState<Partial<SettingsType>>({})

  // Thermocouple state
  const [thermocouples, setThermocouples] = useState<Thermocouple[]>([])
  const [showAddTC, setShowAddTC] = useState(false)
  const [newTC, setNewTC] = useState<Partial<ThermocoupleCreate>>({ name: '', cs_pin: 8, enabled: true, color: '#ef4444' })
  const [editingTC, setEditingTC] = useState<number | null>(null)
  const [editingName, setEditingName] = useState<number | null>(null)
  const [tempName, setTempName] = useState('')
  const [tcMessage, setTcMessage] = useState('')

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        setLoading(true)
        const [settingsData, thermocouplesData] = await Promise.all([
          apiClient.getSettings(),
          apiClient.getThermocouples()
        ])
        setSettings(settingsData)
        setFormData(settingsData)
        setThermocouples(thermocouplesData.thermocouples.sort((a, b) => a.order - b.order))
      } catch (error) {
        setMessage(`Error loading settings: ${error instanceof Error ? error.message : 'Unknown error'}`)
      } finally {
        setLoading(false)
      }
    }

    fetchSettings()
  }, [])

  const handleInputChange = (field: keyof SettingsType, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setMessage('')
      
      const response = await apiClient.updateSettings(formData)
      setSettings(response.settings)
      setMessage('Settings saved successfully')
    } catch (error) {
      setMessage(`Error saving settings: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setSaving(false)
    }
  }

  const handleReset = async () => {
    try {
      setSaving(true)
      setMessage('')
      
      const response = await apiClient.resetSettings()
      setSettings(response.settings)
      setFormData(response.settings)
      setMessage('Settings reset to defaults')
    } catch (error) {
      setMessage(`Error resetting settings: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setSaving(false)
    }
  }

  // Thermocouple handlers
  const handleAddTC = async () => {
    if (!newTC.name || newTC.cs_pin === undefined) {
      setTcMessage('Please enter a name and CS pin')
      return
    }
    try {
      await apiClient.createThermocouple(newTC as ThermocoupleCreate)
      const updatedList = await apiClient.getThermocouples()
      setThermocouples(updatedList.thermocouples.sort((a, b) => a.order - b.order))
      setNewTC({ name: '', cs_pin: 8, enabled: true, color: '#ef4444' })
      setShowAddTC(false)
      setTcMessage('Thermocouple added successfully')
      setTimeout(() => setTcMessage(''), 3000)
    } catch (error) {
      setTcMessage(`Error adding thermocouple: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleUpdateTC = async (id: number, updates: Partial<Thermocouple>) => {
    try {
      await apiClient.updateThermocouple(id, updates)
      const updatedList = await apiClient.getThermocouples()
      setThermocouples(updatedList.thermocouples.sort((a, b) => a.order - b.order))
      setEditingTC(null)
      setTcMessage('Thermocouple updated successfully')
      setTimeout(() => setTcMessage(''), 3000)
    } catch (error) {
      setTcMessage(`Error updating thermocouple: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleSetControl = async (id: number) => {
    try {
      await apiClient.setControlThermocouple(id)
      const updatedList = await apiClient.getThermocouples()
      setThermocouples(updatedList.thermocouples.sort((a, b) => a.order - b.order))
      setTcMessage('Control thermocouple updated')
      setTimeout(() => setTcMessage(''), 3000)
    } catch (error) {
      setTcMessage(`Error setting control thermocouple: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleDeleteTC = async (id: number) => {
    if (!confirm('Are you sure you want to delete this thermocouple?')) return
    try {
      await apiClient.deleteThermocouple(id)
      const updatedList = await apiClient.getThermocouples()
      setThermocouples(updatedList.thermocouples.sort((a, b) => a.order - b.order))
      setTcMessage('Thermocouple deleted')
      setTimeout(() => setTcMessage(''), 3000)
    } catch (error) {
      setTcMessage(`Error deleting thermocouple: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleStartEditName = (tc: Thermocouple) => {
    setEditingName(tc.id)
    setTempName(tc.name)
  }

  const handleSaveName = async (id: number) => {
    if (!tempName.trim()) {
      setTcMessage('Name cannot be empty')
      setEditingName(null)
      return
    }
    try {
      await apiClient.updateThermocouple(id, { name: tempName.trim() })
      const updatedList = await apiClient.getThermocouples()
      setThermocouples(updatedList.thermocouples.sort((a, b) => a.order - b.order))
      setEditingName(null)
    } catch (error) {
      setTcMessage(`Error updating name: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleCancelEditName = () => {
    setEditingName(null)
    setTempName('')
  }

  const handleNameKeyDown = (e: React.KeyboardEvent, id: number) => {
    if (e.key === 'Enter') {
      handleSaveName(id)
    } else if (e.key === 'Escape') {
      handleCancelEditName()
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading settings...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!settings) {
    return (
      <div className="card">
        <div className="text-center py-8">
          <p className="text-gray-600">Failed to load settings</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">Settings</h2>
          <div className="space-x-2">
            <button
              onClick={handleReset}
              disabled={saving}
              className="btn btn-outline disabled:opacity-50"
            >
              Reset to Defaults
            </button>
            <button
              onClick={handleSave}
              disabled={saving}
              className="btn btn-primary disabled:opacity-50"
            >
              {saving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        </div>

        {/* Message */}
        {message && (
          <div className={`mb-6 p-3 rounded-lg ${
            message.startsWith('Error') 
              ? 'bg-danger-100 text-danger-700' 
              : 'bg-success-100 text-success-700'
          }`}>
            {message}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Temperature Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Temperature Settings</h3>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Units
              </label>
              <select
                value={formData.units || 'F'}
                onChange={(e) => handleInputChange('units', e.target.value)}
                className="input"
              >
                <option value="F">Fahrenheit (°F)</option>
                <option value="C">Celsius (°C)</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                Temperature unit for display. All values will convert automatically when you switch units.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Default Setpoint
              </label>
              <input
                type="number"
                value={
                  formData.units === 'C' 
                    ? Math.round((formData.setpoint_c || 107.2) * 10) / 10
                    : Math.round(formData.setpoint_f || 225)
                }
                onChange={(e) => {
                  const value = parseFloat(e.target.value)
                  if (formData.units === 'C') {
                    handleInputChange('setpoint_c', value)
                    handleInputChange('setpoint_f', cToF(value))
                  } else {
                    handleInputChange('setpoint_f', value)
                    handleInputChange('setpoint_c', fToC(value))
                  }
                }}
                className="input"
                min={formData.units === 'C' ? '40' : '100'}
                max={formData.units === 'C' ? '200' : '400'}
                step={formData.units === 'C' ? '0.5' : '1'}
              />
              <p className="text-xs text-gray-500 mt-1">
                Target temperature for smoking. This is the temperature the controller will try to maintain.
              </p>
            </div>
          </div>

          {/* Control Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Control Settings</h3>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Control Mode
              </label>
              <select
                value={formData.control_mode || 'thermostat'}
                onChange={(e) => handleInputChange('control_mode', e.target.value)}
                className="input"
              >
                <option value="thermostat">Thermostat (Simple On/Off)</option>
                <option value="time_proportional">Time-Proportional PID</option>
              </select>
              <p className="text-xs text-gray-500 mt-1">
                {formData.control_mode === 'thermostat' 
                  ? 'Simple on/off control (like your home thermostat). Best for most smokers - reliable and easy to tune.'
                  : 'Advanced PID control with duty cycle modulation. More precise temperature regulation but requires tuning.'}
              </p>
            </div>

            {/* Thermostat Mode Settings */}
            {formData.control_mode === 'thermostat' && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Min On Time (s)
                    </label>
                    <input
                      type="number"
                      value={formData.min_on_s || 5}
                      onChange={(e) => handleInputChange('min_on_s', parseInt(e.target.value))}
                      className="input"
                      min="0"
                      max="60"
                      step="1"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Minimum time heater stays ON before turning off. Prevents rapid cycling and extends relay life.
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Min Off Time (s)
                    </label>
                    <input
                      type="number"
                      value={formData.min_off_s || 5}
                      onChange={(e) => handleInputChange('min_off_s', parseInt(e.target.value))}
                      className="input"
                      min="0"
                      max="60"
                      step="1"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Minimum time heater stays OFF before turning on again. Prevents rapid cycling.
                    </p>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Hysteresis ({formData.units === 'C' ? '°C' : '°F'})
                  </label>
                  <input
                    type="number"
                    value={
                      formData.units === 'C'
                        ? Math.round((formData.hyst_c || 0.6) * 10) / 10
                        : Math.round(cToF(formData.hyst_c || 0.6) * 10) / 10
                    }
                    onChange={(e) => {
                      const value = parseFloat(e.target.value)
                      handleInputChange('hyst_c', formData.units === 'C' ? value : fToC(value))
                    }}
                    className="input"
                    min="0"
                    max={formData.units === 'C' ? '5' : '10'}
                    step="0.1"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Temperature deadband around setpoint. Heater turns ON when temp drops below (setpoint - hysteresis/2) and OFF when above (setpoint + hysteresis/2). Larger values reduce cycling frequency.
                  </p>
                </div>
              </>
            )}

            {/* Time-Proportional Mode Settings */}
            {formData.control_mode === 'time_proportional' && (
              <>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Kp (Proportional)
                    </label>
                    <input
                      type="number"
                      value={formData.kp || 4.0}
                      onChange={(e) => handleInputChange('kp', parseFloat(e.target.value))}
                      className="input"
                      min="0"
                      max="100"
                      step="0.1"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Responds to current error. Higher = stronger response but may oscillate.
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Ki (Integral)
                    </label>
                    <input
                      type="number"
                      value={formData.ki || 0.1}
                      onChange={(e) => handleInputChange('ki', parseFloat(e.target.value))}
                      className="input"
                      min="0"
                      max="10"
                      step="0.01"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Eliminates steady-state error. Too high causes overshoot and instability.
                    </p>
                  </div>
                  
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      Kd (Derivative)
                    </label>
                    <input
                      type="number"
                      value={formData.kd || 20.0}
                      onChange={(e) => handleInputChange('kd', parseFloat(e.target.value))}
                      className="input"
                      min="0"
                      max="100"
                      step="0.1"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Responds to rate of change. Helps prevent overshoot and improves stability.
                    </p>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Time Window (s)
                  </label>
                  <input
                    type="number"
                    value={formData.time_window_s || 10}
                    onChange={(e) => handleInputChange('time_window_s', parseInt(e.target.value))}
                    className="input"
                    min="5"
                    max="60"
                    step="1"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Time window for duty cycle control. Example: 60% PID output with 10s window = 6 seconds ON, 4 seconds OFF. Longer windows provide smoother control but slower response.
                  </p>
                </div>
              </>
            )}
          </div>

          {/* Alarm Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Alarm Thresholds</h3>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  High Alarm ({formData.units === 'C' ? '°C' : '°F'})
                </label>
                <input
                  type="number"
                  value={
                    formData.units === 'C'
                      ? Math.round(formData.hi_alarm_c || 135.0)
                      : Math.round(cToF(formData.hi_alarm_c || 135.0))
                  }
                  onChange={(e) => {
                    const value = parseFloat(e.target.value)
                    handleInputChange('hi_alarm_c', formData.units === 'C' ? value : fToC(value))
                  }}
                  className="input"
                  min={formData.units === 'C' ? '50' : '120'}
                  max={formData.units === 'C' ? '200' : '400'}
                  step="1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Alert triggers when temperature exceeds this threshold. Helps prevent overheating and fire hazards.
                </p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Low Alarm ({formData.units === 'C' ? '°C' : '°F'})
                </label>
                <input
                  type="number"
                  value={
                    formData.units === 'C'
                      ? Math.round(formData.lo_alarm_c || 65.6)
                      : Math.round(cToF(formData.lo_alarm_c || 65.6))
                  }
                  onChange={(e) => {
                    const value = parseFloat(e.target.value)
                    handleInputChange('lo_alarm_c', formData.units === 'C' ? value : fToC(value))
                  }}
                  className="input"
                  min={formData.units === 'C' ? '0' : '32'}
                  max={formData.units === 'C' ? '150' : '300'}
                  step="1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Alert triggers when temperature falls below this threshold. Warns you if your fire has gone out.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Stuck High Rate ({formData.units === 'C' ? '°C/min' : '°F/min'})
                </label>
                <input
                  type="number"
                  value={
                    formData.units === 'C'
                      ? Math.round((formData.stuck_high_c || 2.0) * 10) / 10
                      : Math.round((formData.stuck_high_c || 2.0) * 9/5 * 10) / 10
                  }
                  onChange={(e) => {
                    const value = parseFloat(e.target.value)
                    // For rates, we convert directly (not using fToC since it has +32 offset)
                    handleInputChange('stuck_high_c', formData.units === 'C' ? value : value * 5/9)
                  }}
                  className="input"
                  min="0"
                  max={formData.units === 'C' ? '10' : '18'}
                  step="0.1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Alert if temperature rises faster than this rate for the stuck high duration. Detects runaway temperature.
                </p>
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Stuck High Duration (s)
                </label>
                <input
                  type="number"
                  value={formData.stuck_high_duration_s || 60}
                  onChange={(e) => handleInputChange('stuck_high_duration_s', parseInt(e.target.value))}
                  className="input"
                  min="10"
                  max="300"
                  step="10"
                />
                <p className="text-xs text-gray-500 mt-1">
                  How long temperature must rise at stuck high rate before triggering alert. Prevents false alarms during startup.
                </p>
              </div>
            </div>
          </div>

          {/* Hardware Settings */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900">Hardware Settings</h3>
            
            <div>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={formData.sim_mode || false}
                  onChange={(e) => handleInputChange('sim_mode', e.target.checked)}
                  className="mr-2"
                />
                <span className="text-sm font-medium text-gray-700">Simulation Mode</span>
              </label>
              <p className="text-xs text-gray-500 mt-1">
                Enable for testing without real hardware. Uses a software simulator that mimics temperature sensor and heater behavior.
              </p>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  GPIO Pin
                </label>
                <input
                  type="number"
                  value={formData.gpio_pin || 17}
                  onChange={(e) => handleInputChange('gpio_pin', parseInt(e.target.value))}
                  className="input"
                  min="1"
                  max="40"
                  step="1"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Raspberry Pi GPIO pin (BCM numbering) connected to relay controlling your heater. Default is GPIO 17.
                </p>
              </div>
              
              <div>
                <label className="flex items-center mt-6">
                  <input
                    type="checkbox"
                    checked={formData.relay_active_high || false}
                    onChange={(e) => handleInputChange('relay_active_high', e.target.checked)}
                    className="mr-2"
                  />
                  <span className="text-sm font-medium text-gray-700">Relay Active High</span>
                </label>
                <p className="text-xs text-gray-500 mt-1">
                  Enable if relay turns ON with high signal (3.3V). Disable if it turns ON with low signal (0V).
                </p>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Boost Duration (s)
              </label>
              <input
                type="number"
                value={formData.boost_duration_s || 60}
                onChange={(e) => handleInputChange('boost_duration_s', parseInt(e.target.value))}
                className="input"
                min="10"
                max="300"
                step="10"
              />
              <p className="text-xs text-gray-500 mt-1">
                How long the heater runs at maximum when boost mode is activated. Useful for quickly recovering from temperature drops.
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Webhook URL
              </label>
              <input
                type="url"
                value={formData.webhook_url || ''}
                onChange={(e) => handleInputChange('webhook_url', e.target.value || null)}
                className="input"
                placeholder="https://example.com/webhook"
              />
              <p className="text-xs text-gray-500 mt-1">
                Optional HTTP endpoint to receive alert notifications. Useful for integrating with Discord, Slack, or custom systems.
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Thermocouple Configuration */}
      <div className="card">
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-xl font-semibold text-gray-900">🌡️ Thermocouple Configuration</h3>
          <button
            onClick={() => setShowAddTC(!showAddTC)}
            className="btn btn-secondary text-sm"
          >
            {showAddTC ? 'Cancel' : '+ Add Thermocouple'}
          </button>
        </div>

        {tcMessage && (
          <div className={`mb-4 p-3 rounded ${
            tcMessage.includes('Error') ? 'bg-danger-100 text-danger-800' : 'bg-success-100 text-success-800'
          }`}>
            {tcMessage}
          </div>
        )}

        {/* Add Thermocouple Form */}
        {showAddTC && (
          <div className="mb-6 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <h4 className="font-semibold text-gray-900 mb-4">Add New Thermocouple</h4>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={newTC.name || ''}
                  onChange={(e) => setNewTC({ ...newTC, name: e.target.value })}
                  className="input"
                  placeholder="e.g., Grate, Dome"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">CS Pin (GPIO)</label>
                <input
                  type="number"
                  value={newTC.cs_pin || 8}
                  onChange={(e) => setNewTC({ ...newTC, cs_pin: parseInt(e.target.value) })}
                  className="input"
                  min="0"
                  max="27"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Color</label>
                <input
                  type="color"
                  value={newTC.color || '#ef4444'}
                  onChange={(e) => setNewTC({ ...newTC, color: e.target.value })}
                  className="input h-10"
                />
              </div>
              <div className="flex items-end">
                <button onClick={handleAddTC} className="btn btn-primary w-full">
                  Add
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Thermocouples List */}
        <div className="space-y-3">
          {thermocouples.map((tc) => (
            <div
              key={tc.id}
              className={`p-4 rounded-lg border-2 transition-all ${
                tc.is_control ? 'border-primary-500 bg-primary-50' : 'border-gray-200 bg-white hover:border-gray-300'
              }`}
            >
              <div className="flex items-center justify-between gap-4">
                {/* Color indicator */}
                <div className="flex items-center space-x-3 flex-1 min-w-0">
                  <input
                    type="color"
                    value={tc.color}
                    onChange={(e) => handleUpdateTC(tc.id, { color: e.target.value })}
                    className="w-10 h-10 rounded cursor-pointer border-2 border-gray-300 hover:border-gray-400 transition-colors"
                    title="Change color"
                  />
                  
                  {/* Name - inline editing */}
                  <div className="flex-1 min-w-0">
                    {editingName === tc.id ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={tempName}
                          onChange={(e) => setTempName(e.target.value)}
                          onKeyDown={(e) => handleNameKeyDown(e, tc.id)}
                          onBlur={() => handleSaveName(tc.id)}
                          className="input text-base font-semibold flex-1 min-w-0"
                          autoFocus
                          placeholder="Thermocouple name"
                        />
                        <button
                          onClick={() => handleSaveName(tc.id)}
                          className="text-green-600 hover:text-green-700 p-1"
                          title="Save"
                        >
                          ✓
                        </button>
                        <button
                          onClick={handleCancelEditName}
                          className="text-gray-500 hover:text-gray-600 p-1"
                          title="Cancel"
                        >
                          ✕
                        </button>
                      </div>
                    ) : (
                      <div
                        onClick={() => handleStartEditName(tc)}
                        className="cursor-pointer group"
                      >
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-gray-900 text-base group-hover:text-primary-600 transition-colors">
                            {tc.name}
                          </span>
                          <span className="opacity-0 group-hover:opacity-100 text-gray-400 text-sm transition-opacity">
                            ✏️
                          </span>
                          {tc.is_control && (
                            <span className="text-xs px-2 py-0.5 rounded-full bg-primary-100 text-primary-800 font-medium">
                              CONTROL
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-gray-600 mt-0.5">GPIO Pin: {tc.cs_pin}</div>
                      </div>
                    )}
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center gap-2 flex-shrink-0">
                  <label className="flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={tc.enabled}
                      onChange={(e) => handleUpdateTC(tc.id, { enabled: e.target.checked })}
                      className="mr-2 cursor-pointer"
                    />
                    <span className="text-sm text-gray-700 whitespace-nowrap">Enabled</span>
                  </label>
                  
                  {!tc.is_control && tc.enabled && (
                    <button
                      onClick={() => handleSetControl(tc.id)}
                      className="btn btn-secondary text-xs px-3 py-1.5 whitespace-nowrap"
                    >
                      Set as Control
                    </button>
                  )}
                  
                  <button
                    onClick={() => handleDeleteTC(tc.id)}
                    className="btn btn-danger text-xs px-3 py-1.5"
                    title="Delete thermocouple"
                  >
                    🗑️
                  </button>
                </div>
              </div>

              {/* Advanced settings - expandable */}
              {editingTC === tc.id && (
                <div className="mt-3 pt-3 border-t border-gray-200">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">CS Pin (GPIO)</label>
                      <input
                        type="number"
                        defaultValue={tc.cs_pin}
                        onBlur={(e) => handleUpdateTC(tc.id, { cs_pin: parseInt(e.target.value) })}
                        className="input text-sm w-full"
                        min="0"
                        max="27"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-1">Display Order</label>
                      <input
                        type="number"
                        defaultValue={tc.order}
                        onBlur={(e) => handleUpdateTC(tc.id, { order: parseInt(e.target.value) })}
                        className="input text-sm w-full"
                        min="0"
                      />
                    </div>
                  </div>
                </div>
              )}
              
              {editingTC !== tc.id && (
                <button
                  onClick={() => setEditingTC(tc.id)}
                  className="mt-2 text-xs text-gray-500 hover:text-gray-700 underline"
                >
                  Advanced settings
                </button>
              )}
              {editingTC === tc.id && (
                <button
                  onClick={() => setEditingTC(null)}
                  className="mt-2 text-xs text-gray-500 hover:text-gray-700 underline"
                >
                  Hide advanced settings
                </button>
              )}
            </div>
          ))}
        </div>

        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <p className="text-sm text-blue-800">
            <strong>💡 Tips:</strong> Click on any thermocouple name to rename it. Click the color circle to change its display color. 
            Each thermocouple must be connected to a unique CS (Chip Select) GPIO pin. 
            The control thermocouple is used for PID temperature control.
          </p>
        </div>
      </div>
    </div>
  )
}
