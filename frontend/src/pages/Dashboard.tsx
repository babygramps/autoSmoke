import { useState, useEffect } from 'react'
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core'
import {
  arrayMove,
  SortableContext,
  rectSortingStrategy,
  useSortable,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { Header } from '../components/Header'
import { Charts } from '../components/Charts'
import { Controls } from '../components/Controls'
import { Alarms } from '../components/Alarms'
import { SmokeSession } from '../components/SmokeSession'
import { PhaseProgress } from '../components/PhaseProgress'
import { SessionTimeDisplay } from '../components/SessionTimeDisplay'
import { PhaseTransitionModal } from '../components/PhaseTransitionModal'
import { EditPhaseDialog } from '../components/EditPhaseDialog'
import { apiClient, useWebSocket } from '../api/client'
import { ControllerStatus, Thermocouple, WebSocketMessage } from '../types'

type TileSize = 'small' | 'medium' | 'large' | 'full'

interface DashboardTile {
  id: string
  title: string
  component: React.ReactNode
  size: TileSize
  visible: boolean
  icon: string
  description: string
}

interface SortableItemProps {
  id: string
  children: React.ReactNode
  size: TileSize
  onResize: (id: string, newSize: TileSize) => void
  title: string
  locked: boolean
}

const SIZE_CONFIG = {
  small: { cols: 'col-span-1', label: 'Small', icon: '□' },
  medium: { cols: 'col-span-1 md:col-span-2', label: 'Medium', icon: '▭' },
  large: { cols: 'col-span-1 md:col-span-2 lg:col-span-3', label: 'Large', icon: '▬' },
  full: { cols: 'col-span-1 md:col-span-2 lg:col-span-4', label: 'Full Width', icon: '█' },
}

function SortableItem({ id, children, size, onResize, title, locked }: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled: locked })
  const [showSizeMenu, setShowSizeMenu] = useState(false)

  const style = {
    transform: CSS.Transform.toString(transform),
    transition: transition || 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
    opacity: isDragging ? 0.4 : 1,
    zIndex: isDragging ? 50 : 'auto',
  }

  const sizes: TileSize[] = ['small', 'medium', 'large', 'full']

  return (
    <div
      ref={setNodeRef}
      style={style}
      className={`${SIZE_CONFIG[size].cols} relative group`}
    >
      {/* Control Panel - Top Right - Only show when not locked */}
      {!locked && (
        <div className="absolute top-3 right-3 z-20 flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-all duration-300">
        {/* Size Selector */}
        <div className="relative">
          <button
            onClick={() => setShowSizeMenu(!showSizeMenu)}
            className="flex items-center gap-2 px-3 py-2 bg-white rounded-lg shadow-lg border border-gray-200 hover:border-primary-400 hover:shadow-xl transition-all duration-200 backdrop-blur-sm bg-opacity-95"
            title="Resize tile"
          >
            <svg className="w-4 h-4 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
            </svg>
            <span className="text-xs font-semibold text-gray-700">{SIZE_CONFIG[size].label}</span>
            <svg className="w-3 h-3 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {/* Size Menu Dropdown */}
          {showSizeMenu && (
            <>
              {/* Backdrop */}
              <div 
                className="fixed inset-0 z-10" 
                onClick={() => setShowSizeMenu(false)}
              />
              
              {/* Menu */}
              <div className="absolute top-full right-0 mt-2 w-48 bg-white rounded-xl shadow-2xl border border-gray-200 overflow-hidden z-30 animate-in fade-in slide-in-from-top-2 duration-200">
                {sizes.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      onResize(id, s)
                      setShowSizeMenu(false)
                    }}
                    className={`w-full px-4 py-3 text-left flex items-center gap-3 transition-all duration-150 ${
                      s === size
                        ? 'bg-primary-50 text-primary-700 font-semibold'
                        : 'hover:bg-gray-50 text-gray-700'
                    }`}
                  >
                    <span className="text-lg">{SIZE_CONFIG[s].icon}</span>
                    <div className="flex-1">
                      <div className="text-sm font-medium">{SIZE_CONFIG[s].label}</div>
                    </div>
                    {s === size && (
                      <svg className="w-4 h-4 text-primary-600" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    )}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        {/* Drag Handle */}
        <div
          {...attributes}
          {...listeners}
          className="p-2 bg-white rounded-lg shadow-lg border border-gray-200 hover:border-primary-400 hover:shadow-xl cursor-move transition-all duration-200 backdrop-blur-sm bg-opacity-95"
          title={`Drag to move ${title}`}
        >
          <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 8h16M4 16h16" />
          </svg>
        </div>
      </div>
      )}

      {/* Content */}
      <div className="h-full">
        {children}
      </div>
    </div>
  )
}

const DEFAULT_LAYOUT = [
  'connection',
  'controls',
  'session',
  'session-time',
  'phases',
  'chart',
  'thermocouples',
  'alarms',
]

const DEFAULT_SIZES: Record<string, TileSize> = {
  connection: 'full',
  controls: 'medium',
  session: 'medium',
  'session-time': 'medium',
  phases: 'medium',
  chart: 'large',
  thermocouples: 'full',
  alarms: 'full',
}

const DEFAULT_VISIBILITY: Record<string, boolean> = {
  connection: true,
  controls: true,
  session: true,
  'session-time': true,
  phases: true,
  chart: true,
  thermocouples: true,
  alarms: true,
}

export function Dashboard() {
  const [status, setStatus] = useState<ControllerStatus | null>(null)
  const [units, setUnits] = useState<'F' | 'C'>('F')
  const [connected, setConnected] = useState(false)
  const [thermocouples, setThermocouples] = useState<Thermocouple[]>([])
  const [layout, setLayout] = useState<string[]>(() => {
    const saved = localStorage.getItem('dashboardLayout')
    return saved ? JSON.parse(saved) : DEFAULT_LAYOUT
  })
  const [tileSizes, setTileSizes] = useState<Record<string, TileSize>>(() => {
    const saved = localStorage.getItem('dashboardTileSizes')
    return saved ? JSON.parse(saved) : DEFAULT_SIZES
  })
  const [tileVisibility, setTileVisibility] = useState<Record<string, boolean>>(() => {
    const saved = localStorage.getItem('dashboardTileVisibility')
    return saved ? JSON.parse(saved) : DEFAULT_VISIBILITY
  })
  const [locked, setLocked] = useState<boolean>(() => {
    const saved = localStorage.getItem('dashboardLocked')
    return saved ? JSON.parse(saved) : false
  })
  const [sidebarOpen, setSidebarOpen] = useState(false)

  // Phase management state
  const [showPhaseTransitionModal, setShowPhaseTransitionModal] = useState(false)
  const [phaseTransitionData, setPhaseTransitionData] = useState<any>(null)
  const [showEditPhaseDialog, setShowEditPhaseDialog] = useState(false)
  const [editPhaseData, setEditPhaseData] = useState<any>(null)
  const [activeSmoke, setActiveSmoke] = useState<any>(null)
  const [allPhases, setAllPhases] = useState<any[]>([])

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    }),
    useSensor(KeyboardSensor)
  )

  // WebSocket connection
  const { connect } = useWebSocket((data: WebSocketMessage) => {
    if (data.type === 'telemetry') {
      console.log('🔌 WebSocket telemetry received:', {
        adaptive_pid_enabled: data.data.adaptive_pid?.enabled,
        control_mode: data.data.control_mode,
        running: data.data.running,
        timestamp: new Date().toISOString()
      })
      setStatus(data.data)
      setConnected(true)
    } else if (data.type === 'phase_transition_ready') {
      // Phase transition ready - show modal for user approval
      setPhaseTransitionData(data.data)
      setShowPhaseTransitionModal(true)
    } else if (data.type === 'phase_started') {
      // Phase started - refresh status
      apiClient.getStatus().then(setStatus).catch(console.error)
    }
  })

  useEffect(() => {
    const ws = connect()
    
    const fetchInitialData = async () => {
      try {
        const [statusData, settingsData, thermocouplesData] = await Promise.all([
          apiClient.getStatus(),
          apiClient.getSettings(),
          apiClient.getThermocouples()
        ])
        setStatus(statusData)
        setUnits(settingsData.units)
        setThermocouples(thermocouplesData.thermocouples.sort((a, b) => a.order - b.order))
        
        // Load active smoke and phases if available
        if (statusData.active_smoke_id) {
          const smokesData = await apiClient.getSmokes({ limit: 1 })
          const active = smokesData.smokes.find((s: any) => s.is_active)
          setActiveSmoke(active || null)
          
          if (active) {
            const phasesData = await apiClient.getSmokePhases(active.id)
            setAllPhases(phasesData?.phases || [])
          }
        }
      } catch (error) {
        console.error('Failed to fetch initial data:', error)
      }
    }
    
    fetchInitialData()
    return () => ws?.close()
  }, [])

  const handleStatusUpdate = (newStatus: ControllerStatus) => {
    setStatus(newStatus)
  }

  const handleAlertUpdate = () => {
    apiClient.getStatus().then(setStatus).catch(console.error)
  }

  const handleSessionChange = async () => {
    try {
      const newStatus = await apiClient.getStatus()
      setStatus(newStatus)
      
      // Load active smoke and phases if available
      if (newStatus.active_smoke_id) {
        const smokesData = await apiClient.getSmokes({ limit: 1 })
        const active = smokesData.smokes.find((s: any) => s.is_active)
        setActiveSmoke(active || null)
        
        // Load phases for active smoke
        if (active) {
          const phasesData = await apiClient.getSmokePhases(active.id)
          setAllPhases(phasesData?.phases || [])
        }
      } else {
        setActiveSmoke(null)
        setAllPhases([])
      }
    } catch (error) {
      console.error('Error updating session:', error)
    }
  }

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event

    if (over && active.id !== over.id) {
      setLayout((items) => {
        const oldIndex = items.indexOf(active.id as string)
        const newIndex = items.indexOf(over.id as string)
        const newLayout = arrayMove(items, oldIndex, newIndex)
        localStorage.setItem('dashboardLayout', JSON.stringify(newLayout))
        return newLayout
      })
    }
  }

  const handleResize = (id: string, newSize: TileSize) => {
    setTileSizes((prev) => {
      const updated = { ...prev, [id]: newSize }
      localStorage.setItem('dashboardTileSizes', JSON.stringify(updated))
      return updated
    })
  }

  const toggleTileVisibility = (id: string) => {
    setTileVisibility((prev) => {
      const updated = { ...prev, [id]: !prev[id] }
      localStorage.setItem('dashboardTileVisibility', JSON.stringify(updated))
      return updated
    })
  }

  const toggleLock = () => {
    setLocked((prev) => {
      const newLocked = !prev
      localStorage.setItem('dashboardLocked', JSON.stringify(newLocked))
      return newLocked
    })
  }

  const resetLayout = () => {
    setLayout(DEFAULT_LAYOUT)
    setTileSizes(DEFAULT_SIZES)
    setTileVisibility(DEFAULT_VISIBILITY)
    localStorage.setItem('dashboardLayout', JSON.stringify(DEFAULT_LAYOUT))
    localStorage.setItem('dashboardTileSizes', JSON.stringify(DEFAULT_SIZES))
    localStorage.setItem('dashboardTileVisibility', JSON.stringify(DEFAULT_VISIBILITY))
  }

  const tiles: Record<string, DashboardTile> = {
    connection: {
      id: 'connection',
      title: 'Connection Status',
      icon: '🔗',
      description: 'Monitor WebSocket connection status',
      size: tileSizes.connection || 'full',
      visible: tileVisibility.connection ?? true,
      component: (
        <div className="card h-full">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div className={`w-3 h-3 rounded-full ${connected ? 'bg-success-500' : 'bg-danger-500'} animate-pulse`}></div>
              <span className="text-sm font-medium text-gray-700">
                {connected ? 'Connected' : 'Disconnected'}
              </span>
            </div>
            <div className="text-sm text-gray-500">
              Last updated: {status ? new Date().toLocaleTimeString() : 'Never'}
            </div>
          </div>
        </div>
      ),
    },
    controls: {
      id: 'controls',
      title: 'Controller Controls',
      icon: '🎮',
      description: 'Start/stop controller and adjust settings',
      size: tileSizes.controls || 'medium',
      visible: tileVisibility.controls ?? true,
      component: <Controls status={status} onStatusUpdate={handleStatusUpdate} />,
    },
    session: {
      id: 'session',
      title: 'Smoke Session',
      icon: '🔥',
      description: 'Manage smoking sessions',
      size: tileSizes.session || 'medium',
      visible: tileVisibility.session ?? true,
      component: <SmokeSession onSessionChange={handleSessionChange} />,
    },
    'session-time': {
      id: 'session-time',
      title: 'Session Time',
      icon: '⏱️',
      description: 'Track elapsed time and estimated finish',
      size: tileSizes['session-time'] || 'medium',
      visible: tileVisibility['session-time'] ?? true,
      component: status?.active_smoke_id && activeSmoke ? (
        <SessionTimeDisplay
          smoke={activeSmoke}
          currentPhase={status.current_phase as any}
          allPhases={allPhases}
        />
      ) : (
        <div className="card h-full flex items-center justify-center">
          <div className="text-center text-gray-500 py-8">
            <div className="text-4xl mb-2">⏱️</div>
            <div className="text-sm">No active session</div>
            <div className="text-xs mt-1">Create a session to track time</div>
          </div>
        </div>
      ),
    },
    phases: {
      id: 'phases',
      title: 'Cooking Phases',
      icon: '📋',
      description: 'Track cooking phase progress',
      size: tileSizes.phases || 'medium',
      visible: tileVisibility.phases ?? true,
      component: status?.active_smoke_id && status?.current_phase ? (
        <PhaseProgress
          smokeId={status.active_smoke_id}
          currentPhase={status.current_phase}
          onEditPhase={() => {
            if (status?.current_phase) {
              setEditPhaseData({
                smokeId: status.active_smoke_id,
                phaseId: status.current_phase.id,
                phaseName: status.current_phase.phase_name,
                currentTargetTemp: status.current_phase.target_temp_f,
                currentConditions: status.current_phase.completion_conditions
              })
              setShowEditPhaseDialog(true)
            }
          }}
        />
      ) : (
        <div className="card h-full flex items-center justify-center">
          <div className="text-center text-gray-500 py-8">
            <div className="text-4xl mb-2">📋</div>
            <div className="text-sm">No active cooking phases</div>
            <div className="text-xs mt-1">Create a session to see phase progress</div>
          </div>
        </div>
      ),
    },
    chart: {
      id: 'chart',
      title: 'Temperature Chart',
      icon: '📈',
      description: 'Real-time temperature visualization',
      size: tileSizes.chart || 'large',
      visible: tileVisibility.chart ?? true,
      component: <Charts status={status} units={units} smokeId={status?.active_smoke_id || undefined} />,
    },
    thermocouples: {
      id: 'thermocouples',
      title: 'Temperature Readings',
      icon: '🌡️',
      description: 'All thermocouple temperatures',
      size: tileSizes.thermocouples || 'full',
      visible: tileVisibility.thermocouples ?? true,
      component: status && thermocouples.length > 0 ? (
        <div className="card h-full">
          <h3 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
            <span>🌡️</span>
            <span>Temperature Readings</span>
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {thermocouples
              .filter(tc => tc.enabled)
              .map(tc => {
                const reading = status.thermocouple_readings?.[tc.id]
                const isControl = tc.id === status.control_tc_id
                const temp = reading ? (units === 'F' ? reading.temp_f : reading.temp_c) : null
                
                return (
                  <div 
                    key={tc.id}
                    className={`p-4 rounded-xl border-2 transition-all duration-200 ${
                      isControl 
                        ? 'border-primary-500 bg-gradient-to-br from-primary-50 to-primary-100 shadow-lg' 
                        : 'border-gray-200 bg-gray-50 hover:border-gray-300'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center space-x-2">
                        <div 
                          className="w-3 h-3 rounded-full ring-2 ring-white shadow-md" 
                          style={{ backgroundColor: tc.color }}
                        />
                        <h4 className="font-semibold text-gray-900">{tc.name}</h4>
                      </div>
                      {isControl && (
                        <span className="text-xs px-2 py-1 rounded-full bg-primary-600 text-white font-bold shadow-sm">
                          CONTROL
                        </span>
                      )}
                    </div>
                    
                    {reading && !reading.fault ? (
                      <div className="text-3xl font-bold text-gray-900">
                        {temp?.toFixed(1)}°{units}
                      </div>
                    ) : reading?.fault ? (
                      <div className="text-lg font-semibold text-danger-600 flex items-center gap-2">
                        <span>⚠️</span>
                        <span>FAULT</span>
                      </div>
                    ) : (
                      <div className="text-lg text-gray-400">
                        No reading
                      </div>
                    )}
                  </div>
                )
              })}
          </div>
          
          <div className="mt-4 flex items-center justify-center space-x-3 flex-wrap gap-2">
            <div className={`px-3 py-1.5 rounded-full text-sm font-medium shadow-sm ${
              status.running 
                ? 'bg-success-500 text-white' 
                : 'bg-gray-200 text-gray-700'
            }`}>
              {status.running ? '▶ Running' : '⏸ Stopped'}
            </div>
            <div className={`px-3 py-1.5 rounded-full text-sm font-medium shadow-sm ${
              status.relay_state 
                ? 'bg-warning-500 text-white animate-pulse' 
                : 'bg-gray-200 text-gray-700'
            }`}>
              {status.relay_state ? '⚡ Relay ON' : '○ Relay OFF'}
            </div>
            {status.boost_active && (
              <div className="px-3 py-1.5 rounded-full text-sm font-medium bg-orange-500 text-white shadow-sm animate-pulse">
                🚀 Boost Active
              </div>
            )}
            <div className="px-3 py-1.5 rounded-full text-sm font-medium bg-primary-100 text-primary-800 shadow-sm">
              🎯 Target: {units === 'F' ? status.setpoint_f.toFixed(1) : status.setpoint_c.toFixed(1)}°{units}
            </div>
          </div>
        </div>
      ) : null,
    },
    alarms: {
      id: 'alarms',
      title: 'Alerts & Alarms',
      icon: '🚨',
      description: 'System alerts and notifications',
      size: tileSizes.alarms || 'full',
      visible: tileVisibility.alarms ?? true,
      component: (
        <Alarms 
          alertSummary={status?.alert_summary || null} 
          alerts={status?.alerts || []} 
          onAlertUpdate={handleAlertUpdate} 
        />
      ),
    },
  }

  const visibleTiles = layout.filter(id => tiles[id]?.visible)
  const visibleCount = Object.values(tileVisibility).filter(Boolean).length

  return (
    <div className="relative">
        {/* Unified sticky header (app header + dashboard toolbar) */}
        <div className="sticky top-0 z-40 bg-white">
          <Header
            extraRight={
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleLock}
                  className={`btn btn-sm flex items-center gap-2 transition-all duration-200 ${
                    locked 
                      ? 'btn-primary shadow-lg' 
                      : 'btn-outline hover:scale-105'
                  }`}
                  title={locked ? "Unlock tiles (enable moving/resizing)" : "Lock tiles (disable moving/resizing)"}
                >
                  {locked ? (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                    </svg>
                  ) : (
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 11V7a4 4 0 118 0m-4 8v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2z" />
                    </svg>
                  )}
                  <span className="hidden sm:inline">{locked ? 'Locked' : 'Unlocked'}</span>
                </button>
                <button
                  onClick={resetLayout}
                  className="btn btn-outline btn-sm flex items-center gap-2 hover:scale-105 transition-transform"
                  title="Reset to default layout"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                  <span className="hidden sm:inline">Reset</span>
                </button>
                <button
                  onClick={() => setSidebarOpen(!sidebarOpen)}
                  className={`btn btn-sm flex items-center gap-2 transition-all duration-200 ${
                    sidebarOpen 
                      ? 'btn-primary shadow-lg scale-105' 
                      : 'btn-outline hover:scale-105'
                  }`}
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                  <span className="hidden sm:inline">Customize</span>
                </button>
              </div>
            }
          />
        </div>

      {/* Sidebar */}
      <div className={`fixed inset-y-0 right-0 w-80 bg-white shadow-2xl border-l border-gray-200 z-40 transform transition-transform duration-300 ease-in-out ${
        sidebarOpen ? 'translate-x-0' : 'translate-x-full'
      }`}>
        <div className="h-full flex flex-col">
          {/* Sidebar Header */}
          <div className="p-6 border-b border-gray-200 bg-gradient-to-r from-primary-50 to-primary-100">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-bold text-gray-900">Customize Dashboard</h2>
              <button
                onClick={() => setSidebarOpen(false)}
                className="p-2 hover:bg-white rounded-lg transition-colors"
              >
                <svg className="w-5 h-5 text-gray-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <p className="text-sm text-gray-600">
              Show or hide dashboard tiles
            </p>
          </div>

          {/* Tile List */}
          <div className="flex-1 overflow-y-auto p-4 space-y-2">
            {DEFAULT_LAYOUT.map((tileId) => {
              const tile = tiles[tileId]
              if (!tile) return null
              
              return (
                <div
                  key={tile.id}
                  className={`group p-4 rounded-xl border-2 transition-all duration-200 cursor-pointer ${
                    tile.visible
                      ? 'border-primary-300 bg-primary-50 shadow-md hover:shadow-lg'
                      : 'border-gray-200 bg-gray-50 hover:border-gray-300 opacity-60'
                  }`}
                  onClick={() => toggleTileVisibility(tile.id)}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 text-2xl">{tile.icon}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between mb-1">
                        <h3 className="font-semibold text-gray-900 text-sm">{tile.title}</h3>
                        <div className={`flex-shrink-0 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-all ${
                          tile.visible
                            ? 'border-primary-600 bg-primary-600'
                            : 'border-gray-300 bg-white'
                        }`}>
                          {tile.visible && (
                            <svg className="w-3 h-3 text-white" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                            </svg>
                          )}
                        </div>
                      </div>
                      <p className="text-xs text-gray-600">{tile.description}</p>
                      {tile.visible && (
                        <div className="mt-2 flex items-center gap-1">
                          <span className="text-xs px-2 py-0.5 bg-white rounded-full text-gray-600 font-medium border border-gray-200">
                            {SIZE_CONFIG[tile.size].label}
                          </span>
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Sidebar Footer */}
          <div className="p-4 border-t border-gray-200 bg-gray-50">
            <button
              onClick={resetLayout}
              className="w-full btn btn-outline flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Reset to Default
            </button>
          </div>
        </div>
      </div>

      {/* Backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black bg-opacity-30 z-30 transition-opacity backdrop-blur-sm"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main Content */}
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={handleDragEnd}
      >
        <SortableContext
          items={visibleTiles}
          strategy={rectSortingStrategy}
        >
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-1">
            {visibleTiles.map((tileId) => {
              const tile = tiles[tileId]
              if (!tile) return null
              
              return (
                <SortableItem 
                  key={tile.id} 
                  id={tile.id} 
                  size={tile.size}
                  onResize={handleResize}
                  title={tile.title}
                  locked={locked}
                >
                  {tile.component}
                </SortableItem>
              )
            })}
          </div>
        </SortableContext>
      </DndContext>

      {/* Empty State */}
      {visibleCount === 0 && (
        <div className="text-center py-20">
          <div className="text-6xl mb-4">📊</div>
          <h3 className="text-xl font-semibold text-gray-900 mb-2">No tiles visible</h3>
          <p className="text-gray-600 mb-6">Click "Customize" to show some tiles</p>
          <button
            onClick={() => setSidebarOpen(true)}
            className="btn btn-primary"
          >
            Open Customize Panel
          </button>
        </div>
      )}

      {/* Help Hint */}
      {visibleCount > 0 && (
        <div className="mt-8 text-center">
          <div className="inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-primary-50 to-blue-50 rounded-full border border-primary-200">
            <span className="text-sm text-gray-700">
              💡 <strong>Pro tip:</strong> Hover over tiles to resize or drag them around
            </span>
          </div>
        </div>
      )}

      {/* Phase Transition Modal */}
      {phaseTransitionData && (
        <PhaseTransitionModal
          isOpen={showPhaseTransitionModal}
          onClose={() => setShowPhaseTransitionModal(false)}
          smokeId={phaseTransitionData.smoke_id}
          reason={phaseTransitionData.reason}
          currentPhase={phaseTransitionData.current_phase}
          nextPhase={phaseTransitionData.next_phase}
          onApproved={() => {
            apiClient.getStatus().then(setStatus).catch(console.error)
          }}
        />
      )}

      {/* Edit Phase Dialog */}
      {editPhaseData && (
        <EditPhaseDialog
          isOpen={showEditPhaseDialog}
          onClose={() => setShowEditPhaseDialog(false)}
          smokeId={editPhaseData.smokeId}
          phaseId={editPhaseData.phaseId}
          phaseName={editPhaseData.phaseName}
          currentTargetTemp={editPhaseData.currentTargetTemp}
          currentConditions={editPhaseData.currentConditions}
          onUpdated={() => {
            apiClient.getStatus().then(setStatus).catch(console.error)
          }}
        />
      )}
    </div>
  )
}
