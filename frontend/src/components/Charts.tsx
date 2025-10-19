import { useEffect, useRef, useState } from 'react'
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
import { apiClient } from '../api/client'
import { ChartDataPoint, Thermocouple } from '../types'

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

interface ChartsProps {
  status: any
  units: 'F' | 'C'
  smokeId?: number
}

export function Charts({ status, units, smokeId }: ChartsProps) {
  const [chartData, setChartData] = useState<ChartDataPoint[]>([])
  const [loading, setLoading] = useState(true)
  const [timeRange, setTimeRange] = useState<number | null>(2) // Default to 2 hours, null = all session data
  const [filterMode, setFilterMode] = useState<'session' | 'all'>('all') // session = filter by active session, all = show all data
  const [thermocouples, setThermocouples] = useState<Thermocouple[]>([])
  const chartRef = useRef<ChartJS<'line', number[], string>>(null)
  const isMountedRef = useRef(true)

  // Fetch thermocouples on mount
  useEffect(() => {
    const fetchThermocouples = async () => {
      try {
        const response = await apiClient.getThermocouples()
        setThermocouples(response.thermocouples.filter(tc => tc.enabled).sort((a, b) => a.order - b.order))
      } catch (error) {
        console.error('Failed to fetch thermocouples:', error)
      }
    }
    fetchThermocouples()
  }, [])

  // Fetch historical data
  useEffect(() => {
    let cancelled = false
    
    const fetchData = async () => {
      try {
        setLoading(true)
        
        const endTime = new Date()
        let params: any = {
          to_time: endTime.toISOString(),
          limit: 5000, // Reduced from 10000 for better performance
          include_thermocouples: true, // Include thermocouple readings
        }
        
        // Apply session filter if in session mode and a session is active
        if (filterMode === 'session' && smokeId) {
          params.smoke_id = smokeId
          
          if (timeRange !== null) {
            // User selected a specific time range
            const startTime = new Date(endTime.getTime() - timeRange * 60 * 60 * 1000)
            params.from_time = startTime.toISOString()
          }
          // If timeRange is null, don't set from_time to get ALL session data
        } else {
          // Show all data with time range filter
          if (timeRange !== null) {
            const startTime = new Date(endTime.getTime() - timeRange * 60 * 60 * 1000)
            params.from_time = startTime.toISOString()
          } else {
            // Shouldn't happen in 'all' mode, but fallback to 2 hours
            const startTime = new Date(endTime.getTime() - 2 * 60 * 60 * 1000)
            params.from_time = startTime.toISOString()
          }
        }
        
        const response = await apiClient.getReadings(params)
        
        // Only update if not cancelled
        if (!cancelled && isMountedRef.current) {
          const data: ChartDataPoint[] = response.readings.map(reading => ({
            timestamp: reading.ts,
            temp_c: reading.temp_c,
            temp_f: reading.temp_f,
            setpoint_c: reading.setpoint_c,
            setpoint_f: reading.setpoint_f,
            relay_state: reading.relay_state,
            pid_output: reading.pid_output,
            thermocouple_readings: reading.thermocouple_readings,
          }))
          
          // Sort by timestamp to ensure chronological order
          data.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
          
          // Debug logging
          console.log('📊 Chart data loaded:', {
            count: data.length,
            firstTimestamp: data.length > 0 ? data[0].timestamp : 'N/A',
            lastTimestamp: data.length > 0 ? data[data.length - 1].timestamp : 'N/A',
            timeRangeHours: timeRange,
            filterMode: filterMode,
            smokeId: smokeId,
            paramsUsed: params
          })
          
          setChartData(data)
          setLoading(false)
        }
      } catch (error) {
        if (!cancelled && isMountedRef.current) {
          console.error('Failed to fetch chart data:', error)
          setChartData([])
          setLoading(false)
        }
      }
    }
    
    fetchData()
    
    // Cleanup function
    return () => {
      cancelled = true
    }
  }, [smokeId, timeRange, filterMode])
  
  // Track mounted state
  useEffect(() => {
    isMountedRef.current = true
    return () => {
      isMountedRef.current = false
    }
  }, [])

  // Update chart with new data point (only for live data, not when loading)
  useEffect(() => {
    // Don't add points while loading or if not mounted
    if (loading || !isMountedRef.current) return
    
    // Only update if we have valid temperature data (controller can be running or stopped now)
    if (status && status.current_temp_f !== null && status.current_temp_f !== undefined) {
      const newDataPoint: ChartDataPoint = {
        timestamp: new Date().toISOString(),
        temp_c: status.current_temp_c,
        temp_f: status.current_temp_f,
        setpoint_c: status.setpoint_c,
        setpoint_f: status.setpoint_f,
        relay_state: status.relay_state,
        pid_output: status.pid_output,
        thermocouple_readings: status.thermocouple_readings,
      }
      
      setChartData(prev => {
        // Avoid duplicates - check last point timestamp (within 1 second)
        const lastPoint = prev[prev.length - 1]
        if (lastPoint) {
          const lastTime = new Date(lastPoint.timestamp).getTime()
          const newTime = new Date(newDataPoint.timestamp).getTime()
          if (Math.abs(newTime - lastTime) < 1000) {
            return prev // Too close in time, skip
          }
        }
        
        const updated = [...prev, newDataPoint]
        
        // Apply time filtering if specified (not null)
        let filtered = updated
        if (timeRange !== null) {
          const cutoff = new Date(Date.now() - timeRange * 60 * 60 * 1000)
          filtered = updated.filter(point => new Date(point.timestamp) > cutoff)
        }
        // If timeRange === null, keep all points (entire session)
        
        // Ensure data is sorted chronologically
        filtered.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        
        return filtered
      })
    }
  }, [status, loading, timeRange])

  // Calculate dynamic temperature scale based on actual data
  const calculateTempRange = () => {
    if (chartData.length === 0) {
      return units === 'F' ? { min: 100, max: 300 } : { min: 40, max: 150 }
    }
    
    const temps = chartData.map(point => units === 'F' ? point.temp_f : point.temp_c)
    const setpoints = chartData.map(point => units === 'F' ? point.setpoint_f : point.setpoint_c)
    
    // Also include all thermocouple readings
    const tcTemps: number[] = []
    chartData.forEach(point => {
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
  
  const tempRange = calculateTempRange()

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
        ctx.fillStyle = 'rgba(34, 197, 94, 0.15)' // Green with 15% opacity (more visible)
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
      const data = chartData.map(point => {
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
      data: chartData.map(point => units === 'F' ? point.setpoint_f : point.setpoint_c),
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
      data: chartData.map(point => point.relay_state ? 1 : 0),
      hidden: true,
      pointRadius: 0,
    })
    
    return datasets
  }

  const chartConfig = {
    labels: chartData.map(point => point.timestamp),
    datasets: buildDatasets(),
  }

  const options = {
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
              return date.toLocaleTimeString()
            }
            return ''
          },
          label: (context: any) => {
            const label = context.dataset.label || ''
            const value = context.parsed.y
            return `${label}: ${value.toFixed(1)}°${units}`
          },
          afterBody: (items: any) => {
            const dataIndex = items[0].dataIndex
            const point = chartData[dataIndex]
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

  if (loading) {
    return (
      <div className="card">
        <div className="flex items-center justify-center h-96">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600 mx-auto mb-4"></div>
            <p className="text-gray-600">Loading chart data...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="card">
      {/* Filter and Time Range Selectors */}
      <div className="mb-4 flex items-center justify-between flex-wrap gap-2">
        <h3 className="text-lg font-semibold text-gray-900">
          Temperature and Control History
        </h3>
        <div className="flex items-center gap-3 flex-wrap">
          {/* Filter Mode Selector - only show if there's an active session */}
          {smokeId && (
            <div className="flex items-center gap-2">
              <label className="text-sm text-gray-600">Filter:</label>
              <select
                value={filterMode}
                onChange={(e) => setFilterMode(e.target.value as 'session' | 'all')}
                className="text-sm border border-gray-300 rounded px-3 py-1 focus:outline-none focus:ring-2 focus:ring-primary-500 font-medium"
              >
                <option value="session">Current Session Only</option>
                <option value="all">All Data</option>
              </select>
            </div>
          )}
          
          {/* Time Range Selector */}
          <div className="flex items-center gap-2">
            <label className="text-sm text-gray-600">View:</label>
            <select
              value={timeRange === null ? 'all' : timeRange}
              onChange={(e) => setTimeRange(e.target.value === 'all' ? null : Number(e.target.value))}
              className="text-sm border border-gray-300 rounded px-3 py-1 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {filterMode === 'session' && smokeId && <option value="all">Entire Session</option>}
              <option value={0.25}>Last 15 minutes</option>
              <option value={0.5}>Last 30 minutes</option>
              <option value={0.75}>Last 45 minutes</option>
              <option value={1}>Last 1 hour</option>
              <option value={2}>Last 2 hours</option>
              <option value={4}>Last 4 hours</option>
              <option value={8}>Last 8 hours</option>
              <option value={24}>Last 24 hours</option>
            </select>
          </div>
        </div>
      </div>
      
      <div className="h-96">
        <Line ref={chartRef} data={chartConfig} options={options} plugins={[heaterBackgroundPlugin]} />
      </div>
    </div>
  )
}
