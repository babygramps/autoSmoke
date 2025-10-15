import { useState, useEffect } from 'react'
import { Smoke, CookingPhase } from '../types'

interface SessionTimeDisplayProps {
  smoke: Smoke
  currentPhase?: CookingPhase
  allPhases?: CookingPhase[]
}

export function SessionTimeDisplay({ smoke, currentPhase, allPhases }: SessionTimeDisplayProps) {
  const [elapsedTime, setElapsedTime] = useState<string>('0:00')
  const [estimatedFinish, setEstimatedFinish] = useState<string>('Calculating...')

  useEffect(() => {
    // Update elapsed time every minute
    const updateElapsed = () => {
      if (!smoke.started_at) return

      const startTime = new Date(smoke.started_at).getTime()
      const now = Date.now()
      const elapsedMs = now - startTime

      const hours = Math.floor(elapsedMs / (1000 * 60 * 60))
      const minutes = Math.floor((elapsedMs % (1000 * 60 * 60)) / (1000 * 60))

      setElapsedTime(`${hours}:${minutes.toString().padStart(2, '0')}`)
    }

    updateElapsed()
    const interval = setInterval(updateElapsed, 60000) // Update every minute

    return () => clearInterval(interval)
  }, [smoke.started_at])

  useEffect(() => {
    // Calculate estimated finish time
    if (!allPhases || allPhases.length === 0 || !currentPhase) {
      setEstimatedFinish('N/A')
      return
    }

    try {
      // Find completed phases
      const completedPhases = allPhases.filter(p => p.ended_at !== null)
      
      // Calculate time spent on completed phases
      let completedMinutes = 0
      completedPhases.forEach(phase => {
        if (phase.started_at && phase.ended_at) {
          const start = new Date(phase.started_at).getTime()
          const end = new Date(phase.ended_at).getTime()
          completedMinutes += (end - start) / (1000 * 60)
        }
      })

      // Estimate remaining time based on phase max durations
      let remainingMinutes = 0
      
      // Current phase: assume it takes max_duration_min
      if (currentPhase && currentPhase.completion_conditions) {
        const conditions = typeof currentPhase.completion_conditions === 'string' 
          ? JSON.parse(currentPhase.completion_conditions)
          : currentPhase.completion_conditions
        
        const phaseMax = conditions.max_duration_min || 60
        const phaseElapsed = currentPhase.started_at 
          ? (Date.now() - new Date(currentPhase.started_at).getTime()) / (1000 * 60)
          : 0
        
        remainingMinutes += Math.max(0, phaseMax - phaseElapsed)
      }

      // Future phases: sum their max durations
      const futurePhases = allPhases.filter(
        p => p.phase_order > (currentPhase?.phase_order || 0) && !p.ended_at
      )
      
      futurePhases.forEach(phase => {
        if (phase.completion_conditions) {
          const conditions = typeof phase.completion_conditions === 'string'
            ? JSON.parse(phase.completion_conditions)
            : phase.completion_conditions
          remainingMinutes += conditions.max_duration_min || 60
        }
      })

      // Calculate finish time
      const finishTime = new Date(Date.now() + remainingMinutes * 60 * 1000)
      const hours = finishTime.getHours()
      const minutes = finishTime.getMinutes()
      const ampm = hours >= 12 ? 'PM' : 'AM'
      const displayHours = hours % 12 || 12
      
      setEstimatedFinish(
        `${displayHours}:${minutes.toString().padStart(2, '0')} ${ampm}` +
        ` (~${Math.round(remainingMinutes / 60)}h ${Math.round(remainingMinutes % 60)}m remaining)`
      )
    } catch (error) {
      console.error('Error calculating finish time:', error)
      setEstimatedFinish('N/A')
    }
  }, [allPhases, currentPhase])

  return (
    <div className="card">
      <div className="grid grid-cols-2 gap-4">
        {/* Elapsed Time */}
        <div>
          <div className="text-sm font-medium text-gray-600 mb-1">⏱️ Elapsed Time</div>
          <div className="text-3xl font-bold text-primary-600">{elapsedTime}</div>
          <div className="text-xs text-gray-500 mt-1">
            Started {new Date(smoke.started_at).toLocaleTimeString([], { 
              hour: 'numeric', 
              minute: '2-digit' 
            })}
          </div>
        </div>

        {/* Estimated Finish */}
        <div>
          <div className="text-sm font-medium text-gray-600 mb-1">🎯 Est. Finish</div>
          <div className="text-lg font-semibold text-success-600">{estimatedFinish}</div>
          <div className="text-xs text-gray-500 mt-1">
            Based on phase durations
          </div>
        </div>
      </div>

      {/* Session Info */}
      <div className="mt-4 pt-4 border-t border-gray-200">
        <div className="text-sm text-gray-700">
          <span className="font-medium">{smoke.name}</span>
          {smoke.description && (
            <span className="text-gray-500 ml-2">• {smoke.description}</span>
          )}
        </div>
        {currentPhase && (
          <div className="text-xs text-gray-500 mt-1">
            Current: {currentPhase.phase_name.replace('_', ' ')} @ {currentPhase.target_temp_f}°F
          </div>
        )}
      </div>
    </div>
  )
}

