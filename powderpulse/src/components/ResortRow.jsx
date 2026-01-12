import React, { useRef } from 'react'
import { ChevronLeft, ChevronRight, Thermometer, Wind, Sun, Cloud, CloudSnow, CloudRain, Map, Gauge } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'
import { PASS_COLORS } from '../data/resorts'
import { getLiftStatusColor } from '../services/liftieApi'

const REGION_FLAGS = {
  colorado: '🇺🇸',
  utah: '🇺🇸',
  wyoming: '🇺🇸',
  canada: '🇨🇦',
  japan: '🇯🇵',
  europe: '🇪🇺'
}

const REGION_LABELS = {
  colorado: 'Colorado',
  utah: 'Utah',
  wyoming: 'Wyoming',
  canada: 'Canada',
  japan: 'Japan',
  europe: 'Europe'
}

// Get snow color based on amount
const getSnowColor = (inches) => {
  if (inches >= 12) return { bg: 'bg-purple-600', text: 'text-purple-300', hex: '#9333ea' }
  if (inches >= 8) return { bg: 'bg-blue-600', text: 'text-blue-300', hex: '#2563eb' }
  if (inches >= 4) return { bg: 'bg-blue-500', text: 'text-blue-400', hex: '#3b82f6' }
  if (inches >= 2) return { bg: 'bg-blue-400', text: 'text-blue-400', hex: '#60a5fa' }
  if (inches > 0) return { bg: 'bg-slate-500', text: 'text-slate-400', hex: '#64748b' }
  return { bg: 'bg-slate-700', text: 'text-slate-500', hex: '#334155' }
}

// Get snow bar height
const getSnowBarHeight = (inches, maxInches = 12) => {
  if (inches <= 0) return 4
  const percentage = Math.min(inches / maxInches, 1)
  return Math.max(8, percentage * 48)
}

// Format snow display
const formatSnow = (inches) => {
  if (!inches || inches === 0) return '0"'
  if (inches < 1) return `${inches.toFixed(1)}"`
  return `${Math.round(inches)}"`
}

// Weather icon component
const WeatherIcon = ({ code, className = "w-6 h-6" }) => {
  if ([71, 73, 75, 77, 85, 86].includes(code)) {
    return <CloudSnow className={`${className} text-blue-300`} />
  }
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) {
    return <CloudRain className={`${className} text-blue-400`} />
  }
  if ([0, 1].includes(code)) {
    return <Sun className={`${className} text-yellow-400`} />
  }
  return <Cloud className={`${className} text-slate-400`} />
}

// Group days into periods like OpenSnow
const groupIntoPeriods = (forecast) => {
  if (!forecast || forecast.length === 0) return []

  const periods = []

  // Next 1-5 Days
  const next1to5 = forecast.slice(0, 5)
  const next1to5Total = next1to5.reduce((sum, d) => sum + (d.snowfall || 0), 0)
  periods.push({ label: 'Next 1-5 Days', total: next1to5Total })

  // Next 6-10 Days
  const next6to10 = forecast.slice(5, 10)
  const next6to10Total = next6to10.reduce((sum, d) => sum + (d.snowfall || 0), 0)
  periods.push({ label: 'Next 6-10 Days', total: next6to10Total })

  // Next 11-15 Days
  const next11to15 = forecast.slice(10, 15)
  const next11to15Total = next11to15.reduce((sum, d) => sum + (d.snowfall || 0), 0)
  periods.push({ label: 'Next 11-15 Days', total: next11to15Total })

  return periods
}

const ResortRow = ({ resort, onClick }) => {
  const { getResortWeather, getResortLiftStatus } = useWeatherStore()
  const weather = getResortWeather(resort.id)
  const liftStatus = getResortLiftStatus(resort.id)
  const scrollRef = useRef(null)
  const passColor = PASS_COLORS[resort.pass] || PASS_COLORS.epic

  const dailyForecast = weather?.dailyForecast || []
  const periods = groupIntoPeriods(dailyForecast)

  // Get lift status color
  const liftStatusInfo = liftStatus ? getLiftStatusColor(liftStatus.lifts.percentage) : null

  const scroll = (e, direction) => {
    e.stopPropagation()
    if (scrollRef.current) {
      const scrollAmount = direction === 'left' ? -200 : 200
      scrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' })
    }
  }

  // Calculate totals for display
  const next5DaysSnow = dailyForecast.slice(0, 5).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const next10DaysSnow = dailyForecast.slice(0, 10).reduce((sum, d) => sum + (d.snowfall || 0), 0)

  return (
    <div
      className="bg-[#1e2536] rounded-lg overflow-hidden border border-slate-700/30 cursor-pointer hover:border-slate-600/50 transition-colors"
      onClick={onClick}
    >
      {/* Header Row */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/30">
        {/* Left: Resort Info */}
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-slate-700/50 flex items-center justify-center text-xl">
            {REGION_FLAGS[resort.region]}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-white">
                {resort.name}
              </h3>
              <span
                className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase"
                style={{
                  backgroundColor: passColor.bg,
                  color: passColor.primary
                }}
              >
                {resort.pass}
              </span>
              {/* Lift Status Indicator */}
              {liftStatusInfo && (
                <span
                  className={`flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-bold ${liftStatusInfo.bg} text-white`}
                  title={`${Math.round(liftStatus.lifts.percentage)}% lifts open (${liftStatus.lifts.open}/${liftStatus.lifts.open + liftStatus.lifts.closed})`}
                >
                  <Gauge className="w-3 h-3" />
                  {Math.round(liftStatus.lifts.percentage)}%
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <span>{resort.elevation.toLocaleString()} ft</span>
              <span className="text-slate-600">•</span>
              <span className="text-blue-400">{REGION_LABELS[resort.region]}</span>
              <span className="text-slate-600">•</span>
              <a
                href={`https://openskimap.org/#14/${resort.latitude}/${resort.longitude}`}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 transition-colors"
                onClick={(e) => e.stopPropagation()}
              >
                <Map className="w-3 h-3" />
                <span>Trail Map</span>
              </a>
            </div>
          </div>
        </div>

        {/* Center: Snow Period Summaries */}
        <div className="flex items-center gap-6">
          {/* Last 24 Hours */}
          <div className="text-center">
            <div className="text-[10px] text-slate-500 uppercase tracking-wide">Last 24h</div>
            <div className={`text-2xl font-bold ${getSnowColor(weather?.snow24h || 0).text}`}>
              {formatSnow(weather?.snow24h || 0)}
            </div>
          </div>

          {/* Period Summaries */}
          {periods.map((period, idx) => (
            <div key={idx} className="text-center">
              <div className="text-[10px] text-slate-500 uppercase tracking-wide whitespace-nowrap">
                {period.label}
              </div>
              <div className={`text-xl font-bold ${getSnowColor(period.total).text}`}>
                {formatSnow(period.total)}
              </div>
            </div>
          ))}
        </div>

        {/* Right: Current Temp */}
        <div className="flex items-center gap-1 text-slate-400">
          <Thermometer className="w-4 h-4" />
          <span className="text-lg font-medium text-white">
            {weather?.current?.temp ? `${Math.round(weather.current.temp)}°F` : '--'}
          </span>
        </div>
      </div>

      {/* Details Grid */}
      <div className="px-4 py-3 grid grid-cols-4 gap-4 border-b border-slate-700/30 text-sm">
        {/* Current Conditions */}
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">Current</div>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">Temperature</span>
              <span className="text-white font-medium">
                {weather?.current?.temp ? `${Math.round(weather.current.temp)}°F` : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Wind</span>
              <span className="text-white font-medium">
                {weather?.current?.windSpeed ? `${Math.round(weather.current.windSpeed)} mph` : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Humidity</span>
              <span className="text-white font-medium">
                {weather?.current?.humidity ? `${weather.current.humidity}%` : '--'}
              </span>
            </div>
          </div>
        </div>

        {/* Snow Totals */}
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">Snow Totals</div>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">Last 24h</span>
              <span className={`font-bold ${getSnowColor(weather?.snow24h || 0).text}`}>
                {formatSnow(weather?.snow24h || 0)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Next 5 days</span>
              <span className={`font-bold ${getSnowColor(next5DaysSnow).text}`}>
                {formatSnow(next5DaysSnow)}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Next 10 days</span>
              <span className={`font-bold ${getSnowColor(next10DaysSnow).text}`}>
                {formatSnow(next10DaysSnow)}
              </span>
            </div>
          </div>
        </div>

        {/* Resort Info */}
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">Resort Info</div>
          <div className="space-y-1">
            <div className="flex justify-between">
              <span className="text-slate-400">Elevation</span>
              <span className="text-white font-medium">{resort.elevation.toLocaleString()} ft</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Region</span>
              <span className="text-white font-medium">{REGION_LABELS[resort.region]}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Pass</span>
              <span style={{ color: passColor.primary }} className="font-bold uppercase">
                {resort.pass}
              </span>
            </div>
          </div>
        </div>

        {/* 3-Day Forecast Preview */}
        <div>
          <div className="text-[10px] text-slate-500 uppercase tracking-wide mb-2">Forecast</div>
          <div className="space-y-1">
            {dailyForecast.slice(0, 3).map((day, i) => {
              const date = new Date(day.date)
              const dayName = date.toLocaleDateString('en-US', { weekday: 'short' })
              return (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-slate-400">{dayName}</span>
                  <div className="flex items-center gap-2">
                    <WeatherIcon code={day.weatherCode} className="w-4 h-4" />
                    <span className="text-white">
                      {Math.round(day.tempMax)}° / {Math.round(day.tempMin)}°
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* 15-Day Forecast */}
      <div className="px-4 py-3">
        <div className="text-[10px] text-slate-500 uppercase tracking-wide mb-3">15-Day Forecast</div>
        <div className="relative">
          <button
            onClick={(e) => scroll(e, 'left')}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-10 p-1.5 bg-slate-800/90 rounded-full hover:bg-slate-700 border border-slate-600"
          >
            <ChevronLeft className="w-4 h-4 text-slate-300" />
          </button>
          <button
            onClick={(e) => scroll(e, 'right')}
            className="absolute right-0 top-1/2 -translate-y-1/2 z-10 p-1.5 bg-slate-800/90 rounded-full hover:bg-slate-700 border border-slate-600"
          >
            <ChevronRight className="w-4 h-4 text-slate-300" />
          </button>

          <div
            ref={scrollRef}
            className="flex overflow-x-auto scrollbar-hide px-8 gap-2"
          >
            {dailyForecast.map((day, i) => {
              const date = new Date(day.date)
              const dayName = date.toLocaleDateString('en-US', { weekday: 'short' })
              const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
              const isWeekend = date.getDay() === 0 || date.getDay() === 6
              const snowColor = getSnowColor(day.snowfall)

              return (
                <div
                  key={i}
                  className={`flex flex-col items-center min-w-[70px] p-3 rounded-lg ${
                    isWeekend ? 'bg-yellow-500/10' : 'bg-slate-800/30'
                  }`}
                >
                  <span className={`text-xs font-medium ${isWeekend ? 'text-yellow-500' : 'text-slate-400'}`}>
                    {dayName}
                  </span>
                  <span className={`text-[10px] ${isWeekend ? 'text-yellow-500/70' : 'text-slate-500'}`}>
                    {monthDay}
                  </span>

                  <div className="my-2">
                    <WeatherIcon code={day.weatherCode} />
                  </div>

                  <div className="h-12 w-8 flex items-end justify-center mb-2">
                    <div
                      className={`w-full rounded-t ${snowColor.bg}`}
                      style={{ height: `${getSnowBarHeight(day.snowfall)}px` }}
                    />
                  </div>

                  <span className={`text-sm font-bold ${snowColor.text}`}>
                    {formatSnow(day.snowfall)}
                  </span>

                  <div className="mt-2 text-xs text-center">
                    <span className="text-white">{Math.round(day.tempMax)}°</span>
                    <span className="text-slate-500"> / </span>
                    <span className="text-slate-400">{Math.round(day.tempMin)}°</span>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

export default ResortRow
