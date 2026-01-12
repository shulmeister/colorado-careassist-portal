import React from 'react'
import { Snowflake, Navigation, TrendingUp } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'
import { formatSnowAmount } from '../utils/helpers'
import { PASS_COLORS } from '../data/resorts'

const StatCard = ({ icon: Icon, title, value, subtitle, color, passType }) => {
  const borderColor = passType ? PASS_COLORS[passType]?.primary : color

  return (
    <div
      className="bg-slate-800/50 rounded-xl p-4 border-l-4"
      style={{ borderLeftColor: borderColor || '#3B82F6' }}
    >
      <div className="flex items-start justify-between">
        <div>
          <p className="text-slate-400 text-sm">{title}</p>
          <p className="text-2xl font-bold mt-1" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            {value}
          </p>
          {subtitle && (
            <p className="text-slate-500 text-sm mt-1">{subtitle}</p>
          )}
        </div>
        <div
          className="flex items-center justify-center w-10 h-10 rounded-lg"
          style={{ backgroundColor: `${borderColor}20` }}
        >
          <Icon className="w-5 h-5" style={{ color: borderColor }} />
        </div>
      </div>
    </div>
  )
}

const StatsCards = () => {
  const { stats, isLoading } = useWeatherStore()

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-slate-800/50 rounded-xl p-4 animate-pulse">
            <div className="h-4 bg-slate-700 rounded w-24 mb-2" />
            <div className="h-8 bg-slate-700 rounded w-32" />
          </div>
        ))}
      </div>
    )
  }

  const { mostSnow, closestSnow, bestValue } = stats

  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
      <StatCard
        icon={Snowflake}
        title="Most Snow (7-Day)"
        value={mostSnow ? mostSnow.name : '--'}
        subtitle={mostSnow ? `${formatSnowAmount(mostSnow.snow)} expected` : 'No data'}
        passType={mostSnow?.pass}
      />
      <StatCard
        icon={Navigation}
        title="Closest Snow (48hr)"
        value={closestSnow ? closestSnow.name : '--'}
        subtitle={closestSnow ? `${closestSnow.distanceFromBoulder} mi • ${formatSnowAmount(closestSnow.snow)}` : 'No snow nearby'}
        passType={closestSnow?.pass}
      />
      <StatCard
        icon={TrendingUp}
        title="Best Value"
        value={bestValue ? bestValue.name : '--'}
        subtitle={bestValue ? `${formatSnowAmount(bestValue.snow)} / ${bestValue.distanceFromBoulder} mi` : 'No data'}
        passType={bestValue?.pass}
      />
    </div>
  )
}

export default StatsCards
