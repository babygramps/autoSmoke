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
import { ChartDataPoint } from '../types'

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
  const [timeRange, setTimeRange] = useState<number | null>(null) // null = all session data, or hours
  const chartRef = useRef<ChartJS<'line', number[], string>>(null)
  const isMountedRef = useRef(true)

  // Fetch historical data
  useEffect(() => {
    let cancelled = false
    
    const fetchData = async () => {
      try {
        setLoading(true)
        
        const endTime = new Date()
        let params: any = {
          to_time: endTime.toISOString(),
          limit: 10000, // Backend max limit
        }
        
        if (smokeId) {
          // Filter by session
          params.smoke_id = smokeId
          
          if (timeRange !== null) {
            // User selected a specific time range
            const startTime = new Date(endTime.getTime() - timeRange * 60 * 60 * 1000)
            params.from_time = startTime.toISOString()
          }
          // If timeRange is null, don't set from_time to get ALL session data
        } else {
          // No session, default to last 2 hours
          const startTime = new Date(endTime.getTime() - 2 * 60 * 60 * 1000)
          params.from_time = startTime.toISOString()
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
          }))
          
          // Sort by timestamp to ensure chronological order
          data.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
          
          // Debug logging
          if (data.length > 0) {
            console.log('Chart data loaded:', {
              count: data.length,
              firstTimestamp: data[0].timestamp,
              lastTimestamp: data[data.length - 1].timestamp,
              smokeId: smokeId,
              timeRange: timeRange,
              params: params
            })
          }
          
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
  }, [smokeId, timeRange])
  
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
    
    // Only update if we have valid temperature data and the controller is running
    if (status && status.current_temp_f !== null && status.current_temp_f !== undefined && status.running) {
      const newDataPoint: ChartDataPoint = {
        timestamp: new Date().toISOString(),
        temp_c: status.current_temp_c,
        temp_f: status.current_temp_f,
        setpoint_c: status.setpoint_c,
        setpoint_f: status.setpoint_f,
        relay_state: status.relay_state,
        pid_output: status.pid_output,
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
        
        // Apply time filtering if specified
        let filtered = updated
        if (timeRange) {
          const cutoff = new Date(Date.now() - timeRange * 60 * 60 * 1000)
          filtered = updated.filter(point => new Date(point.timestamp) > cutoff)
        }
        // If showing all session data (timeRange === null), keep all points
        
        // Ensure data is sorted chronologically
        filtered.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
        
        return filtered
      })
    }
  }, [status, loading])

  // Calculate dynamic temperature scale based on actual data
  const calculateTempRange = () => {
    if (chartData.length === 0) {
      return units === 'F' ? { min: 100, max: 300 } : { min: 40, max: 150 }
    }
    
    const temps = chartData.map(point => units === 'F' ? point.temp_f : point.temp_c)
    const setpoints = chartData.map(point => units === 'F' ? point.setpoint_f : point.setpoint_c)
    const allValues = [...temps, ...setpoints].filter(v => v !== null && v !== undefined)
    
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

  const chartConfig = {
    labels: chartData.map(point => point.timestamp),
    datasets: [
      {
        label: `Temperature (${units})`,
        data: chartData.map(point => units === 'F' ? point.temp_f : point.temp_c),
        borderColor: 'rgb(239, 68, 68)',
        backgroundColor: 'rgba(239, 68, 68, 0.05)',
        borderWidth: 3,
        tension: 0.4,
        pointRadius: 0,
        pointHoverRadius: 6,
        fill: false,
      },
      {
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
      },
      {
        // Hidden dataset to carry relay state for the background plugin
        label: '__relay_state__',
        data: chartData.map(point => point.relay_state ? 1 : 0),
        hidden: true,
        pointRadius: 0,
      },
    ],
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
      {/* Time Range Selector */}
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">
          Temperature and Control History {smokeId ? '(Current Session)' : ''}
        </h3>
        <div className="flex items-center gap-2">
          <label className="text-sm text-gray-600">View:</label>
          <select
            value={timeRange === null ? 'all' : timeRange}
            onChange={(e) => setTimeRange(e.target.value === 'all' ? null : Number(e.target.value))}
            className="text-sm border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            {smokeId && <option value="all">All Session Data</option>}
            <option value="1">Last 1 Hour</option>
            <option value="2">Last 2 Hours</option>
            <option value="4">Last 4 Hours</option>
            <option value="8">Last 8 Hours</option>
            <option value="24">Last 24 Hours</option>
          </select>
        </div>
      </div>
      
      <div className="h-96">
        <Line ref={chartRef} data={chartConfig} options={options} plugins={[heaterBackgroundPlugin]} />
      </div>
    </div>
  )
}
