import React, { useEffect, useState } from 'react'
import useWeatherStore from './stores/weatherStore'
import Header from './components/Header'
import ResortRow from './components/ResortRow'
import { RefreshCw } from 'lucide-react'

function App() {
  const {
    fetchWeather,
    filteredResorts,
    isLoading,
    error,
    lastUpdated,
    startAutoRefresh,
    stopAutoRefresh
  } = useWeatherStore()

  const [viewMode, setViewMode] = useState('snow-summary') // snow-summary, weather, snow-forecast

  useEffect(() => {
    fetchWeather()
    startAutoRefresh()
    return () => stopAutoRefresh()
  }, [fetchWeather, startAutoRefresh, stopAutoRefresh])

  const handleRefresh = () => {
    fetchWeather()
  }

  return (
    <div className="min-h-screen bg-[#1a1f2e]">
      <Header />

      <main className="max-w-6xl mx-auto px-4 py-6">
        {/* View Mode Tabs */}
        <div className="flex items-center gap-2 mb-6">
          <div className="flex bg-slate-800/50 rounded-lg p-1">
            {[
              { id: 'snow-summary', label: 'Snow Summary' },
              { id: 'weather', label: 'Weather' },
              { id: 'snow-forecast', label: 'Snow Forecast' }
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setViewMode(tab.id)}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  viewMode === tab.id
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-4">
            {lastUpdated && (
              <span className="text-xs text-slate-500">
                Updated {new Date(lastUpdated).toLocaleTimeString()}
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={isLoading}
              className={`p-2 rounded-lg transition-all ${
                isLoading
                  ? 'bg-slate-700 text-slate-500'
                  : 'bg-slate-800 text-slate-400 hover:text-white'
              }`}
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Error Banner */}
        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
            {error}
          </div>
        )}

        {/* Loading State */}
        {isLoading && filteredResorts.length === 0 && (
          <div className="space-y-4">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="bg-slate-800/50 rounded-lg p-4 animate-pulse">
                <div className="h-6 bg-slate-700 rounded w-48 mb-3" />
                <div className="h-4 bg-slate-700 rounded w-32 mb-4" />
                <div className="h-20 bg-slate-700/50 rounded" />
              </div>
            ))}
          </div>
        )}

        {/* Resort List */}
        <div className="space-y-3">
          {filteredResorts.map(resort => (
            <ResortRow
              key={resort.id}
              resort={resort}
              viewMode={viewMode}
            />
          ))}
        </div>

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
          <p>Weather data from Open-Meteo • Auto-refreshes every 15 minutes</p>
          <p className="mt-1">Forecast confidence decreases beyond 7 days</p>
        </footer>
      </main>
    </div>
  )
}

export default App
