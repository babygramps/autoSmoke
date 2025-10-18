import { useEffect, useState } from 'react'
import { apiClient } from '../api/client'

interface FilteringStat {
  name: string
  outliers_rejected: number
  faults_detected: number
  window_size: number
}

interface FilteringStatsResponse {
  status: string
  message?: string
  stats: Record<number, FilteringStat>
  sim_mode?: boolean
}

export function FilteringStats() {
  const [data, setData] = useState<FilteringStatsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)

  const fetchStats = async () => {
    try {
      setError(null)
      const response = await apiClient.getFilteringStats()
      setData(response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch filtering stats')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
  }, [])

  useEffect(() => {
    if (!autoRefresh) return

    const interval = setInterval(fetchStats, 5000) // Refresh every 5 seconds
    return () => clearInterval(interval)
  }, [autoRefresh])

  if (loading) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Temperature Filtering</h3>
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Temperature Filtering</h3>
        <div className="bg-danger-50 border border-danger-200 rounded-lg p-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-danger-600 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
            <div className="flex-1">
              <h4 className="text-sm font-medium text-danger-800">Error Loading Stats</h4>
              <p className="text-sm text-danger-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (!data) return null

  // Handle different status messages
  if (data.status === 'simulation_mode') {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Temperature Filtering</h3>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
            Simulation Mode
          </span>
        </div>
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-blue-600 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
            </svg>
            <div>
              <h4 className="text-sm font-medium text-blue-800">Simulation Mode Active</h4>
              <p className="text-sm text-blue-700 mt-1">
                Filtering statistics are not available when using simulated sensors. Real hardware sensors use advanced filtering to reject noise and outliers.
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (data.status === 'no_real_sensors') {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Temperature Filtering</h3>
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
            Fallback Mode
          </span>
        </div>
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
          <div className="flex items-start">
            <svg className="w-5 h-5 text-yellow-600 mt-0.5 mr-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
            </svg>
            <div>
              <h4 className="text-sm font-medium text-yellow-800">All Sensors Using Fallback Simulation</h4>
              <p className="text-sm text-yellow-700 mt-1">
                {data.message || 'No real thermocouples detected. Check sensor connections and restart the controller.'}
              </p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const statsArray = Object.entries(data.stats).map(([id, stat]) => ({
    id: Number(id),
    ...stat
  }))

  const totalOutliers = statsArray.reduce((sum, s) => sum + s.outliers_rejected, 0)
  const totalFaults = statsArray.reduce((sum, s) => sum + s.faults_detected, 0)

  const getHealthStatus = (stat: FilteringStat & { id: number }) => {
    if (stat.faults_detected > 10) return { label: 'Critical', color: 'danger' }
    if (stat.outliers_rejected > 50) return { label: 'Warning', color: 'warning' }
    if (stat.faults_detected > 0 || stat.outliers_rejected > 0) return { label: 'Active', color: 'info' }
    return { label: 'Healthy', color: 'success' }
  }

  return (
    <div className="card">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Temperature Filtering</h3>
          <p className="text-sm text-gray-600 mt-1">
            Real-time noise rejection and outlier detection statistics
          </p>
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={`inline-flex items-center px-3 py-1.5 text-xs font-medium rounded-lg transition-colors ${
              autoRefresh
                ? 'bg-primary-100 text-primary-700 hover:bg-primary-200'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            <svg className={`w-4 h-4 mr-1.5 ${autoRefresh ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            {autoRefresh ? 'Auto-Refresh' : 'Paused'}
          </button>
          <button
            onClick={fetchStats}
            className="inline-flex items-center px-3 py-1.5 text-xs font-medium text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
          >
            <svg className="w-4 h-4 mr-1.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            Refresh
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-gradient-to-br from-primary-50 to-primary-100 rounded-lg p-4 border border-primary-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-primary-900">Active Sensors</p>
              <p className="text-2xl font-bold text-primary-700 mt-1">{statsArray.length}</p>
            </div>
            <div className="w-12 h-12 bg-primary-200 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-warning-50 to-warning-100 rounded-lg p-4 border border-warning-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-warning-900">Outliers Rejected</p>
              <p className="text-2xl font-bold text-warning-700 mt-1">{totalOutliers}</p>
            </div>
            <div className="w-12 h-12 bg-warning-200 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-warning-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
          </div>
        </div>

        <div className="bg-gradient-to-br from-danger-50 to-danger-100 rounded-lg p-4 border border-danger-200">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-danger-900">Faults Detected</p>
              <p className="text-2xl font-bold text-danger-700 mt-1">{totalFaults}</p>
            </div>
            <div className="w-12 h-12 bg-danger-200 rounded-full flex items-center justify-center">
              <svg className="w-6 h-6 text-danger-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          </div>
        </div>
      </div>

      {/* Individual Sensor Stats */}
      <div className="space-y-3">
        {statsArray.map((stat) => {
          const health = getHealthStatus(stat)
          return (
            <div
              key={stat.id}
              className="bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-gray-300 transition-colors"
            >
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white rounded-lg shadow-sm flex items-center justify-center border border-gray-200">
                    <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                    </svg>
                  </div>
                  <div>
                    <h4 className="text-sm font-semibold text-gray-900">{stat.name}</h4>
                    <p className="text-xs text-gray-600">ID: {stat.id}</p>
                  </div>
                </div>
                <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold bg-${health.color}-100 text-${health.color}-800 border border-${health.color}-200`}>
                  <span className={`w-2 h-2 rounded-full bg-${health.color}-500 mr-1.5`}></span>
                  {health.label}
                </span>
              </div>

              <div className="grid grid-cols-3 gap-4">
                {/* Outliers */}
                <div className="text-center">
                  <div className="inline-flex items-center justify-center w-full mb-1">
                    <svg className="w-4 h-4 text-warning-600 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                    <span className="text-xs font-medium text-gray-600">Outliers</span>
                  </div>
                  <p className={`text-2xl font-bold ${stat.outliers_rejected > 0 ? 'text-warning-700' : 'text-gray-400'}`}>
                    {stat.outliers_rejected}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">rejected</p>
                </div>

                {/* Faults */}
                <div className="text-center border-x border-gray-200">
                  <div className="inline-flex items-center justify-center w-full mb-1">
                    <svg className="w-4 h-4 text-danger-600 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    <span className="text-xs font-medium text-gray-600">Faults</span>
                  </div>
                  <p className={`text-2xl font-bold ${stat.faults_detected > 0 ? 'text-danger-700' : 'text-gray-400'}`}>
                    {stat.faults_detected}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">detected</p>
                </div>

                {/* Window Size */}
                <div className="text-center">
                  <div className="inline-flex items-center justify-center w-full mb-1">
                    <svg className="w-4 h-4 text-success-600 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <span className="text-xs font-medium text-gray-600">Filter</span>
                  </div>
                  <p className="text-2xl font-bold text-success-700">
                    {stat.window_size}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">samples</p>
                </div>
              </div>

              {/* Progress bars for visual representation */}
              {(stat.outliers_rejected > 0 || stat.faults_detected > 0) && (
                <div className="mt-3 pt-3 border-t border-gray-200 space-y-2">
                  {stat.outliers_rejected > 0 && (
                    <div>
                      <div className="flex justify-between text-xs text-gray-600 mb-1">
                        <span>Outlier Detection Active</span>
                        <span className="font-medium text-warning-700">{stat.outliers_rejected} events</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1.5">
                        <div 
                          className="bg-warning-500 h-1.5 rounded-full transition-all duration-500" 
                          style={{ width: `${Math.min((stat.outliers_rejected / 100) * 100, 100)}%` }}
                        ></div>
                      </div>
                    </div>
                  )}
                  {stat.faults_detected > 0 && (
                    <div>
                      <div className="flex justify-between text-xs text-gray-600 mb-1">
                        <span>Fault Recovery Active</span>
                        <span className="font-medium text-danger-700">{stat.faults_detected} events</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-1.5">
                        <div 
                          className="bg-danger-500 h-1.5 rounded-full transition-all duration-500" 
                          style={{ width: `${Math.min((stat.faults_detected / 50) * 100, 100)}%` }}
                        ></div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Info Footer */}
      <div className="mt-6 pt-4 border-t border-gray-200">
        <div className="flex items-start gap-2 text-xs text-gray-600">
          <svg className="w-4 h-4 text-gray-400 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          <p>
            Temperature filtering uses a 5-sample median window with outlier rejection (&gt;8°F jumps, &gt;3°F/s rate) and double-read verification. 
            High outlier counts may indicate electrical interference or sensor issues requiring hardware improvements.
          </p>
        </div>
      </div>
    </div>
  )
}

