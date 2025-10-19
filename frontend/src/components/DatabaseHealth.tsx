import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'

interface DatabaseHealth {
  health_status: 'good' | 'warning' | 'critical'
  database_size_mb: number
  fragmentation_pct: number
  total_readings: number
  recommendations: Array<{
    severity: 'info' | 'warning' | 'critical'
    message: string
    action: string
  }>
}

export function DatabaseHealth() {
  const [health, setHealth] = useState<DatabaseHealth | null>(null)
  const [loading, setLoading] = useState(true)
  const [cleaning, setCleaning] = useState(false)
  const [optimizing, setOptimizing] = useState(false)

  const fetchHealth = async () => {
    try {
      setLoading(true)
      const response = await fetch('/api/maintenance/health')
      const data = await response.json()
      setHealth(data)
    } catch (error) {
      console.error('Failed to fetch database health:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchHealth()
    // Refresh every 5 minutes
    const interval = setInterval(fetchHealth, 5 * 60 * 1000)
    return () => clearInterval(interval)
  }, [])

  const handleCleanup = async (dryRun: boolean = false) => {
    if (!dryRun && !confirm('Are you sure you want to clean up old data? This cannot be undone.')) {
      return
    }

    try {
      setCleaning(true)
      const response = await fetch('/api/maintenance/cleanup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          reading_days: 30,
          event_days: 90,
          alert_days: 60,
          dry_run: dryRun
        })
      })
      const data = await response.json()
      
      if (dryRun) {
        alert(`Dry run complete:\n- Readings: ${data.stats.readings_deleted}\n- Events: ${data.stats.events_deleted}\n- Alerts: ${data.stats.alerts_deleted}`)
      } else {
        alert('Cleanup completed successfully!')
        await fetchHealth()
      }
    } catch (error) {
      console.error('Cleanup failed:', error)
      alert('Cleanup failed. Check console for details.')
    } finally {
      setCleaning(false)
    }
  }

  const handleOptimize = async () => {
    if (!confirm('Run database optimization? This may take a few moments.')) {
      return
    }

    try {
      setOptimizing(true)
      const response = await fetch('/api/maintenance/optimize', {
        method: 'POST'
      })
      const data = await response.json()
      
      if (data.status === 'success') {
        alert('Database optimization completed successfully!')
        await fetchHealth()
      } else {
        alert('Some optimization steps failed. Check server logs.')
      }
    } catch (error) {
      console.error('Optimization failed:', error)
      alert('Optimization failed. Check console for details.')
    } finally {
      setOptimizing(false)
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div className="flex items-center justify-center h-32">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  if (!health) {
    return null
  }

  const statusColors = {
    good: 'bg-success-100 text-success-800 border-success-300',
    warning: 'bg-warning-100 text-warning-800 border-warning-300',
    critical: 'bg-danger-100 text-danger-800 border-danger-300'
  }

  const statusIcons = {
    good: '✅',
    warning: '⚠️',
    critical: '🚨'
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
          <span>💾</span>
          <span>Database Health</span>
        </h3>
        <div className={`px-3 py-1 rounded-full border-2 font-semibold text-sm ${statusColors[health.health_status]}`}>
          {statusIcons[health.health_status]} {health.health_status.toUpperCase()}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-gray-900">{health.database_size_mb.toFixed(1)}</div>
          <div className="text-xs text-gray-600">Database Size (MB)</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-gray-900">{health.fragmentation_pct.toFixed(1)}%</div>
          <div className="text-xs text-gray-600">Fragmentation</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-gray-900">{(health.total_readings / 1000).toFixed(1)}k</div>
          <div className="text-xs text-gray-600">Total Readings</div>
        </div>
        <div className="text-center p-3 bg-gray-50 rounded-lg">
          <div className="text-2xl font-bold text-gray-900">{health.recommendations.length}</div>
          <div className="text-xs text-gray-600">Recommendations</div>
        </div>
      </div>

      {/* Recommendations */}
      {health.recommendations.length > 0 && (
        <div className="mb-4 space-y-2">
          <h4 className="text-sm font-semibold text-gray-700">Recommendations:</h4>
          {health.recommendations.map((rec, idx) => {
            const recColors = {
              info: 'bg-blue-50 border-blue-200 text-blue-800',
              warning: 'bg-warning-50 border-warning-200 text-warning-800',
              critical: 'bg-danger-50 border-danger-200 text-danger-800'
            }
            
            return (
              <div key={idx} className={`p-3 rounded-lg border ${recColors[rec.severity]}`}>
                <div className="text-sm">{rec.message}</div>
              </div>
            )
          })}
        </div>
      )}

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-2">
        <button
          onClick={() => handleCleanup(true)}
          disabled={cleaning}
          className="btn btn-sm btn-outline flex items-center gap-2"
        >
          <span>🔍</span>
          <span>Preview Cleanup</span>
        </button>
        <button
          onClick={() => handleCleanup(false)}
          disabled={cleaning}
          className="btn btn-sm btn-primary flex items-center gap-2"
        >
          {cleaning ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Cleaning...</span>
            </>
          ) : (
            <>
              <span>🧹</span>
              <span>Run Cleanup</span>
            </>
          )}
        </button>
        <button
          onClick={handleOptimize}
          disabled={optimizing}
          className="btn btn-sm btn-secondary flex items-center gap-2"
        >
          {optimizing ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>Optimizing...</span>
            </>
          ) : (
            <>
              <span>⚡</span>
              <span>Optimize</span>
            </>
          )}
        </button>
        <button
          onClick={fetchHealth}
          className="btn btn-sm btn-outline flex items-center gap-2"
        >
          <span>🔄</span>
          <span>Refresh</span>
        </button>
      </div>

      {/* Help Text */}
      <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-200">
        <p className="text-xs text-blue-800">
          <strong>Tip:</strong> Run cleanup periodically to maintain performance. Preview first to see what will be deleted.
          Optimize the database after cleanup to reclaim disk space.
        </p>
      </div>
    </div>
  )
}

