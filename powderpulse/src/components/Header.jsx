import React from 'react'
import { Snowflake, Filter, Mountain } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'
import { PASS_COLORS } from '../data/resorts'

const Header = () => {
  const { passFilter, setPassFilter, filteredResorts } = useWeatherStore()

  const filters = [
    { id: 'all', label: 'All Resorts' },
    { id: 'epic', label: 'Epic Pass', color: PASS_COLORS.epic.primary },
    { id: 'ikon', label: 'Ikon Pass', color: PASS_COLORS.ikon.primary }
  ]

  return (
    <header className="bg-[#0f1219] border-b border-slate-800 sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-purple-600 rounded-xl flex items-center justify-center shadow-lg shadow-blue-500/20">
              <Snowflake className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white tracking-tight" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                PowderPulse
              </h1>
              <p className="text-[10px] text-slate-500 -mt-0.5">15-Day Snow Forecast</p>
            </div>
          </div>

          {/* Pass Filter */}
          <div className="flex items-center gap-4">
            <div className="flex bg-[#1a1f2e] rounded-lg p-1 border border-slate-700/50">
              {filters.map(filter => (
                <button
                  key={filter.id}
                  onClick={() => setPassFilter(filter.id)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-all ${
                    passFilter === filter.id
                      ? 'text-white shadow-sm'
                      : 'text-slate-400 hover:text-white'
                  }`}
                  style={passFilter === filter.id ? {
                    backgroundColor: filter.color || '#3b82f6',
                    color: 'white'
                  } : {}}
                >
                  {filter.label}
                </button>
              ))}
            </div>

            <div className="flex items-center gap-2 text-slate-500 border-l border-slate-700 pl-4">
              <Mountain className="w-4 h-4" />
              <span className="text-sm font-medium">{filteredResorts.length} resorts</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
