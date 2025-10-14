import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { Alert, AlertSummary } from '../types'
import { format, subDays } from 'date-fns'

interface AlarmsProps {
  alertSummary: AlertSummary | null
  onAlertUpdate: () => void
}

export function Alarms({ alertSummary, onAlertUpdate }: AlarmsProps) {
  const [alerts, setAlerts] = useState<Alert[]>([])
  const [loading, setLoading] = useState(true)
  const [message, setMessage] = useState('')
  const [showExportModal, setShowExportModal] = useState(false)
  
  // Export date range state
  const [fromDate, setFromDate] = useState(format(subDays(new Date(), 7), 'yyyy-MM-dd'))
  const [toDate, setToDate] = useState(format(new Date(), 'yyyy-MM-dd'))

  // Fetch alerts
  useEffect(() => {
    const fetchAlerts = async () => {
      try {
        setLoading(true)
        const response = await apiClient.getAlerts({ active_only: true, limit: 50 })
        setAlerts(response.alerts)
      } catch (error) {
        console.error('Failed to fetch alerts:', error)
        setMessage(`Error loading alerts: ${error instanceof Error ? error.message : 'Unknown error'}`)
      } finally {
        setLoading(false)
      }
    }

    fetchAlerts()
  }, [])

  const handleAcknowledge = async (alertId: number) => {
    try {
      await apiClient.acknowledgeAlert(alertId)
      setMessage('Alert acknowledged')
      // Refresh alerts
      const response = await apiClient.getAlerts({ active_only: true, limit: 50 })
      setAlerts(response.alerts)
      onAlertUpdate()
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleClear = async (alertId: number) => {
    try {
      await apiClient.clearAlert(alertId)
      setMessage('Alert cleared')
      // Refresh alerts
      const response = await apiClient.getAlerts({ active_only: true, limit: 50 })
      setAlerts(response.alerts)
      onAlertUpdate()
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleClearAll = async () => {
    try {
      const response = await apiClient.clearAllAlerts()
      setMessage(`Cleared ${response.cleared_count} alerts`)
      // Refresh alerts
      const alertsResponse = await apiClient.getAlerts({ active_only: true, limit: 50 })
      setAlerts(alertsResponse.alerts)
      onAlertUpdate()
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleExportAlerts = async () => {
    try {
      const fromDateTime = new Date(`${fromDate}T00:00:00`)
      const toDateTime = new Date(`${toDate}T23:59:59`)
      
      const blob = await apiClient.exportAlertsCSV(
        fromDateTime.toISOString(),
        toDateTime.toISOString()
      )
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `alerts_${fromDate}_to_${toDate}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      setMessage('Alerts CSV exported successfully')
      setShowExportModal(false)
    } catch (error) {
      setMessage(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleExportEvents = async () => {
    try {
      const fromDateTime = new Date(`${fromDate}T00:00:00`)
      const toDateTime = new Date(`${toDate}T23:59:59`)
      
      const blob = await apiClient.exportEventsCSV(
        fromDateTime.toISOString(),
        toDateTime.toISOString()
      )
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `events_${fromDate}_to_${toDate}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      setMessage('Events CSV exported successfully')
      setShowExportModal(false)
    } catch (error) {
      setMessage(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case 'critical':
        return 'badge-critical'
      case 'error':
        return 'badge-error'
      case 'warning':
        return 'badge-warning'
      case 'info':
        return 'badge-info'
      default:
        return 'badge-info'
    }
  }

  const getAlertTypeLabel = (alertType: string) => {
    switch (alertType) {
      case 'high_temp':
        return 'High Temperature'
      case 'low_temp':
        return 'Low Temperature'
      case 'stuck_high':
        return 'Stuck High'
      case 'sensor_fault':
        return 'Sensor Fault'
      default:
        return alertType
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div className="flex items-center justify-center h-32">
          <div className="text-center">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600 mx-auto mb-2"></div>
            <p className="text-gray-600">Loading alerts...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Alert Summary */}
      {alertSummary && alertSummary.count > 0 && (
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Alert Summary</h3>
            <div className="flex items-center space-x-2">
              <button
                onClick={() => setShowExportModal(true)}
                className="btn btn-outline btn-sm"
              >
                Export CSV
              </button>
              <button
                onClick={handleClearAll}
                className="btn btn-danger btn-sm"
              >
                Clear All
              </button>
            </div>
          </div>
          
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="text-center">
              <div className="text-2xl font-bold text-gray-900">{alertSummary.count}</div>
              <div className="text-sm text-gray-500">Total</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-600">{alertSummary.critical}</div>
              <div className="text-sm text-gray-500">Critical</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-red-500">{alertSummary.error}</div>
              <div className="text-sm text-gray-500">Error</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-yellow-500">{alertSummary.warning}</div>
              <div className="text-sm text-gray-500">Warning</div>
            </div>
            <div className="text-center">
              <div className="text-2xl font-bold text-orange-500">{alertSummary.unacknowledged}</div>
              <div className="text-sm text-gray-500">Unacknowledged</div>
            </div>
          </div>
        </div>
      )}

      {/* Alerts List */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Active Alerts</h3>
        
        {alerts.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-gray-400 text-4xl mb-2">✅</div>
            <p className="text-gray-600">No active alerts</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className={`p-4 rounded-lg border-l-4 ${
                  alert.severity === 'critical' ? 'border-red-500 bg-red-50' :
                  alert.severity === 'error' ? 'border-red-400 bg-red-50' :
                  alert.severity === 'warning' ? 'border-yellow-400 bg-yellow-50' :
                  'border-blue-400 bg-blue-50'
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center space-x-2 mb-2">
                      <span className={`badge ${getSeverityBadge(alert.severity)}`}>
                        {alert.severity.toUpperCase()}
                      </span>
                      <span className="text-sm font-medium text-gray-700">
                        {getAlertTypeLabel(alert.alert_type)}
                      </span>
                      {alert.acknowledged && (
                        <span className="badge badge-success">ACKNOWLEDGED</span>
                      )}
                    </div>
                    
                    <p className="text-gray-800 mb-2">{alert.message}</p>
                    
                    <div className="text-sm text-gray-500">
                      {new Date(alert.ts).toLocaleString()}
                    </div>
                  </div>
                  
                  <div className="flex items-center space-x-2 ml-4">
                    {!alert.acknowledged && (
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        className="btn btn-outline btn-sm"
                      >
                        Acknowledge
                      </button>
                    )}
                    <button
                      onClick={() => handleClear(alert.id)}
                      className="btn btn-danger btn-sm"
                    >
                      Clear
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Message */}
      {message && (
        <div className={`p-3 rounded-lg ${
          message.startsWith('Error') 
            ? 'bg-danger-100 text-danger-700' 
            : 'bg-success-100 text-success-700'
        }`}>
          {message}
        </div>
      )}

      {/* Export Modal */}
      {showExportModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
            <div className="p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">Export Data</h3>
              
              {/* Date Range */}
              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">From Date</label>
                  <input
                    type="date"
                    value={fromDate}
                    onChange={(e) => setFromDate(e.target.value)}
                    className="input w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">To Date</label>
                  <input
                    type="date"
                    value={toDate}
                    onChange={(e) => setToDate(e.target.value)}
                    className="input w-full"
                  />
                </div>
              </div>

              {/* Export Options */}
              <div className="space-y-3 mb-6">
                <button
                  onClick={handleExportAlerts}
                  className="btn btn-primary w-full"
                >
                  Export Alerts
                </button>
                <button
                  onClick={handleExportEvents}
                  className="btn btn-outline w-full"
                >
                  Export Events
                </button>
              </div>

              {/* Close Button */}
              <button
                onClick={() => setShowExportModal(false)}
                className="btn btn-outline w-full"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
