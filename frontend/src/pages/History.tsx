import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { Reading, ReadingStats, Smoke } from '../types'
import { format, subDays } from 'date-fns'

export function History() {
  const [readings, setReadings] = useState<Reading[]>([])
  const [stats, setStats] = useState<ReadingStats | null>(null)
  const [smokes, setSmokes] = useState<Smoke[]>([])
  const [selectedSmoke, setSelectedSmoke] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  
  // Date range state - default to last 24 hours
  const getDefaultDates = () => {
    const now = new Date()
    const yesterday = subDays(now, 1)
    return {
      fromDate: format(yesterday, 'yyyy-MM-dd'),
      toDate: format(now, 'yyyy-MM-dd'),
      fromTime: format(yesterday, 'HH:mm'),
      toTime: format(now, 'HH:mm')
    }
  }
  
  const defaults = getDefaultDates()
  const [fromDate, setFromDate] = useState(defaults.fromDate)
  const [toDate, setToDate] = useState(defaults.toDate)
  const [fromTime, setFromTime] = useState(defaults.fromTime)
  const [toTime, setToTime] = useState(defaults.toTime)
  
  // Pagination
  const [currentPage, setCurrentPage] = useState(1)
  const [totalPages, setTotalPages] = useState(1)
  const itemsPerPage = 100

  const fetchData = async () => {
    try {
      setLoading(true)
      setMessage('')
      
      const fromDateTime = new Date(`${fromDate}T${fromTime}:00`)
      const toDateTime = new Date(`${toDate}T${toTime}:00`)
      
      const [readingsResponse, statsResponse] = await Promise.all([
        apiClient.getReadings({
          smoke_id: selectedSmoke || undefined,
          from_time: fromDateTime.toISOString(),
          to_time: toDateTime.toISOString(),
          limit: itemsPerPage * currentPage,
        }),
        apiClient.getReadingStats({ 
          smoke_id: selectedSmoke || undefined,
          hours: 24 
        })
      ])
      
      setReadings(readingsResponse.readings)
      setStats(statsResponse)
      setTotalPages(Math.ceil(readingsResponse.count / itemsPerPage))
      
      // Data date range can be determined from readings if needed
      
      // Show helpful message if no data
      if (readingsResponse.count === 0) {
        setMessage('No data found for this date range. Try selecting a different time period or use "Last 24 Hours".')
      }
    } catch (error) {
      setMessage(`Error loading data: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Fetch smoke sessions on mount
    const fetchSmokes = async () => {
      try {
        const data = await apiClient.getSmokes({ limit: 50 })
        setSmokes(data.smokes)
      } catch (error) {
        console.error('Failed to load smokes:', error)
      }
    }
    fetchSmokes()
  }, [])

  useEffect(() => {
    fetchData()
  }, [fromDate, toDate, fromTime, toTime, currentPage, selectedSmoke])

  const handleExportCSV = async () => {
    try {
      const fromDateTime = new Date(`${fromDate}T${fromTime}:00`)
      const toDateTime = new Date(`${toDate}T${toTime}:00`)
      
      const blob = await apiClient.exportReadingsCSV(
        fromDateTime.toISOString(),
        toDateTime.toISOString()
      )
      
      const url = window.URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `readings_${fromDate}_to_${toDate}.csv`
      document.body.appendChild(a)
      a.click()
      window.URL.revokeObjectURL(url)
      document.body.removeChild(a)
      
      setMessage('CSV exported successfully')
    } catch (error) {
      setMessage(`Export failed: ${error instanceof Error ? error.message : 'Unknown error'}`)
    }
  }

  const handleQuickRange = (days: number) => {
    const end = new Date()
    const start = subDays(end, days)
    setFromDate(format(start, 'yyyy-MM-dd'))
    setToDate(format(end, 'yyyy-MM-dd'))
    setFromTime(format(start, 'HH:mm'))
    setToTime(format(end, 'HH:mm'))
    setCurrentPage(1)
    setMessage('') // Clear any previous messages
  }
  
  const handleTodayRange = () => {
    const now = new Date()
    const startOfToday = new Date(now)
    startOfToday.setHours(0, 0, 0, 0)
    
    setFromDate(format(startOfToday, 'yyyy-MM-dd'))
    setToDate(format(now, 'yyyy-MM-dd'))
    setFromTime('00:00')
    setToTime(format(now, 'HH:mm'))
    setCurrentPage(1)
    setMessage('') // Clear any previous messages
  }

  return (
    <div className="space-y-6">
      {/* Controls */}
      <div className="card">
        <h2 className="text-2xl font-bold text-gray-900 mb-6">Historical Data</h2>
        
        {/* Smoke Session Filter */}
        {smokes.length > 0 && (
          <div className="mb-6">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Filter by Session
            </label>
            <select
              value={selectedSmoke || ''}
              onChange={(e) => {
                setSelectedSmoke(e.target.value ? parseInt(e.target.value) : null)
                setCurrentPage(1)
                setMessage('')
              }}
              className="input max-w-md"
            >
              <option value="">All Sessions</option>
              {smokes.map(smoke => (
                <option key={smoke.id} value={smoke.id}>
                  {smoke.name} ({new Date(smoke.started_at).toLocaleDateString()})
                  {smoke.is_active && ' - Active'}
                </option>
              ))}
            </select>
          </div>
        )}
        
        {/* Quick Range Buttons */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-gray-700 mb-2">Quick Select</label>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={handleTodayRange}
              className="btn btn-outline btn-sm"
            >
              Today
            </button>
            <button
              onClick={() => handleQuickRange(1)}
              className="btn btn-outline btn-sm"
            >
              Last 24 Hours
            </button>
            <button
              onClick={() => handleQuickRange(7)}
              className="btn btn-outline btn-sm"
            >
              Last 7 Days
            </button>
            <button
              onClick={() => handleQuickRange(30)}
              className="btn btn-outline btn-sm"
            >
              Last 30 Days
            </button>
          </div>
        </div>

        {/* Date/Time Range */}
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Custom Date Range <span className="text-gray-500 font-normal">(your local time: {Intl.DateTimeFormat().resolvedOptions().timeZone})</span>
          </label>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div>
              <input
                type="date"
                value={fromDate}
                onChange={(e) => {
                  setFromDate(e.target.value)
                  setMessage('') // Clear message on user input
                }}
                className="input"
                placeholder="From Date"
              />
            </div>
            <div>
              <input
                type="time"
                value={fromTime}
                onChange={(e) => {
                  setFromTime(e.target.value)
                  setMessage('') // Clear message on user input
                }}
                className="input"
                placeholder="From Time"
              />
            </div>
            <div>
              <input
                type="date"
                value={toDate}
                onChange={(e) => {
                  setToDate(e.target.value)
                  setMessage('') // Clear message on user input
                }}
                className="input"
                placeholder="To Date"
              />
            </div>
            <div>
              <input
                type="time"
                value={toTime}
                onChange={(e) => {
                  setToTime(e.target.value)
                  setMessage('') // Clear message on user input
                }}
                className="input"
                placeholder="To Time"
              />
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center space-x-4">
          <button
            onClick={fetchData}
            disabled={loading}
            className="btn btn-primary disabled:opacity-50"
          >
            {loading ? 'Loading...' : 'Refresh'}
          </button>
          <button
            onClick={handleExportCSV}
            disabled={loading || readings.length === 0}
            className="btn btn-outline disabled:opacity-50"
          >
            Export CSV
          </button>
        </div>

        {/* Message */}
        {message && (
          <div className={`mt-4 p-3 rounded-lg ${
            message.startsWith('Error') 
              ? 'bg-danger-100 text-danger-700' 
              : 'bg-success-100 text-success-700'
          }`}>
            {message}
          </div>
        )}
      </div>

      {/* Statistics */}
      {stats && stats.stats && (
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Statistics</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div>
              <h4 className="text-sm font-medium text-gray-500 mb-2">Temperature Range (°F)</h4>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Min:</span>
                  <span className="font-medium">{stats.stats.temperature_f.min}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Max:</span>
                  <span className="font-medium">{stats.stats.temperature_f.max}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Avg:</span>
                  <span className="font-medium">{stats.stats.temperature_f.avg}</span>
                </div>
              </div>
            </div>
            
            <div>
              <h4 className="text-sm font-medium text-gray-500 mb-2">Temperature Range (°C)</h4>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Min:</span>
                  <span className="font-medium">{stats.stats.temperature_c.min}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Max:</span>
                  <span className="font-medium">{stats.stats.temperature_c.max}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Avg:</span>
                  <span className="font-medium">{stats.stats.temperature_c.avg}</span>
                </div>
              </div>
            </div>
            
            <div>
              <h4 className="text-sm font-medium text-gray-500 mb-2">Relay Usage</h4>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">On Time:</span>
                  <span className="font-medium">{stats.stats.relay_on_percentage.toFixed(1)}%</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-sm text-gray-600">Readings:</span>
                  <span className="font-medium">{stats.reading_count}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Data Table */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Readings</h3>
        
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="text-center">
              <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-600 mx-auto mb-2"></div>
              <p className="text-gray-600">Loading data...</p>
            </div>
          </div>
        ) : readings.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-600">No data found for the selected time range</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Timestamp
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Temp (°F)
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Setpoint (°F)
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      PID Output
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Relay
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Boost
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {readings.map((reading) => (
                    <tr key={reading.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {new Date(reading.ts).toLocaleString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {reading.temp_f.toFixed(1)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {reading.setpoint_f.toFixed(1)}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                        {reading.pid_output.toFixed(1)}%
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          reading.relay_state 
                            ? 'bg-success-100 text-success-800' 
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {reading.relay_state ? 'ON' : 'OFF'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          reading.boost_active 
                            ? 'bg-warning-100 text-warning-800' 
                            : 'bg-gray-100 text-gray-800'
                        }`}>
                          {reading.boost_active ? 'YES' : 'NO'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="mt-6 flex items-center justify-between">
                <div className="text-sm text-gray-700">
                  Showing page {currentPage} of {totalPages}
                </div>
                <div className="flex space-x-2">
                  <button
                    onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
                    disabled={currentPage === 1}
                    className="btn btn-outline btn-sm disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setCurrentPage(prev => Math.min(totalPages, prev + 1))}
                    disabled={currentPage === totalPages}
                    className="btn btn-outline btn-sm disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
