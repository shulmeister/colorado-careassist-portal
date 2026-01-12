import React from 'react'
import { MapPin, Thermometer, Mountain, Globe } from 'lucide-react'
import { AreaChart, Area, ResponsiveContainer } from 'recharts'
import useWeatherStore from '../stores/weatherStore'
import { PASS_COLORS } from '../data/resorts'
import { formatSnowAmount, formatTemp, getSnowHexColor } from '../utils/helpers'

const REGION_LABELS = {
  colorado: 'CO',
  utah: 'UT',
  wyoming: 'WY',
  canada: 'CAN',
  japan: 'JPN',
  europe: 'EU'
}

const REGION_FLAGS = {
  colorado: '🇺🇸',
  utah: '🇺🇸',
  wyoming: '🇺🇸',
  canada: '🇨🇦',
  japan: '🇯🇵',
  europe: '🇪🇺'
}

const ResortCard = ({ resort }) => {
  const { getResortWeather } = useWeatherStore()
  const weather = getResortWeather(resort.id)

  const passColor = PASS_COLORS[resort.pass] || PASS_COLORS.epic
  const isPowderDay = weather?.isPowderDay
  const isInternational = !['colorado', 'utah', 'wyoming'].includes(resort.region)

  return (
    <div
      className={`resort-card bg-slate-800/50 rounded-xl overflow-hidden border-l-4 ${
        isPowderDay ? 'ring-2 ring-purple-500/50' : ''
      }`}
      style={{ borderLeftColor: passColor.primary }}
    >
      {/* Header */}
      <div className="p-4 pb-2">
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-bold" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
              {resort.name}
            </h3>
            <div className="flex items-center gap-2 text-slate-400 text-sm mt-1">
              {isInternational ? (
                <>
                  <span>{REGION_FLAGS[resort.region]}</span>
                  <span>{REGION_LABELS[resort.region]}</span>
                </>
              ) : (
                <>
                  <MapPin className="w-3 h-3" />
                  <span>{resort.distanceFromBoulder} mi</span>
                </>
              )}
              <span className="text-slate-600">•</span>
              <Mountain className="w-3 h-3" />
              <span>{resort.elevation.toLocaleString()}'</span>
            </div>
          </div>

          {/* Pass badge */}
          <span
            className="px-2 py-1 rounded text-xs font-semibold uppercase"
            style={{
              backgroundColor: passColor.bg,
              color: passColor.primary
            }}
          >
            {resort.pass}
          </span>
        </div>

        {/* Powder day badge */}
        {isPowderDay && (
          <div className="mt-2 inline-flex items-center gap-1 px-2 py-1 bg-purple-500/20 text-purple-300 rounded-full text-xs font-semibold">
            <span className="animate-pulse">❄️</span>
            POWDER DAY
          </div>
        )}
      </div>

      {/* Current conditions */}
      <div className="px-4 py-2 flex items-center gap-4 border-t border-slate-700/50">
        <div className="flex items-center gap-1">
          <Thermometer className="w-4 h-4 text-slate-400" />
          <span className="text-lg font-semibold">
            {formatTemp(weather?.current?.temp)}
          </span>
        </div>
        {weather?.current?.snowDepth > 0 && (
          <div className="text-slate-400 text-sm">
            Base: {formatSnowAmount(weather.current.snowDepth)}
          </div>
        )}
      </div>

      {/* Snow stats */}
      <div className="px-4 py-3 grid grid-cols-3 gap-2 bg-slate-900/30">
        <SnowStat label="24hr" value={weather?.snow24h} />
        <SnowStat label="48hr" value={weather?.snow48h} />
        <SnowStat label="7-day" value={weather?.snow7Day} />
      </div>

      {/* Sparkline chart */}
      {weather?.sparklineData && (
        <div className="px-4 py-2 h-16">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={weather.sparklineData}>
              <defs>
                <linearGradient id={`gradient-${resort.id}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={passColor.primary} stopOpacity={0.4} />
                  <stop offset="100%" stopColor={passColor.primary} stopOpacity={0} />
                </linearGradient>
              </defs>
              <Area
                type="monotone"
                dataKey="snow"
                stroke={passColor.primary}
                strokeWidth={2}
                fill={`url(#gradient-${resort.id})`}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Footer with description */}
      <div className="px-4 py-2 border-t border-slate-700/50">
        <p className="text-slate-500 text-xs">{resort.description}</p>
      </div>
    </div>
  )
}

const SnowStat = ({ label, value }) => {
  const snowColor = getSnowHexColor(value || 0)

  return (
    <div className="text-center">
      <div className="text-xs text-slate-500 uppercase">{label}</div>
      <div
        className="text-lg font-bold"
        style={{ color: value > 0 ? snowColor : '#64748B' }}
      >
        {formatSnowAmount(value || 0)}
      </div>
    </div>
  )
}

export default ResortCard
