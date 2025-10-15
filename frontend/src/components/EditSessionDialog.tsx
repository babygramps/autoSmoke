import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { Smoke, Thermocouple } from '../types'

interface EditSessionDialogProps {
  isOpen: boolean
  onClose: () => void
  smoke: Smoke
  thermocouples: Thermocouple[]
  onUpdated?: () => void
}

export function EditSessionDialog({
  isOpen,
  onClose,
  smoke,
  thermocouples,
  onUpdated
}: EditSessionDialogProps) {
  const [name, setName] = useState(smoke.name)
  const [description, setDescription] = useState(smoke.description || '')
  
  // Temperature presets
  const [preheatTemp, setPreheatTemp] = useState<number>(270)
  const [cookTemp, setCookTemp] = useState<number>(225)
  const [finishTemp, setFinishTemp] = useState<number>(160)
  
  // Phase timing
  const [preheatDuration, setPreheatDuration] = useState<number>(60)  // max duration in minutes
  const [preheatStability, setPreheatStability] = useState<number>(10)  // stability hold time in minutes
  const [cookDuration, setCookDuration] = useState<number>(360)  // cook phase max duration (6 hours)
  const [finishDuration, setFinishDuration] = useState<number>(120)  // finish phase max duration (2 hours)
  
  // Meat probe settings
  const [meatTargetTemp, setMeatTargetTemp] = useState<number | undefined>(
    (smoke as any).meat_target_temp_f || undefined
  )
  const [meatProbeId, setMeatProbeId] = useState<number | undefined>(
    (smoke as any).meat_probe_tc_id || undefined
  )
  
  // Stall detection
  const [enableStallDetection, setEnableStallDetection] = useState<boolean>(true)
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // Reset form when dialog opens or smoke changes
  useEffect(() => {
    if (isOpen) {
      setName(smoke.name)
      setDescription(smoke.description || '')
      setMeatTargetTemp((smoke as any).meat_target_temp_f || undefined)
      setMeatProbeId((smoke as any).meat_probe_tc_id || undefined)
      
      // Load temperature presets and timing from smoke config
      const smokeAny = smoke as any
      setPreheatTemp(smokeAny.preheat_temp_f || 270)
      setCookTemp(smokeAny.cook_temp_f || 225)
      setFinishTemp(smokeAny.finish_temp_f || 160)
      setPreheatDuration(smokeAny.preheat_duration_min || 60)
      setPreheatStability(smokeAny.preheat_stability_min || 10)
      setCookDuration(smokeAny.cook_duration_min || 360)
      setFinishDuration(smokeAny.finish_duration_min || 120)
      setEnableStallDetection(smokeAny.enable_stall_detection !== false) // default true
      
      setError('')
      setSuccessMessage('')
    }
  }, [isOpen, smoke])

  if (!isOpen) return null

  const handleSave = async () => {
    try {
      setLoading(true)
      setError('')
      setSuccessMessage('')

      await apiClient.updateSmoke(smoke.id, {
        name: name.trim() || undefined,
        description: description.trim() || undefined,
        meat_target_temp_f: meatTargetTemp,
        meat_probe_tc_id: meatProbeId,
        preheat_temp_f: preheatTemp,
        cook_temp_f: cookTemp,
        finish_temp_f: finishTemp,
        enable_stall_detection: enableStallDetection,
        preheat_duration_min: preheatDuration,
        preheat_stability_min: preheatStability,
        cook_duration_min: cookDuration,
        finish_duration_min: finishDuration
      })

      setSuccessMessage('Session settings updated successfully')
      
      if (onUpdated) {
        onUpdated()
      }
      
      // Close after a brief delay to show success message
      setTimeout(() => {
        onClose()
      }, 1500)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update session')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" onClick={onClose}>
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" />
        
        {/* Dialog */}
        <div 
          className="relative bg-white rounded-lg shadow-xl max-w-md w-full p-6"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="mb-4">
            <h2 className="text-xl font-bold text-gray-900">
              Edit Session Settings
            </h2>
            <div className="text-sm text-gray-600 mt-1">
              Update session parameters during cooking
            </div>
          </div>

          {/* Form */}
          <div className="space-y-4 mb-6">
            {/* Session Name */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Session Name
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g., Saturday Brisket"
                className="input"
                disabled={loading}
              />
            </div>

            {/* Description */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Description
              </label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional notes about this session"
                className="input"
                rows={3}
                disabled={loading}
              />
            </div>

            {/* Temperature Presets */}
            <div className="border-t pt-4">
              <div className="text-sm font-medium text-gray-700 mb-3">
                🌡️ Temperature Presets
              </div>
              
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    Preheat (°F)
                  </label>
                  <input
                    type="number"
                    value={preheatTemp}
                    onChange={(e) => setPreheatTemp(Number(e.target.value))}
                    className="input"
                    min={200}
                    max={300}
                    disabled={loading}
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    Cook (°F)
                  </label>
                  <input
                    type="number"
                    value={cookTemp}
                    onChange={(e) => setCookTemp(Number(e.target.value))}
                    className="input"
                    min={180}
                    max={275}
                    disabled={loading}
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    Finish (°F)
                  </label>
                  <input
                    type="number"
                    value={finishTemp}
                    onChange={(e) => setFinishTemp(Number(e.target.value))}
                    className="input"
                    min={140}
                    max={200}
                    disabled={loading}
                  />
                </div>
              </div>
              <div className="text-xs text-gray-500 mt-2">
                These temperatures are applied to the cooking phases
              </div>
              
              {/* Phase Timing Controls */}
              <div className="mt-3 space-y-3">
                {/* Preheat Timing */}
                <div>
                  <div className="text-xs font-semibold text-gray-700 mb-2">Preheat Phase</div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">
                        Max Time (min)
                      </label>
                      <input
                        type="number"
                        value={preheatDuration}
                        onChange={(e) => setPreheatDuration(Number(e.target.value))}
                        className="input"
                        min={15}
                        max={120}
                        disabled={loading}
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-600 mb-1">
                        Hold Stable (min)
                      </label>
                      <input
                        type="number"
                        value={preheatStability}
                        onChange={(e) => setPreheatStability(Number(e.target.value))}
                        className="input"
                        min={3}
                        max={30}
                        disabled={loading}
                      />
                    </div>
                  </div>
                </div>

                {/* Cook Phase Timing */}
                <div>
                  <div className="text-xs font-semibold text-gray-700 mb-2">Cook Phase</div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      Max Duration (min)
                    </label>
                    <input
                      type="number"
                      value={cookDuration}
                      onChange={(e) => setCookDuration(Number(e.target.value))}
                      className="input"
                      min={60}
                      max={720}
                      step={30}
                      disabled={loading}
                    />
                    <div className="text-xs text-gray-500 mt-1">
                      Default: 360 min (6 hours)
                    </div>
                  </div>
                </div>

                {/* Finish Phase Timing */}
                <div>
                  <div className="text-xs font-semibold text-gray-700 mb-2">Finish & Hold Phase</div>
                  <div>
                    <label className="block text-xs text-gray-600 mb-1">
                      Max Duration (min)
                    </label>
                    <input
                      type="number"
                      value={finishDuration}
                      onChange={(e) => setFinishDuration(Number(e.target.value))}
                      className="input"
                      min={30}
                      max={360}
                      step={15}
                      disabled={loading}
                    />
                    <div className="text-xs text-gray-500 mt-1">
                      Default: 120 min (2 hours)
                    </div>
                  </div>
                </div>
              </div>
            </div>

            {/* Meat Probe Settings */}
            <div className="border-t pt-4">
              <div className="text-sm font-medium text-gray-700 mb-3">
                🥩 Meat Probe Settings
              </div>
              
              <div className="space-y-3">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    Target Temperature (°F)
                  </label>
                  <input
                    type="number"
                    value={meatTargetTemp || ''}
                    onChange={(e) => setMeatTargetTemp(e.target.value ? Number(e.target.value) : undefined)}
                    placeholder="e.g., 203 for brisket"
                    className="input"
                    min={100}
                    max={250}
                    disabled={loading}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    Leave empty if not using a meat probe
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    Meat Probe Thermocouple
                  </label>
                  <select
                    value={meatProbeId || ''}
                    onChange={(e) => setMeatProbeId(e.target.value ? Number(e.target.value) : undefined)}
                    className="input"
                    disabled={loading}
                  >
                    <option value="">None</option>
                    {thermocouples.filter(tc => tc.enabled).map(tc => (
                      <option key={tc.id} value={tc.id}>
                        {tc.name}
                      </option>
                    ))}
                  </select>
                  <div className="text-xs text-gray-500 mt-1">
                    Select which thermocouple is monitoring the meat
                  </div>
                </div>
              </div>
            </div>

            {/* Stall Detection */}
            <div className="border-t pt-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-gray-700">
                    ⏱️ Stall Detection
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    Automatically manage temperature during the stall
                  </div>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enableStallDetection}
                    onChange={(e) => setEnableStallDetection(e.target.checked)}
                    className="sr-only peer"
                    disabled={loading}
                  />
                  <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-primary-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-primary-600"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Success Message */}
          {successMessage && (
            <div className="mb-4 p-3 bg-success-100 text-success-700 rounded-lg text-sm">
              ✓ {successMessage}
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="mb-4 p-3 bg-danger-100 text-danger-700 rounded-lg text-sm">
              {error}
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex space-x-3">
            <button
              onClick={handleSave}
              disabled={loading || !name.trim()}
              className="flex-1 btn btn-primary disabled:opacity-50"
            >
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
            <button
              onClick={onClose}
              disabled={loading}
              className="flex-1 btn btn-outline"
            >
              Cancel
            </button>
          </div>

          {/* Close Button */}
          <button
            onClick={onClose}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
            disabled={loading}
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

