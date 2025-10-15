import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { PhaseConditions } from '../types'

interface EditPhaseDialogProps {
  isOpen: boolean
  onClose: () => void
  smokeId: number
  phaseId: number
  phaseName: string
  currentTargetTemp: number
  currentConditions: PhaseConditions
  onUpdated?: () => void
}

export function EditPhaseDialog({
  isOpen,
  onClose,
  smokeId,
  phaseId,
  phaseName,
  currentTargetTemp,
  currentConditions,
  onUpdated
}: EditPhaseDialogProps) {
  const [targetTemp, setTargetTemp] = useState(currentTargetTemp)
  const [stabilityRange, setStabilityRange] = useState(currentConditions.stability_range_f || 5)
  const [stabilityDuration, setStabilityDuration] = useState(currentConditions.stability_duration_min || 10)
  const [maxDuration, setMaxDuration] = useState(currentConditions.max_duration_min || 60)
  const [meatTempThreshold, setMeatTempThreshold] = useState(currentConditions.meat_temp_threshold_f || 165)
  
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  // Reset form when dialog opens
  useEffect(() => {
    if (isOpen) {
      setTargetTemp(currentTargetTemp)
      setStabilityRange(currentConditions.stability_range_f || 5)
      setStabilityDuration(currentConditions.stability_duration_min || 10)
      setMaxDuration(currentConditions.max_duration_min || 60)
      setMeatTempThreshold(currentConditions.meat_temp_threshold_f || 165)
      setError('')
    }
  }, [isOpen, currentTargetTemp, currentConditions])

  if (!isOpen) return null

  const handleSave = async () => {
    try {
      setLoading(true)
      setError('')

      // Build updated conditions object
      const updatedConditions: PhaseConditions = {}
      
      if (currentConditions.stability_range_f !== undefined) {
        updatedConditions.stability_range_f = stabilityRange
      }
      if (currentConditions.stability_duration_min !== undefined) {
        updatedConditions.stability_duration_min = stabilityDuration
      }
      if (currentConditions.max_duration_min !== undefined) {
        updatedConditions.max_duration_min = maxDuration
      }
      if (currentConditions.meat_temp_threshold_f !== undefined) {
        updatedConditions.meat_temp_threshold_f = meatTempThreshold
      }

      await apiClient.updatePhase(smokeId, phaseId, {
        target_temp_f: targetTemp,
        completion_conditions: updatedConditions
      })

      if (onUpdated) onUpdated()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update phase')
    } finally {
      setLoading(false)
    }
  }

  const phaseDisplayNames: Record<string, string> = {
    preheat: 'Preheat & Clean-burn',
    load_recover: 'Load & Recover',
    smoke: 'Smoke Phase',
    stall: 'Stall Management',
    finish_hold: 'Finish & Hold'
  }

  const displayName = phaseDisplayNames[phaseName] || phaseName

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
              Edit Phase: {displayName}
            </h2>
            <div className="text-sm text-gray-600 mt-1">
              Adjust temperature and completion conditions
            </div>
          </div>

          {/* Form */}
          <div className="space-y-4 mb-6">
            {/* Target Temperature */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Target Temperature (°F)
              </label>
              <input
                type="number"
                value={targetTemp}
                onChange={(e) => setTargetTemp(Number(e.target.value))}
                min={100}
                max={400}
                className="input"
                disabled={loading}
              />
            </div>

            {/* Stability Conditions */}
            {currentConditions.stability_range_f !== undefined && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Stability Range (±°F)
                  </label>
                  <input
                    type="number"
                    value={stabilityRange}
                    onChange={(e) => setStabilityRange(Number(e.target.value))}
                    min={1}
                    max={20}
                    className="input"
                    disabled={loading}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    Temperature must stay within ±{stabilityRange}°F of target
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Stability Duration (minutes)
                  </label>
                  <input
                    type="number"
                    value={stabilityDuration}
                    onChange={(e) => setStabilityDuration(Number(e.target.value))}
                    min={1}
                    max={60}
                    className="input"
                    disabled={loading}
                  />
                  <div className="text-xs text-gray-500 mt-1">
                    How long temperature must remain stable
                  </div>
                </div>
              </>
            )}

            {/* Meat Temperature Threshold */}
            {currentConditions.meat_temp_threshold_f !== undefined && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Meat Temperature Threshold (°F)
                </label>
                <input
                  type="number"
                  value={meatTempThreshold}
                  onChange={(e) => setMeatTempThreshold(Number(e.target.value))}
                  min={100}
                  max={250}
                  className="input"
                  disabled={loading}
                />
                <div className="text-xs text-gray-500 mt-1">
                  Phase completes when meat reaches this temperature
                </div>
              </div>
            )}

            {/* Maximum Duration */}
            {currentConditions.max_duration_min !== undefined && (
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Maximum Duration (minutes)
                </label>
                <input
                  type="number"
                  value={maxDuration}
                  onChange={(e) => setMaxDuration(Number(e.target.value))}
                  min={5}
                  max={720}
                  step={5}
                  className="input"
                  disabled={loading}
                />
                <div className="text-xs text-gray-500 mt-1">
                  Phase will complete after this time regardless of other conditions
                </div>
              </div>
            )}
          </div>

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
              disabled={loading}
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

