import React from 'react'
import { Snowflake, MapPin, RefreshCw } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'
import { getTimeSinceUpdate } from '../utils/helpers'

const Header = () => {
  const {
    passFilter,
    setPassFilter,
    lastUpdated,
    isLoading,
    refresh
  } = useWeatherStore()

  return (
    <header className="sticky top-0 z-50 bg-[#0F172A]/95 backdrop-blur-sm border-b border-slate-800">
      <div className="max-w-7xl mx-auto px-4 py-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          {/* Logo and location */}
          <div className="flex items-center gap-3">
            <div className="flex items-center justify-center w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl">
              <Snowflake className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                PowderPulse
              </h1>
              <div className="flex items-center gap-1 text-slate-400 text-sm">
                <MapPin className="w-3 h-3" />
                <span>Boulder, CO</span>
              </div>
            </div>
          </div>

          {/* Pass filter toggle */}
          <div className="flex items-center gap-3">
            <div className="flex bg-slate-800 rounded-lg p-1">
              <button
                onClick={() => setPassFilter('all')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  passFilter === 'all'
                    ? 'bg-slate-700 text-white'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                All
              </button>
              <button
                onClick={() => setPassFilter('epic')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  passFilter === 'epic'
                    ? 'bg-[#0066CC] text-white'
                    : 'text-slate-400 hover:text-[#0066CC]'
                }`}
              >
                Epic
              </button>
              <button
                onClick={() => setPassFilter('ikon')}
                className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                  passFilter === 'ikon'
                    ? 'bg-[#E31837] text-white'
                    : 'text-slate-400 hover:text-[#E31837]'
                }`}
              >
                Ikon
              </button>
            </div>

            {/* Refresh button */}
            <button
              onClick={refresh}
              disabled={isLoading}
              className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 rounded-lg text-sm text-slate-300 transition-colors disabled:opacity-50"
            >
              <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
              <span className="hidden sm:inline">
                {isLoading ? 'Updating...' : getTimeSinceUpdate(lastUpdated)}
              </span>
            </button>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
