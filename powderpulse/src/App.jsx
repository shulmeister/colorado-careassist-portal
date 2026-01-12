import React, { useEffect } from 'react'
import useWeatherStore from './stores/weatherStore'
import Header from './components/Header'
import PowderAlert from './components/PowderAlert'
import StatsCards from './components/StatsCards'
import SortControls from './components/SortControls'
import ResortGrid from './components/ResortGrid'
import SnowBarChart from './components/SnowBarChart'
import SnowHeatMap from './components/SnowHeatMap'
import ValueScatterPlot from './components/ValueScatterPlot'
import { RefreshCw, AlertCircle } from 'lucide-react'

function App() {
  const {
    fetchWeather,
    isLoading,
    error,
    lastUpdated,
    startAutoRefresh,
    stopAutoRefresh
  } = useWeatherStore()

  useEffect(() => {
    // Fetch weather on mount
    fetchWeather()

    // Start auto-refresh (every 15 minutes)
    startAutoRefresh()

    // Cleanup on unmount
    return () => stopAutoRefresh()
  }, [fetchWeather, startAutoRefresh, stopAutoRefresh])

  const handleRefresh = () => {
    fetchWeather()
  }

  return (
    <div className="min-h-screen bg-slate-900">
      <Header />

      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Error Banner */}
        {error && (
          <div className="mb-6 bg-red-500/10 border border-red-500/30 rounded-xl p-4 flex items-center gap-3">
            <AlertCircle className="w-5 h-5 text-red-400 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-red-400 font-medium">Unable to load weather data</p>
              <p className="text-red-400/70 text-sm">{error}</p>
            </div>
            <button
              onClick={handleRefresh}
              className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 text-red-400 rounded-lg transition-colors"
            >
              Retry
            </button>
          </div>
        )}

        {/* Powder Alert */}
        <PowderAlert />

        {/* Stats Cards */}
        <section className="mb-8">
          <StatsCards />
        </section>

        {/* Last Updated + Refresh */}
        <div className="flex items-center justify-between mb-6">
          <div className="text-sm text-slate-500">
            {lastUpdated ? (
              <>Last updated: {new Date(lastUpdated).toLocaleTimeString()}</>
            ) : (
              <>Loading weather data...</>
            )}
          </div>
          <button
            onClick={handleRefresh}
            disabled={isLoading}
            className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all ${
              isLoading
                ? 'bg-slate-700 text-slate-500 cursor-not-allowed'
                : 'bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700'
            }`}
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
            <span>{isLoading ? 'Refreshing...' : 'Refresh'}</span>
          </button>
        </div>

        {/* Sort Controls */}
        <section className="mb-6">
          <SortControls />
        </section>

        {/* Resort Cards Grid */}
        <section className="mb-8">
          <ResortGrid />
        </section>

        {/* Charts Section */}
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-8">
          <SnowBarChart />
          <ValueScatterPlot />
        </section>

        {/* Heat Map - Full Width */}
        <section className="mb-8">
          <SnowHeatMap />
        </section>

        {/* Footer */}
        <footer className="border-t border-slate-800 pt-6 pb-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4 text-sm text-slate-500">
            <div className="flex items-center gap-2">
              <span className="text-2xl">🎿</span>
              <span>PowderPulse</span>
              <span className="text-slate-600">|</span>
              <span>Colorado Ski Weather Dashboard</span>
            </div>
            <div className="flex items-center gap-4">
              <span>Weather data from Open-Meteo</span>
              <span className="text-slate-600">|</span>
              <span>Auto-refreshes every 15 min</span>
            </div>
          </div>
          <div className="text-center mt-4 text-xs text-slate-600">
            Forecast confidence decreases beyond 7 days. Always check official resort conditions.
          </div>
        </footer>
      </main>
    </div>
  )
}

export default App
