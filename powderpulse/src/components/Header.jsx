import React from 'react'
import { Snowflake, Filter } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'
import { PASS_COLORS } from '../data/resorts'

const Header = () => {
  const { passFilter, setPassFilter, filteredResorts } = useWeatherStore()

  const filters = [
    { id: 'all', label: 'All' },
    { id: 'epic', label: 'Epic', color: PASS_COLORS.epic.primary },
    { id: 'ikon', label: 'Ikon', color: PASS_COLORS.ikon.primary }
  ]

  return (
    <header className="bg-[#1a1f2e] border-b border-slate-700/50 sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-gradient-to-br from-blue-500 to-purple-600 rounded-lg flex items-center justify-center">
              <Snowflake className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
                PowderPulse
              </h1>
            </div>
          </div>

          {/* Pass Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-slate-500" />
            <div className="flex bg-slate-800/50 rounded-lg p-1">
              {filters.map(filter => (
                <button
                  key={filter.id}
                  onClick={() => setPassFilter(filter.id)}
                  className={`px-3 py-1.5 rounded-md text-sm font-medium transition-all ${
                    passFilter === filter.id
                      ? 'bg-slate-700 text-white'
                      : 'text-slate-400 hover:text-white'
                  }`}
                  style={passFilter === filter.id && filter.color ? {
                    backgroundColor: filter.color,
                    color: 'white'
                  } : {}}
                >
                  {filter.label}
                </button>
              ))}
            </div>
            <span className="text-sm text-slate-500 ml-2">
              {filteredResorts.length} resorts
            </span>
          </div>
        </div>
      </div>
    </header>
  )
}

export default Header
