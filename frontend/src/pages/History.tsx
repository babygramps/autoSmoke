import { useState, useEffect, useRef } from 'react'
import { apiClient } from '../api/client'
import { Reading, ReadingStats, Smoke, Thermocouple } from '../types'
import { format, subDays } from 'date-fns'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale,
} from 'chart.js'
import { Line } from 'react-chartjs-2'
import 'chartjs-adapter-date-fns'

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  TimeScale
)

export function History() {
  const [readings, setReadings] = useState<Reading[]>([])
  const [stats, setStats] = useState<ReadingStats | null>(null)
  const [smokes, setSmokes] = useState<Smoke[]>([])
  const [selectedSmoke, setSelectedSmoke] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [thermocouples, setThermocouples] = useState<Thermocouple[]>([])
  const [units, setUnits] = useState<'F' | 'C'>('F')
  const chartRef = useRef<ChartJS<'line', number[], string>>(null)
  
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
      
      console.log('Fetching history data:', {
        fromDateTime: fromDateTime.toISOString(),
        toDateTime: toDateTime.toISOString(),
        selectedSmoke,
        currentPage
      })
      
      const [readingsResponse, statsResponse] = await Promise.all([
        apiClient.getReadings({
          smoke_id: selectedSmoke || undefined,
          from_time: fromDateTime.toISOString(),
          to_time: toDateTime.toISOString(),
          limit: itemsPerPage * currentPage,
          include_thermocouples: true, // Include thermocouple data for the chart
        }),
        apiClient.getReadingStats({ 
          smoke_id: selectedSmoke || undefined,
          hours: 24 
        })
      ])
      
      console.log('History data fetched:', {
        readingsCount: readingsResponse.count,
        readingsLength: readingsResponse.readings.length,
        hasThermocoupleData: readingsResponse.readings.some(r => r.thermocouple_readings),
        statsAvailable: !!statsResponse.stats
      })
      
      setReadings(readingsResponse.readings)
      setStats(statsResponse)
      setTotalPages(Math.ceil(readingsResponse.count / itemsPerPage))
      
      // Data date range can be determined from readings if needed
      
      // Show helpful message if no data
      if (readingsResponse.count === 0) {
        setMessage('No data found for this date range. Try selecting a different time period or use "Last 24 Hours".')
      }
    } catch (error) {
      console.error('Error fetching history data:', error)
      setMessage(`Error loading data: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Fetch smoke sessions, thermocouples, and settings on mount
    const fetchInitialData = async () => {
      try {
        console.log('Fetching initial data for History page...')
        const [smokesData, thermocoupleSata, settings] = await Promise.all([
          apiClient.getSmokes({ limit: 50 }),
          apiClient.getThermocouples(),
          apiClient.getSettings(),
        ])
        const enabledThermocouples = thermocoupleSata.thermocouples.filter(tc => tc.enabled).sort((a, b) => a.order - b.order)
        console.log('Initial data loaded:', {
          smokesCount: smokesData.smokes.length,
          thermocoplesCount: enabledThermocouples.length,
          units: settings.units
        })
        setSmokes(smokesData.smokes)
        setThermocouples(enabledThermocouples)
        setUnits(settings.units)
      } catch (error) {
        console.error('Failed to load initial data:', error)
      }
    }
    fetchInitialData()
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

  // Chart helper functions
  const calculateTempRange = () => {
    if (readings.length === 0) {
      return units === 'F' ? { min: 100, max: 300 } : { min: 40, max: 150 }
    }
    
    const temps = readings.map(point => units === 'F' ? point.temp_f : point.temp_c)
    const setpoints = readings.map(point => units === 'F' ? point.setpoint_f : point.setpoint_c)
    
    // Also include all thermocouple readings
    const tcTemps: number[] = []
    readings.forEach(point => {
      if (point.thermocouple_readings) {
        Object.values(point.thermocouple_readings).forEach(reading => {
          if (reading && !reading.fault) {
            tcTemps.push(units === 'F' ? reading.temp_f : reading.temp_c)
          }
        })
      }
    })
    
    const allValues = [...temps, ...setpoints, ...tcTemps].filter(v => v !== null && v !== undefined)
    
    if (allValues.length === 0) {
      return units === 'F' ? { min: 100, max: 300 } : { min: 40, max: 150 }
    }
    
    const minTemp = Math.min(...allValues)
    const maxTemp = Math.max(...allValues)
    
    // Add 10% padding above and below for better visibility
    const range = maxTemp - minTemp
    const padding = Math.max(range * 0.15, units === 'F' ? 20 : 10) // At least 20°F or 10°C padding
    
    return {
      min: Math.floor(minTemp - padding),
      max: Math.ceil(maxTemp + padding)
    }
  }

  // Custom plugin to draw heater ON periods as background shading
  const heaterBackgroundPlugin = {
    id: 'heaterBackground',
    beforeDatasetsDraw: (chart: any) => {
      const { ctx, chartArea, scales, data } = chart
      if (!chartArea || !scales.x || !scales.y || !data.labels || data.labels.length === 0) return
      
      // Find the hidden relay state dataset
      const relayDataset = data.datasets.find((ds: any) => ds.label === '__relay_state__')
      if (!relayDataset || !relayDataset.data) return
      
      // Get heater ON periods from the relay state data
      const periods: Array<{ start: string; end: string }> = []
      let currentPeriodStart: string | null = null
      
      relayDataset.data.forEach((value: number, index: number) => {
        const timestamp = data.labels[index]
        
        if (value === 1 && !currentPeriodStart) {
          // Heater turned ON
          currentPeriodStart = timestamp
        } else if (value === 0 && currentPeriodStart) {
          // Heater turned OFF
          periods.push({
            start: currentPeriodStart,
            end: timestamp
          })
          currentPeriodStart = null
        }
      })
      
      // If heater is still on at the end
      if (currentPeriodStart && data.labels.length > 0) {
        periods.push({
          start: currentPeriodStart,
          end: data.labels[data.labels.length - 1]
        })
      }
      
      ctx.save()
      
      periods.forEach(period => {
        const xStart = scales.x.getPixelForValue(new Date(period.start).getTime())
        const xEnd = scales.x.getPixelForValue(new Date(period.end).getTime())
        
        // Draw semi-transparent green rectangle spanning the full chart height
        ctx.fillStyle = 'rgba(34, 197, 94, 0.15)' // Green with 15% opacity
        ctx.fillRect(
          xStart,
          chartArea.top,
          xEnd - xStart,
          chartArea.bottom - chartArea.top
        )
        
        // Add subtle left border to mark the start
        ctx.strokeStyle = 'rgba(34, 197, 94, 0.3)'
        ctx.lineWidth = 2
        ctx.beginPath()
        ctx.moveTo(xStart, chartArea.top)
        ctx.lineTo(xStart, chartArea.bottom)
        ctx.stroke()
      })
      
      ctx.restore()
    }
  }

  // Build datasets dynamically based on available thermocouples
  const buildDatasets = () => {
    const datasets: any[] = []
    
    // Add a dataset for each thermocouple
    thermocouples.forEach((tc) => {
      const data = readings.map(point => {
        const reading = point.thermocouple_readings?.[tc.id]
        if (!reading || reading.fault) return null
        return units === 'F' ? reading.temp_f : reading.temp_c
      })
      
      datasets.push({
        label: `${tc.name} (${units})`,
        data: data,
        borderColor: tc.color,
        backgroundColor: `${tc.color}20`, // Add transparency
        borderWidth: tc.is_control ? 3 : 2, // Thicker line for control thermocouple
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        fill: false,
        spanGaps: true, // Connect line even if there are null values
      })
    })
    
    // Add setpoint line
    datasets.push({
      label: `Setpoint (${units})`,
      data: readings.map(point => units === 'F' ? point.setpoint_f : point.setpoint_c),
      borderColor: 'rgb(59, 130, 246)',
      backgroundColor: 'rgba(59, 130, 246, 0.05)',
      borderDash: [10, 5],
      borderWidth: 2,
      tension: 0.4,
      pointRadius: 0,
      pointHoverRadius: 4,
      fill: false,
    })
    
    // Add hidden relay state dataset for the background plugin
    datasets.push({
      label: '__relay_state__',
      data: readings.map(point => point.relay_state ? 1 : 0),
      hidden: true,
      pointRadius: 0,
    })
    
    return datasets
  }

  const tempRange = calculateTempRange()
  const chartConfig = {
    labels: readings.map(point => point.ts),
    datasets: buildDatasets(),
  }

  const chartOptions = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: 'index' as const,
      intersect: false,
    },
    scales: {
      x: {
        type: 'time' as const,
        time: {
          displayFormats: {
            minute: 'h:mm a',
            hour: 'h:mm a',
          },
          tooltipFormat: 'MMM d, h:mm a',
        },
        bounds: 'data' as const,
        adapters: {
          date: {
            locale: undefined,
          },
        },
        title: {
          display: true,
          text: 'Time',
          color: 'rgb(107, 114, 128)',
          font: {
            size: 12,
            weight: 500,
          },
        },
        grid: {
          color: 'rgba(0, 0, 0, 0.05)',
        },
        ticks: {
          color: 'rgb(107, 114, 128)',
          maxRotation: 45,
          minRotation: 0,
          autoSkip: true,
          maxTicksLimit: 10,
          source: 'data' as const,
        },
      },
      y: {
        type: 'linear' as const,
        display: true,
        position: 'left' as const,
        title: {
          display: true,
          text: `Temperature (°${units})`,
          color: 'rgb(55, 65, 81)',
          font: {
            size: 13,
            weight: 600,
          },
        },
        min: tempRange.min,
        max: tempRange.max,
        grid: {
          color: 'rgba(0, 0, 0, 0.08)',
        },
        ticks: {
          color: 'rgb(107, 114, 128)',
          callback: function(value: any) {
            return value.toFixed(0) + '°'
          },
        },
      },
    },
    plugins: {
      legend: {
        position: 'top' as const,
        labels: {
          usePointStyle: true,
          padding: 15,
          font: {
            size: 12,
            weight: 500,
          },
          color: 'rgb(55, 65, 81)',
        },
      },
      title: {
        display: false,
      },
      tooltip: {
        backgroundColor: 'rgba(17, 24, 39, 0.95)',
        titleColor: 'rgb(255, 255, 255)',
        bodyColor: 'rgb(229, 231, 235)',
        borderColor: 'rgba(255, 255, 255, 0.1)',
        borderWidth: 1,
        padding: 12,
        displayColors: true,
        callbacks: {
          title: (items: any) => {
            if (items[0]) {
              const date = new Date(items[0].parsed.x)
              return date.toLocaleString()
            }
            return ''
          },
          label: (context: any) => {
            const label = context.dataset.label || ''
            const value = context.parsed.y
            if (value === null || value === undefined) return `${label}: N/A`
            return `${label}: ${value.toFixed(1)}°${units}`
          },
          afterBody: (items: any) => {
            const dataIndex = items[0].dataIndex
            const point = readings[dataIndex]
            if (point) {
              return [
                '',
                `Heater: ${point.relay_state ? '🔥 ON' : '⚪ OFF'}`,
                `Output: ${point.pid_output.toFixed(1)}%`,
              ]
            }
            return []
          },
        },
      },
    },
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

      {/* Temperature Chart */}
      {!loading && readings.length > 0 && (
        <div className="card">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-lg font-semibold text-gray-900">
              Temperature History
            </h3>
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Units:</label>
              <select
                value={units}
                onChange={(e) => setUnits(e.target.value as 'F' | 'C')}
                className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary-500"
              >
                <option value="F">°F</option>
                <option value="C">°C</option>
              </select>
            </div>
          </div>
          
          <div className="h-96">
            <Line ref={chartRef} data={chartConfig} options={chartOptions} plugins={[heaterBackgroundPlugin]} />
          </div>
          
          <div className="mt-4 text-sm text-gray-600">
            <p className="flex items-center gap-2">
              <span className="inline-block w-8 h-3 bg-green-500 bg-opacity-15 border-l-2 border-green-500"></span>
              Green background indicates heater ON periods
            </p>
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
