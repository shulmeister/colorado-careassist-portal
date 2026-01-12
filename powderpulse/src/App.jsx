import React, { useEffect, useState } from 'react'
import { BrowserRouter as Router, Routes, Route, useNavigate } from 'react-router-dom'
import useWeatherStore from './stores/weatherStore'
import Header from './components/Header'
import ResortRow from './components/ResortRow'
import ResortDetail from './pages/ResortDetail'
import { RefreshCw, TrendingUp, MapPin, Snowflake } from 'lucide-react'

function HomePage() {
  const {
    fetchWeather,
    filteredResorts,
    isLoading,
    error,
    lastUpdated,
    startAutoRefresh,
    stopAutoRefresh,
    stats,
    weatherData
  } = useWeatherStore()

  const navigate = useNavigate()

  useEffect(() => {
    fetchWeather()
    startAutoRefresh()
    return () => stopAutoRefresh()
  }, [fetchWeather, startAutoRefresh, stopAutoRefresh])

  const handleRefresh = () => {
    fetchWeather()
  }

  const handleResortClick = (resortId) => {
    navigate(`/resort/${resortId}`)
  }

  // Calculate some quick stats for the header
  const totalSnowNext5Days = Object.values(weatherData).reduce((sum, w) => {
    const next5 = w?.dailyForecast?.slice(0, 5) || []
    return sum + next5.reduce((s, d) => s + (d.snowfall || 0), 0)
  }, 0)

  const resortsWithSnow = Object.values(weatherData).filter(w => (w?.snow24h || 0) > 0).length

  return (
    <div className="min-h-screen bg-[#0f1219]">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Quick Stats Bar */}
        <div className="flex items-center justify-between mb-6 bg-[#1a1f2e] rounded-lg p-4 border border-slate-700/30">
          <div className="flex items-center gap-8">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 bg-blue-500/20 rounded-lg flex items-center justify-center">
                <Snowflake className="w-4 h-4 text-blue-400" />
              </div>
              <div>
                <div className="text-xs text-slate-500">Resorts w/ Snow (24h)</div>
                <div className="text-lg font-bold text-white">{resortsWithSnow}</div>
              </div>
            </div>

            {stats.mostSnow && (
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-purple-500/20 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-purple-400" />
                </div>
                <div>
                  <div className="text-xs text-slate-500">Most Snow (24h)</div>
                  <div className="text-lg font-bold text-white">
                    {stats.mostSnow.name} - {Math.round(weatherData[stats.mostSnow.id]?.snow24h || 0)}"
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
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
                  : 'bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700'
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
          <div className="space-y-3">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="bg-[#1e2536] rounded-lg p-4 animate-pulse border border-slate-700/30">
                <div className="flex items-center gap-3 mb-4">
                  <div className="w-10 h-10 bg-slate-700 rounded-lg" />
                  <div>
                    <div className="h-5 bg-slate-700 rounded w-40 mb-2" />
                    <div className="h-3 bg-slate-700/50 rounded w-24" />
                  </div>
                </div>
                <div className="flex gap-2">
                  {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15].map(j => (
                    <div key={j} className="flex flex-col items-center gap-1">
                      <div className="w-7 h-12 bg-slate-700/50 rounded" />
                      <div className="w-4 h-3 bg-slate-700/30 rounded" />
                    </div>
                  ))}
                </div>
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
              onClick={() => handleResortClick(resort.id)}
            />
          ))}
        </div>

        {/* Empty State */}
        {!isLoading && filteredResorts.length === 0 && (
          <div className="text-center py-12 text-slate-500">
            <Snowflake className="w-12 h-12 mx-auto mb-4 opacity-50" />
            <p>No resorts found matching your filters</p>
          </div>
        )}

        {/* Footer */}
        <footer className="mt-12 pt-6 border-t border-slate-800 text-center text-xs text-slate-500">
          <p>Weather data from Open-Meteo API • Auto-refreshes every 15 minutes</p>
          <p className="mt-1">Click on any resort to view detailed forecast</p>
        </footer>
      </main>
    </div>
  )
}

function App() {
  return (
    <Router basename="/powderpulse">
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/resort/:resortId" element={<ResortDetail />} />
      </Routes>
    </Router>
  )
}

export default App
