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
  const chartRef = useRef<ChartJS<'line', number[], string>>(null)

  // Fetch historical data
  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true)
        const endTime = new Date()
        const startTime = new Date(endTime.getTime() - 2 * 60 * 60 * 1000) // 2 hours ago
        
        const response = await apiClient.getReadings({
          smoke_id: smokeId,
          from_time: startTime.toISOString(),
          to_time: endTime.toISOString(),
          limit: 7200, // 2 hours at 1Hz
        })
        
        const data: ChartDataPoint[] = response.readings.map(reading => ({
          timestamp: reading.ts,
          temp_c: reading.temp_c,
          temp_f: reading.temp_f,
          setpoint_c: reading.setpoint_c,
          setpoint_f: reading.setpoint_f,
          relay_state: reading.relay_state,
          pid_output: reading.pid_output,
        }))
        
        setChartData(data)
      } catch (error) {
        console.error('Failed to fetch chart data:', error)
      } finally {
        setLoading(false)
      }
    }
    
    fetchData()
  }, [smokeId])

  // Update chart with new data point
  useEffect(() => {
    if (status && status.current_temp_f && chartRef.current) {
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
        const updated = [...prev, newDataPoint]
        // Keep only last 2 hours of data
        const cutoff = new Date(Date.now() - 2 * 60 * 60 * 1000)
        return updated.filter(point => new Date(point.timestamp) > cutoff)
      })
    }
  }, [status])

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
            minute: 'HH:mm',
            hour: 'HH:mm',
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
        display: true,
        text: smokeId ? 'Temperature and Control History (Current Session)' : 'Temperature and Control History (Last 2 Hours)',
        color: 'rgb(17, 24, 39)',
        font: {
          size: 16,
          weight: 600,
        },
        padding: {
          top: 10,
          bottom: 20,
        },
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
      <div className="h-96">
        <Line ref={chartRef} data={chartConfig} options={options} plugins={[heaterBackgroundPlugin]} />
      </div>
    </div>
  )
}
