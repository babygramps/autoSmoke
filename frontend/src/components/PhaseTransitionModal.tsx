import { useState } from 'react'
import { apiClient } from '../api/client'

interface PhaseTransitionModalProps {
  isOpen: boolean
  onClose: () => void
  smokeId: number
  reason: string
  currentPhase: {
    id: number
    phase_name: string
    target_temp_f: number
  } | null
  nextPhase: {
    id: number
    phase_name: string
    target_temp_f: number
  } | null
  onApproved?: () => void
}

const phaseDisplayNames: Record<string, string> = {
  preheat: 'Preheat & Clean-burn',
  load_recover: 'Load & Recover',
  smoke: 'Smoke Phase',
  stall: 'Stall Management',
  finish_hold: 'Finish & Hold'
}

const phaseIcons: Record<string, string> = {
  preheat: '🔥',
  load_recover: '📦',
  smoke: '💨',
  stall: '⏳',
  finish_hold: '✨'
}

export function PhaseTransitionModal({
  isOpen,
  onClose,
  smokeId,
  reason,
  currentPhase,
  nextPhase,
  onApproved
}: PhaseTransitionModalProps) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  if (!isOpen) return null

  const handleApprove = async () => {
    try {
      setLoading(true)
      setError('')
      
      await apiClient.approvePhaseTransition(smokeId)
      
      if (onApproved) onApproved()
      onClose()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to approve transition')
    } finally {
      setLoading(false)
    }
  }

  const handleStay = () => {
    // Just close the modal - the phase will continue
    onClose()
  }

  const currentPhaseName = currentPhase ? phaseDisplayNames[currentPhase.phase_name] || currentPhase.phase_name : 'Current Phase'
  const nextPhaseName = nextPhase ? phaseDisplayNames[nextPhase.phase_name] || nextPhase.phase_name : 'Next Phase'
  const currentIcon = currentPhase ? phaseIcons[currentPhase.phase_name] || '📊' : '📊'
  const nextIcon = nextPhase ? phaseIcons[nextPhase.phase_name] || '📊' : '📊'

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto" onClick={onClose}>
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div className="fixed inset-0 bg-black bg-opacity-50 transition-opacity" />
        
        {/* Modal */}
        <div 
          className="relative bg-white rounded-lg shadow-xl max-w-lg w-full p-6"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="mb-4">
            <h2 className="text-2xl font-bold text-gray-900 mb-2">
              Phase Transition Ready 🎯
            </h2>
            <div className="text-sm text-gray-600">
              {reason}
            </div>
          </div>

          {/* Phase Comparison */}
          <div className="mb-6">
            <div className="grid grid-cols-2 gap-4">
              {/* Current Phase */}
              <div className="border-2 border-gray-300 rounded-lg p-4">
                <div className="text-xs text-gray-500 mb-1">Completing</div>
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-2xl">{currentIcon}</span>
                  <div className="font-semibold text-gray-900">{currentPhaseName}</div>
                </div>
                {currentPhase && (
                  <div className="text-sm text-gray-600">
                    {currentPhase.target_temp_f}°F
                  </div>
                )}
              </div>

              {/* Next Phase */}
              <div className="border-2 border-primary-500 bg-primary-50 rounded-lg p-4">
                <div className="text-xs text-primary-700 mb-1">Moving to</div>
                <div className="flex items-center space-x-2 mb-2">
                  <span className="text-2xl">{nextIcon}</span>
                  <div className="font-semibold text-primary-900">{nextPhaseName}</div>
                </div>
                {nextPhase && (
                  <div className="text-sm text-primary-700">
                    Target: {nextPhase.target_temp_f}°F
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Info Box */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="text-sm text-blue-900">
              <strong>What happens next?</strong>
              <ul className="mt-2 space-y-1 list-disc list-inside">
                <li>The current phase will be marked as complete</li>
                {nextPhase && currentPhase && nextPhase.target_temp_f !== currentPhase.target_temp_f && (
                  <li>Target temperature will change to {nextPhase.target_temp_f}°F</li>
                )}
                <li>Progress will be tracked for the new phase</li>
                <li>You can skip or modify phases at any time</li>
              </ul>
            </div>
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
              onClick={handleApprove}
              disabled={loading}
              className="flex-1 btn btn-primary disabled:opacity-50"
            >
              {loading ? 'Approving...' : 'Approve & Continue'}
            </button>
            <button
              onClick={handleStay}
              disabled={loading}
              className="flex-1 btn btn-outline"
            >
              Stay in Current Phase
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

