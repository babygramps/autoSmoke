import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { CookingPhase, PhaseProgress as PhaseProgressType } from '../types'

interface PhaseProgressProps {
  smokeId: number
  currentPhase: {
    id: number
    phase_name: string
    phase_order: number
    target_temp_f: number
    started_at: string | null
    is_active: boolean
    completion_conditions: any
  } | null
  onEditPhase?: () => void
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

export function PhaseProgress({ smokeId, currentPhase, onEditPhase }: PhaseProgressProps) {
  const [phases, setPhases] = useState<CookingPhase[]>([])
  const [progress, setProgress] = useState<PhaseProgressType | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadPhases()
    const interval = setInterval(loadProgress, 5000) // Update progress every 5 seconds
    loadProgress()
    
    return () => clearInterval(interval)
  }, [smokeId])

  const loadPhases = async () => {
    try {
      const data = await apiClient.getSmokePhases(smokeId)
      setPhases(data.phases)
    } catch (error) {
      console.error('Failed to load phases:', error)
    }
  }

  const loadProgress = async () => {
    try {
      const data = await apiClient.getPhaseProgress(smokeId)
      setProgress(data)
    } catch (error) {
      console.error('Failed to load progress:', error)
    }
  }

  if (!currentPhase) {
    return (
      <div className="card">
        <div className="text-center text-gray-500 py-4">
          No active cooking phase
        </div>
      </div>
    )
  }

  const phaseName = currentPhase.phase_name
  const displayName = phaseDisplayNames[phaseName] || phaseName
  const icon = phaseIcons[phaseName] || '📊'

  const completedPhases = phases.filter(p => p.ended_at !== null)
  const currentPhaseIndex = phases.findIndex(p => p.id === currentPhase.id)
  const upcomingPhases = phases.filter((p, idx) => idx > currentPhaseIndex && !p.ended_at)

  // Format duration
  const formatDuration = (startedAt: string) => {
    const start = new Date(startedAt)
    const now = new Date()
    const minutes = Math.floor((now.getTime() - start.getTime()) / 60000)
    const hours = Math.floor(minutes / 60)
    const mins = minutes % 60
    if (hours > 0) {
      return `${hours}h ${mins}m`
    }
    return `${mins}m`
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900">Cooking Phase</h3>
        {onEditPhase && (
          <button
            onClick={onEditPhase}
            className="btn btn-sm btn-outline"
          >
            Edit Phase
          </button>
        )}
      </div>

      {/* Current Phase Card */}
      <div className="bg-primary-50 border-2 border-primary-200 rounded-lg p-4 mb-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center space-x-2">
            <span className="text-2xl">{icon}</span>
            <div>
              <div className="text-sm font-medium text-primary-700">Current Phase</div>
              <div className="text-xl font-bold text-primary-900">{displayName}</div>
            </div>
          </div>
          <div className="text-right">
            <div className="text-sm text-primary-700">Target</div>
            <div className="text-2xl font-bold text-primary-900">
              {currentPhase.target_temp_f}°F
            </div>
          </div>
        </div>

        {currentPhase.started_at && (
          <div className="text-xs text-primary-600 mb-3">
            Duration: {formatDuration(currentPhase.started_at)}
          </div>
        )}

        {/* Progress Bar */}
        {progress && progress.has_phase && progress.overall_progress !== undefined && (
          <div>
            <div className="flex justify-between text-xs text-primary-700 mb-1">
              <span>Progress</span>
              <span>{Math.round(progress.overall_progress)}%</span>
            </div>
            <div className="w-full bg-primary-200 rounded-full h-3 overflow-hidden">
              <div
                className="bg-primary-600 h-full transition-all duration-500 rounded-full"
                style={{ width: `${Math.min(100, progress.overall_progress)}%` }}
              />
            </div>

            {/* Progress Factors */}
            {progress.progress_factors && progress.progress_factors.length > 0 && (
              <div className="mt-3 space-y-2">
                {progress.progress_factors.map((factor, idx) => (
                  <div key={idx} className="text-xs">
                    <div className="flex justify-between text-primary-700">
                      <span className="capitalize">
                        {factor.type === 'meat_temp' ? 'Meat Temp' : factor.type.replace('_', ' ')}:
                      </span>
                      <span>
                        {factor.type === 'stability' && factor.in_range !== undefined && (
                          factor.in_range ? '✓ In Range' : '✗ Out of Range'
                        )}
                        {factor.met && ' ✅'}
                      </span>
                    </div>
                    <div className="flex items-center space-x-2 text-primary-600">
                      <span>{typeof factor.current === 'number' ? factor.current.toFixed(1) : factor.current}</span>
                      <span>/</span>
                      <span>{typeof factor.target === 'number' ? factor.target.toFixed(1) : factor.target}</span>
                      {factor.type.includes('temp') && <span>°F</span>}
                      {factor.type.includes('duration') && <span>min</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Phase Timeline */}
      <div>
        <div className="text-sm font-medium text-gray-700 mb-2">Phase Timeline</div>
        <div className="space-y-2">
          {/* Completed Phases */}
          {completedPhases.map((phase) => (
            <div key={phase.id} className="flex items-center space-x-2 text-sm">
              <div className="w-6 h-6 rounded-full bg-success-500 flex items-center justify-center text-white text-xs">
                ✓
              </div>
              <div className="flex-1">
                <span className="text-gray-600">{phaseDisplayNames[phase.phase_name]}</span>
                {phase.actual_duration_minutes && (
                  <span className="text-gray-400 text-xs ml-2">
                    ({phase.actual_duration_minutes}m)
                  </span>
                )}
              </div>
            </div>
          ))}

          {/* Current Phase in Timeline */}
          <div className="flex items-center space-x-2 text-sm">
            <div className="w-6 h-6 rounded-full bg-primary-500 flex items-center justify-center text-white text-xs animate-pulse">
              ▶
            </div>
            <div className="flex-1 font-medium text-primary-900">
              {displayName}
            </div>
          </div>

          {/* Upcoming Phases */}
          {upcomingPhases.map((phase) => (
            <div key={phase.id} className="flex items-center space-x-2 text-sm">
              <div className="w-6 h-6 rounded-full bg-gray-300 flex items-center justify-center text-gray-500 text-xs">
                {phase.phase_order + 1}
              </div>
              <div className="flex-1 text-gray-400">
                {phaseDisplayNames[phase.phase_name]}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Completion Conditions Info */}
      {currentPhase.completion_conditions && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="text-xs text-gray-600">
            <div className="font-medium mb-1">Completion Conditions:</div>
            <ul className="list-disc list-inside space-y-1">
              {currentPhase.completion_conditions.stability_range_f && (
                <li>
                  Temperature stable at {currentPhase.target_temp_f}°F ±
                  {currentPhase.completion_conditions.stability_range_f}°F for{' '}
                  {currentPhase.completion_conditions.stability_duration_min} minutes
                </li>
              )}
              {currentPhase.completion_conditions.meat_temp_threshold_f && (
                <li>
                  Meat temperature reaches {currentPhase.completion_conditions.meat_temp_threshold_f}°F
                </li>
              )}
              {currentPhase.completion_conditions.max_duration_min && (
                <li>
                  Maximum duration: {currentPhase.completion_conditions.max_duration_min} minutes
                </li>
              )}
            </ul>
          </div>
        </div>
      )}
    </div>
  )
}

