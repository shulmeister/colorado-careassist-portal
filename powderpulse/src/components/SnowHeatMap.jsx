import React from 'react'
import useWeatherStore from '../stores/weatherStore'
import { resorts } from '../data/resorts'
import { getSnowHexColor, getDayName } from '../utils/helpers'

const SnowHeatMap = () => {
  const { weatherData, isLoading } = useWeatherStore()

  if (isLoading) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-4">
        <div className="h-6 bg-slate-700 rounded w-48 mb-4" />
        <div className="h-64 bg-slate-700/50 rounded animate-pulse" />
      </div>
    )
  }

  // Get sorted resorts by total snow
  const sortedResorts = [...resorts].sort((a, b) => {
    const aSnow = weatherData[a.id]?.snow7Day || 0
    const bSnow = weatherData[b.id]?.snow7Day || 0
    return bSnow - aSnow
  })

  // Get days from first resort's data
  const firstResortData = weatherData[resorts[0]?.id]
  const days = firstResortData?.dailyForecast?.slice(0, 15) || []

  return (
    <div className="bg-slate-800/50 rounded-xl p-4 overflow-x-auto">
      <h3 className="text-lg font-bold mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        15-Day Snow Forecast
      </h3>

      <div className="min-w-[700px]">
        {/* Day headers */}
        <div className="flex mb-2">
          <div className="w-28 flex-shrink-0" />
          {days.map((day, i) => (
            <div
              key={day.date}
              className={`flex-1 text-center text-xs ${
                day.confidence === 'high' ? 'text-slate-300' :
                day.confidence === 'medium' ? 'text-slate-400' :
                'text-slate-500'
              }`}
            >
              {getDayName(day.date)}
            </div>
          ))}
        </div>

        {/* Resort rows */}
        {sortedResorts.map(resort => {
          const forecast = weatherData[resort.id]?.dailyForecast || []

          return (
            <div key={resort.id} className="flex mb-1">
              <div className="w-28 flex-shrink-0 text-sm text-slate-300 truncate pr-2">
                {resort.name}
              </div>
              <div className="flex flex-1 gap-0.5">
                {days.map((_, i) => {
                  const dayData = forecast[i]
                  const snow = dayData?.snowfall || 0
                  const confidence = dayData?.confidence || 'low'

                  return (
                    <div
                      key={i}
                      className={`flex-1 h-8 rounded-sm flex items-center justify-center text-xs font-medium transition-all hover:scale-105 ${
                        confidence === 'low' ? 'opacity-50' : ''
                      }`}
                      style={{
                        backgroundColor: snow > 0 ? getSnowHexColor(snow) : '#1E293B',
                        color: snow > 3 ? 'white' : '#94A3B8'
                      }}
                      title={`${resort.name}: ${snow.toFixed(1)}" on ${dayData?.date || ''}`}
                    >
                      {snow >= 1 ? Math.round(snow) : ''}
                    </div>
                  )
                })}
              </div>
            </div>
          )
        })}

        {/* Legend */}
        <div className="flex items-center justify-center gap-4 mt-4 pt-3 border-t border-slate-700">
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span>Snow (inches):</span>
          </div>
          {[
            { label: '1-3"', color: '#60A5FA' },
            { label: '3-6"', color: '#3B82F6' },
            { label: '6-12"', color: '#2563EB' },
            { label: '12-18"', color: '#1D4ED8' },
            { label: '18"+', color: '#7C3AED' }
          ].map(item => (
            <div key={item.label} className="flex items-center gap-1">
              <div
                className="w-4 h-4 rounded-sm"
                style={{ backgroundColor: item.color }}
              />
              <span className="text-xs text-slate-400">{item.label}</span>
            </div>
          ))}
        </div>

        {/* Confidence indicator */}
        <div className="flex items-center justify-center gap-6 mt-2 text-xs text-slate-500">
          <span className="text-slate-300">Days 1-7: High confidence</span>
          <span className="text-slate-400">Days 8-12: Medium</span>
          <span className="text-slate-500">Days 13-15: Low</span>
        </div>
      </div>
    </div>
  )
}

export default SnowHeatMap
