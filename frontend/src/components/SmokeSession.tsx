import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { Smoke } from '../types'

interface SmokeSessionProps {
  onSessionChange?: () => void
}

export function SmokeSession({ onSessionChange }: SmokeSessionProps) {
  const [smokes, setSmokes] = useState<Smoke[]>([])
  const [activeSmoke, setActiveSmoke] = useState<Smoke | null>(null)
  const [showCreateForm, setShowCreateForm] = useState(false)
  const [newSmokeName, setNewSmokeName] = useState('')
  const [newSmokeDescription, setNewSmokeDescription] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')

  const loadSmokes = async () => {
    try {
      const data = await apiClient.getSmokes({ limit: 20 })
      setSmokes(data.smokes)
      const active = data.smokes.find(s => s.is_active)
      setActiveSmoke(active || null)
    } catch (error) {
      console.error('Failed to load smokes:', error)
    }
  }

  useEffect(() => {
    loadSmokes()
  }, [])

  const handleCreateSmoke = async () => {
    if (!newSmokeName.trim()) {
      setMessage('Please enter a session name')
      return
    }

    try {
      setLoading(true)
      setMessage('')
      
      await apiClient.createSmoke({
        name: newSmokeName.trim(),
        description: newSmokeDescription.trim() || undefined
      })
      
      setNewSmokeName('')
      setNewSmokeDescription('')
      setShowCreateForm(false)
      setMessage('Session created successfully')
      
      await loadSmokes()
      if (onSessionChange) onSessionChange()
      
      setTimeout(() => setMessage(''), 3000)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  const handleEndSmoke = async () => {
    if (!activeSmoke || !confirm('End this smoking session?')) return

    try {
      setLoading(true)
      await apiClient.endSmoke(activeSmoke.id)
      setMessage('Session ended')
      await loadSmokes()
      if (onSessionChange) onSessionChange()
      setTimeout(() => setMessage(''), 3000)
    } catch (error) {
      setMessage(`Error: ${error instanceof Error ? error.message : 'Unknown error'}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="card">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Smoking Session</h3>
      
      {/* Active Session Display */}
      {activeSmoke ? (
        <div className="mb-4 p-4 bg-primary-50 rounded-lg border-2 border-primary-200">
          <div className="flex items-center justify-between mb-2">
            <div>
              <div className="text-sm font-medium text-primary-900">🔥 Active Session</div>
              <div className="text-xl font-bold text-primary-900">{activeSmoke.name}</div>
              {activeSmoke.description && (
                <div className="text-sm text-primary-700 mt-1">{activeSmoke.description}</div>
              )}
            </div>
            <button
              onClick={handleEndSmoke}
              disabled={loading}
              className="btn btn-danger btn-sm disabled:opacity-50"
            >
              End Session
            </button>
          </div>
          <div className="text-xs text-primary-700">
            Started: {new Date(activeSmoke.started_at).toLocaleString()}
          </div>
        </div>
      ) : (
        <div className="mb-4 p-4 bg-gray-50 rounded-lg border-2 border-gray-200">
          <div className="text-sm text-gray-600 mb-2">No active smoking session</div>
          <div className="text-xs text-gray-500">
            Create a session to start tracking this smoke
          </div>
        </div>
      )}

      {/* Create New Session */}
      {!showCreateForm ? (
        <button
          onClick={() => setShowCreateForm(true)}
          className="btn btn-primary w-full"
          disabled={loading || !!activeSmoke}
        >
          {activeSmoke ? 'End Current Session First' : '+ New Smoking Session'}
        </button>
      ) : (
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Session Name *
            </label>
            <input
              type="text"
              value={newSmokeName}
              onChange={(e) => setNewSmokeName(e.target.value)}
              placeholder="e.g., Saturday Ribs, Brisket Day"
              className="input"
              disabled={loading}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description (optional)
            </label>
            <input
              type="text"
              value={newSmokeDescription}
              onChange={(e) => setNewSmokeDescription(e.target.value)}
              placeholder="e.g., Baby back ribs, 225°F for 6 hours"
              className="input"
              disabled={loading}
            />
          </div>
          
          <div className="flex space-x-2">
            <button
              onClick={handleCreateSmoke}
              disabled={loading}
              className="btn btn-primary flex-1 disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Session'}
            </button>
            <button
              onClick={() => {
                setShowCreateForm(false)
                setNewSmokeName('')
                setNewSmokeDescription('')
              }}
              disabled={loading}
              className="btn btn-outline"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Message */}
      {message && (
        <div className={`mt-4 p-3 rounded-lg text-sm ${
          message.startsWith('Error') 
            ? 'bg-danger-100 text-danger-700' 
            : 'bg-success-100 text-success-700'
        }`}>
          {message}
        </div>
      )}

      {/* Recent Sessions */}
      {smokes.length > 0 && (
        <div className="mt-4 pt-4 border-t border-gray-200">
          <div className="text-sm font-medium text-gray-700 mb-2">Recent Sessions</div>
          <div className="space-y-2 max-h-40 overflow-y-auto">
            {smokes.slice(0, 5).map(smoke => (
              <div
                key={smoke.id}
                className={`text-sm p-2 rounded ${
                  smoke.is_active 
                    ? 'bg-primary-50 text-primary-900' 
                    : 'bg-gray-50 text-gray-700'
                }`}
              >
                <div className="font-medium">{smoke.name}</div>
                <div className="text-xs opacity-75">
                  {new Date(smoke.started_at).toLocaleDateString()}
                  {smoke.ended_at && ` - ${new Date(smoke.ended_at).toLocaleDateString()}`}
                  {smoke.avg_temp_f && ` • Avg: ${smoke.avg_temp_f.toFixed(0)}°F`}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

