import React from 'react'
import { ArrowDownWideNarrow, Snowflake, Navigation, SortAsc, TrendingUp } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'

const sortOptions = [
  { value: 'snow', label: 'Most Snow', icon: Snowflake },
  { value: 'distance', label: 'Closest', icon: Navigation },
  { value: 'name', label: 'A-Z', icon: SortAsc },
  { value: 'value', label: 'Best Value', icon: TrendingUp }
]

const SortControls = () => {
  const { sortBy, setSortBy, filteredResorts } = useWeatherStore()

  return (
    <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div className="flex items-center gap-2 text-slate-400">
        <ArrowDownWideNarrow className="w-4 h-4" />
        <span className="text-sm">
          Showing <span className="text-white font-medium">{filteredResorts.length}</span> resorts
        </span>
      </div>

      <div className="flex flex-wrap gap-2">
        {sortOptions.map(option => {
          const Icon = option.icon
          const isActive = sortBy === option.value

          return (
            <button
              key={option.value}
              onClick={() => setSortBy(option.value)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm transition-all ${
                isActive
                  ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30'
                  : 'bg-slate-800 text-slate-400 hover:text-white border border-transparent'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{option.label}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}

export default SortControls
