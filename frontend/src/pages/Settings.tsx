import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { Settings as SettingsType } from '../types'

export function Settings() {
  const [settings, setSettings] = useState<SettingsType | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  // Form state
  const [formData, setFormData] = useState<Partial<SettingsType>>({})

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        setLoading(true)
        const data = await apiClient.getSettings()
        setSettings(data)
        setFormData(data)
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
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Default Setpoint
              </label>
              <input
                type="number"
                value={formData.setpoint_f || 225}
                onChange={(e) => handleInputChange('setpoint_f', parseFloat(e.target.value))}
                className="input"
                min="100"
                max="400"
                step="1"
              />
              <p className="text-xs text-gray-500 mt-1">Temperature in Fahrenheit</p>
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
                  ? 'Simple on/off control with hysteresis - best for most smokers'
                  : 'PID control with time-based duty cycle - more precise but complex'}
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
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Hysteresis (°C)
                  </label>
                  <input
                    type="number"
                    value={formData.hyst_c || 0.6}
                    onChange={(e) => handleInputChange('hyst_c', parseFloat(e.target.value))}
                    className="input"
                    min="0"
                    max="5"
                    step="0.1"
                  />
                  <p className="text-xs text-gray-500 mt-1">Temperature deadband around setpoint</p>
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
                    Time window for duty cycle calculation (e.g., 60% PID output = 6s ON in 10s window)
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
                  High Alarm (°C)
                </label>
                <input
                  type="number"
                  value={formData.hi_alarm_c || 135.0}
                  onChange={(e) => handleInputChange('hi_alarm_c', parseFloat(e.target.value))}
                  className="input"
                  min="50"
                  max="200"
                  step="1"
                />
              </div>
              
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Low Alarm (°C)
                </label>
                <input
                  type="number"
                  value={formData.lo_alarm_c || 65.6}
                  onChange={(e) => handleInputChange('lo_alarm_c', parseFloat(e.target.value))}
                  className="input"
                  min="0"
                  max="150"
                  step="1"
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Stuck High Rate (°C/min)
                </label>
                <input
                  type="number"
                  value={formData.stuck_high_c || 2.0}
                  onChange={(e) => handleInputChange('stuck_high_c', parseFloat(e.target.value))}
                  className="input"
                  min="0"
                  max="10"
                  step="0.1"
                />
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
              <p className="text-xs text-gray-500 mt-1">Enable for development without hardware</p>
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
              <p className="text-xs text-gray-500 mt-1">Optional webhook for alert notifications</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
