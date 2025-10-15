import { useState, useEffect } from 'react'
import { apiClient } from '../api/client'
import { Smoke, CookingRecipe, Thermocouple } from '../types'

interface SmokeSessionProps {
  onSessionChange?: () => void
}

type WizardStep = 'list' | 'select-recipe' | 'customize' | 'review'

export function SmokeSession({ onSessionChange }: SmokeSessionProps) {
  const [smokes, setSmokes] = useState<Smoke[]>([])
  const [activeSmoke, setActiveSmoke] = useState<Smoke | null>(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  
  // Wizard state
  const [wizardStep, setWizardStep] = useState<WizardStep>('list')
  const [recipes, setRecipes] = useState<CookingRecipe[]>([])
  const [thermocouples, setThermocouples] = useState<Thermocouple[]>([])
  const [selectedRecipe, setSelectedRecipe] = useState<CookingRecipe | null>(null)
  
  // Session parameters
  const [newSmokeName, setNewSmokeName] = useState('')
  const [newSmokeDescription, setNewSmokeDescription] = useState('')
  const [preheatTemp, setPreheatTemp] = useState(270)
  const [cookTemp, setCookTemp] = useState(225)
  const [finishTemp, setFinishTemp] = useState(160)
  const [meatTargetTemp, setMeatTargetTemp] = useState<number | undefined>(undefined)
  const [meatProbeId, setMeatProbeId] = useState<number | undefined>(undefined)
  const [enableStallDetection, setEnableStallDetection] = useState(true)

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

  const loadRecipes = async () => {
    try {
      const data = await apiClient.getRecipes()
      setRecipes(data.recipes)
    } catch (error) {
      console.error('Failed to load recipes:', error)
    }
  }

  const loadThermocouples = async () => {
    try {
      const data = await apiClient.getThermocouples()
      setThermocouples(data.thermocouples.filter(tc => tc.enabled))
    } catch (error) {
      console.error('Failed to load thermocouples:', error)
    }
  }

  useEffect(() => {
    loadSmokes()
  }, [])

  const startWizard = async () => {
    await loadRecipes()
    await loadThermocouples()
    setWizardStep('select-recipe')
  }

  const handleRecipeSelected = (recipe: CookingRecipe) => {
    setSelectedRecipe(recipe)
    setWizardStep('customize')
  }

  const handleCreateSmoke = async () => {
    if (!newSmokeName.trim() || !selectedRecipe) {
      setMessage('Please complete all required fields')
      return
    }

    try {
      setLoading(true)
      setMessage('')
      
      await apiClient.createSmoke({
        name: newSmokeName.trim(),
        description: newSmokeDescription.trim() || undefined,
        recipe_id: selectedRecipe.id,
        preheat_temp_f: preheatTemp,
        cook_temp_f: cookTemp,
        finish_temp_f: finishTemp,
        meat_target_temp_f: meatTargetTemp,
        meat_probe_tc_id: meatProbeId,
        enable_stall_detection: enableStallDetection
      })
      
      // Reset wizard
      setNewSmokeName('')
      setNewSmokeDescription('')
      setSelectedRecipe(null)
      setWizardStep('list')
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

  const cancelWizard = () => {
    setWizardStep('list')
    setSelectedRecipe(null)
    setNewSmokeName('')
    setNewSmokeDescription('')
    setPreheatTemp(270)
    setCookTemp(225)
    setFinishTemp(160)
    setMeatTargetTemp(undefined)
    setMeatProbeId(undefined)
    setEnableStallDetection(true)
  }

  // Step: List (default view)
  if (wizardStep === 'list') {
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

        {/* Create New Session Button */}
        <button
          onClick={startWizard}
          className="btn btn-primary w-full"
          disabled={loading || !!activeSmoke}
        >
          {activeSmoke ? 'End Current Session First' : '+ New Smoking Session'}
        </button>

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

  // Step 1: Select Recipe
  if (wizardStep === 'select-recipe') {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Select Cooking Recipe</h3>
          <button onClick={cancelWizard} className="text-gray-500 hover:text-gray-700">
            ✕
          </button>
        </div>

        <div className="space-y-3">
          {recipes.map(recipe => (
            <button
              key={recipe.id}
              onClick={() => handleRecipeSelected(recipe)}
              className="w-full text-left p-4 border-2 border-gray-300 rounded-lg hover:border-primary-500 hover:bg-primary-50 transition-colors"
            >
              <div className="font-semibold text-gray-900">{recipe.name}</div>
              {recipe.description && (
                <div className="text-sm text-gray-600 mt-1">{recipe.description}</div>
              )}
              <div className="text-xs text-gray-500 mt-2">
                {recipe.phases.length} phases • {recipe.is_system ? 'System Preset' : 'Custom Recipe'}
              </div>
            </button>
          ))}
        </div>
      </div>
    )
  }

  // Step 2: Customize Parameters
  if (wizardStep === 'customize') {
    return (
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Customize Session</h3>
            <div className="text-sm text-gray-600">{selectedRecipe?.name}</div>
          </div>
          <button onClick={cancelWizard} className="text-gray-500 hover:text-gray-700">
            ✕
          </button>
        </div>

        <div className="space-y-4">
          {/* Session Info */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Session Name *
            </label>
            <input
              type="text"
              value={newSmokeName}
              onChange={(e) => setNewSmokeName(e.target.value)}
              placeholder="e.g., Saturday Brisket"
              className="input"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <input
              type="text"
              value={newSmokeDescription}
              onChange={(e) => setNewSmokeDescription(e.target.value)}
              placeholder="Optional notes"
              className="input"
            />
          </div>

          {/* Temperature Settings */}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Preheat °F
              </label>
              <input
                type="number"
                value={preheatTemp}
                onChange={(e) => setPreheatTemp(Number(e.target.value))}
                className="input"
                min={200}
                max={350}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Cook °F
              </label>
              <input
                type="number"
                value={cookTemp}
                onChange={(e) => setCookTemp(Number(e.target.value))}
                className="input"
                min={180}
                max={300}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Finish °F
              </label>
              <input
                type="number"
                value={finishTemp}
                onChange={(e) => setFinishTemp(Number(e.target.value))}
                className="input"
                min={140}
                max={200}
              />
            </div>
          </div>

          {/* Optional: Meat Probe */}
          <div className="border-t pt-4">
            <div className="text-sm font-medium text-gray-700 mb-2">Meat Probe (Optional)</div>
            
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Target Temp °F
                </label>
                <input
                  type="number"
                  value={meatTargetTemp || ''}
                  onChange={(e) => setMeatTargetTemp(e.target.value ? Number(e.target.value) : undefined)}
                  placeholder="e.g., 203"
                  className="input"
                  min={100}
                  max={250}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  Probe
                </label>
                <select
                  value={meatProbeId || ''}
                  onChange={(e) => setMeatProbeId(e.target.value ? Number(e.target.value) : undefined)}
                  className="input"
                >
                  <option value="">None</option>
                  {thermocouples.map(tc => (
                    <option key={tc.id} value={tc.id}>
                      {tc.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <label className="flex items-center mt-3">
              <input
                type="checkbox"
                checked={enableStallDetection}
                onChange={(e) => setEnableStallDetection(e.target.checked)}
                className="mr-2"
              />
              <span className="text-sm text-gray-700">Enable stall detection</span>
            </label>
          </div>

          {/* Navigation Buttons */}
          <div className="flex space-x-3 pt-4">
            <button
              onClick={() => setWizardStep('select-recipe')}
              className="btn btn-outline"
            >
              Back
            </button>
            <button
              onClick={handleCreateSmoke}
              disabled={loading || !newSmokeName.trim()}
              className="flex-1 btn btn-primary disabled:opacity-50"
            >
              {loading ? 'Creating...' : 'Create Session'}
            </button>
          </div>
        </div>

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
      </div>
    )
  }

  return null
}

