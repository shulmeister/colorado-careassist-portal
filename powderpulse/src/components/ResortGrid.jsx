import React from 'react'
import useWeatherStore from '../stores/weatherStore'
import ResortCard from './ResortCard'

const ResortGrid = () => {
  const { filteredResorts, isLoading } = useWeatherStore()

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} className="bg-slate-800/50 rounded-xl p-4 animate-pulse">
            <div className="h-6 bg-slate-700 rounded w-32 mb-3" />
            <div className="h-4 bg-slate-700 rounded w-24 mb-4" />
            <div className="h-20 bg-slate-700 rounded mb-3" />
            <div className="grid grid-cols-3 gap-2">
              <div className="h-12 bg-slate-700 rounded" />
              <div className="h-12 bg-slate-700 rounded" />
              <div className="h-12 bg-slate-700 rounded" />
            </div>
          </div>
        ))}
      </div>
    )
  }

  if (filteredResorts.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-slate-400">No resorts match your filter criteria.</p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {filteredResorts.map(resort => (
        <ResortCard key={resort.id} resort={resort} />
      ))}
    </div>
  )
}

export default ResortGrid
