import React, { useRef } from 'react'
import { ChevronLeft, ChevronRight, Thermometer, Wind, Cloud, Sun, CloudSnow, CloudRain } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'
import { PASS_COLORS, REGIONS } from '../data/resorts'

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

// Get snow bar color based on amount
const getSnowBarColor = (inches) => {
  if (inches >= 12) return 'bg-purple-500'
  if (inches >= 6) return 'bg-blue-500'
  if (inches >= 3) return 'bg-blue-400'
  if (inches >= 1) return 'bg-blue-300'
  if (inches > 0) return 'bg-slate-500'
  return 'bg-transparent'
}

// Get snow bar height based on amount (max 40px)
const getSnowBarHeight = (inches) => {
  if (inches <= 0) return 4
  const height = Math.min(40, Math.max(8, inches * 4))
  return height
}

// Format snow amount for display
const formatSnow = (inches) => {
  if (!inches || inches === 0) return '0"'
  if (inches < 1) return `${inches.toFixed(1)}"`
  return `${Math.round(inches)}"`
}

// Get weather icon component
const WeatherIcon = ({ code, className = "w-5 h-5" }) => {
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

const ResortRow = ({ resort, viewMode }) => {
  const { getResortWeather } = useWeatherStore()
  const weather = getResortWeather(resort.id)
  const scrollRef = useRef(null)
  const passColor = PASS_COLORS[resort.pass] || PASS_COLORS.epic

  const scroll = (direction) => {
    if (scrollRef.current) {
      const scrollAmount = direction === 'left' ? -200 : 200
      scrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' })
    }
  }

  const dailyForecast = weather?.dailyForecast || []

  return (
    <div className="bg-[#252d3d] rounded-lg overflow-hidden">
      {/* Resort Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-700/50">
        <div className="flex items-center gap-3">
          {/* Flag/Logo placeholder */}
          <div className="w-10 h-10 rounded bg-slate-700 flex items-center justify-center text-lg">
            {REGION_FLAGS[resort.region]}
          </div>
          <div>
            <h3 className="font-semibold text-white hover:text-blue-400 cursor-pointer">
              {resort.name}
            </h3>
            <div className="flex items-center gap-2 text-sm text-slate-400">
              <span>{resort.elevation.toLocaleString()} ft</span>
              <span>•</span>
              <span className="text-blue-400">{REGION_LABELS[resort.region]}</span>
            </div>
          </div>
        </div>

        {/* Pass Badge */}
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

      {/* Content based on view mode */}
      <div className="relative">
        {/* Scroll buttons */}
        <button
          onClick={() => scroll('left')}
          className="absolute left-0 top-1/2 -translate-y-1/2 z-10 p-1 bg-slate-900/80 rounded-r hover:bg-slate-800"
        >
          <ChevronLeft className="w-5 h-5 text-slate-400" />
        </button>
        <button
          onClick={() => scroll('right')}
          className="absolute right-0 top-1/2 -translate-y-1/2 z-10 p-1 bg-slate-900/80 rounded-l hover:bg-slate-800"
        >
          <ChevronRight className="w-5 h-5 text-slate-400" />
        </button>

        {/* Scrollable forecast */}
        <div
          ref={scrollRef}
          className="flex overflow-x-auto scrollbar-hide px-8 py-4"
          style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
        >
          {viewMode === 'snow-summary' && (
            <SnowSummaryView forecast={dailyForecast} snow24h={weather?.snow24h} />
          )}
          {viewMode === 'weather' && (
            <WeatherView forecast={dailyForecast} current={weather?.current} />
          )}
          {viewMode === 'snow-forecast' && (
            <SnowForecastView forecast={dailyForecast} />
          )}
        </div>
      </div>
    </div>
  )
}

// Snow Summary View - Shows historical + forecast with center "Last 24 Hours"
const SnowSummaryView = ({ forecast, snow24h }) => {
  // Show 15 days
  const days = forecast.slice(0, 15)

  return (
    <div className="flex items-end gap-1 min-w-max">
      {/* Past periods (just show placeholders since we don't have historical data) */}
      <div className="flex flex-col items-center px-3">
        <span className="text-xs text-slate-500 mb-1">Prev 5 Days</span>
        <span className="text-slate-500 text-lg">--</span>
      </div>

      {/* Last 24 Hours - Highlighted */}
      <div className="flex flex-col items-center px-6 py-3 bg-slate-700/50 rounded-lg mx-2">
        <span className="text-xs text-slate-300 mb-1">Last 24 Hours</span>
        <span className="text-3xl font-bold text-white">{formatSnow(snow24h || 0)}</span>
      </div>

      {/* Next 15 days forecast */}
      {days.map((day, i) => {
        const date = new Date(day.date)
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' }).charAt(0)
        const dayNum = date.getDate()
        const isWeekend = date.getDay() === 0 || date.getDay() === 6

        return (
          <div key={i} className="flex flex-col items-center min-w-[40px]">
            {/* Snow amount */}
            <span className={`text-xs mb-1 ${day.snowfall > 0 ? 'text-blue-300' : 'text-slate-500'}`}>
              {day.snowfall > 0 ? Math.round(day.snowfall) : '0'}
            </span>

            {/* Snow bar */}
            <div className="h-10 w-6 flex items-end justify-center mb-1">
              <div
                className={`w-full rounded-t ${getSnowBarColor(day.snowfall)}`}
                style={{ height: `${getSnowBarHeight(day.snowfall)}px` }}
              />
            </div>

            {/* Day label */}
            <span className={`text-xs ${isWeekend ? 'text-yellow-500' : 'text-slate-400'}`}>
              {dayName}
            </span>
            <span className={`text-xs ${isWeekend ? 'text-yellow-500' : 'text-slate-500'}`}>
              {dayNum}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// Weather View - Shows current conditions and daily forecast
const WeatherView = ({ forecast, current }) => {
  const days = forecast.slice(0, 10)

  return (
    <div className="flex items-center gap-1 min-w-max">
      {/* Current conditions */}
      <div className="flex items-center gap-6 pr-6 mr-4 border-r border-slate-600">
        <div className="flex items-center gap-2">
          <Thermometer className="w-5 h-5 text-slate-400" />
          <span className="text-2xl font-semibold text-white">
            {current?.temp ? `${Math.round(current.temp)}°F` : '--'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Wind className="w-5 h-5 text-slate-400" />
          <span className="text-lg text-white">
            {current?.windSpeed ? `${Math.round(current.windSpeed)} mph` : '--'}
          </span>
        </div>
      </div>

      {/* Daily forecast */}
      {days.map((day, i) => {
        const date = new Date(day.date)
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' }).toUpperCase()
        const dayNum = date.getDate()
        const isWeekend = date.getDay() === 0 || date.getDay() === 6

        return (
          <div key={i} className="flex flex-col items-center min-w-[70px] px-2">
            {/* Day label */}
            <span className={`text-xs font-medium ${isWeekend ? 'text-yellow-500' : 'text-slate-400'}`}>
              {dayName} {dayNum}
            </span>

            {/* High/Low temps */}
            <div className="text-center my-2">
              <span className="text-white font-medium">{Math.round(day.tempMax)}°F</span>
              <br />
              <span className="text-slate-400 text-sm">{Math.round(day.tempMin)}°F</span>
            </div>

            {/* Weather icon */}
            <WeatherIcon code={day.weatherCode} />
          </div>
        )
      })}
    </div>
  )
}

// Snow Forecast View - Shows daily snow with bars, temps, and dates
const SnowForecastView = ({ forecast }) => {
  const days = forecast.slice(0, 15)

  return (
    <div className="flex items-end gap-1 min-w-max">
      {days.map((day, i) => {
        const date = new Date(day.date)
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short' })
        const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
        const isWeekend = date.getDay() === 0 || date.getDay() === 6
        const hasSnow = day.snowfall > 0

        return (
          <div key={i} className="flex flex-col items-center min-w-[60px]">
            {/* Snow range */}
            <span className={`text-xs font-medium mb-1 ${hasSnow ? 'text-blue-300' : 'text-slate-500'}`}>
              {hasSnow ? (
                day.snowfall < 1 ? '0-1"' :
                day.snowfall < 3 ? '1-3"' :
                day.snowfall < 6 ? '3-6"' :
                day.snowfall < 12 ? '6-12"' :
                '12"+'
              ) : '0"'}
            </span>

            {/* Snow bar */}
            <div className="h-12 w-8 flex items-end justify-center mb-1">
              <div
                className={`w-full rounded-t transition-all ${getSnowBarColor(day.snowfall)}`}
                style={{ height: `${getSnowBarHeight(day.snowfall)}px` }}
              />
            </div>

            {/* Temperature */}
            <span className="text-xs text-slate-400 mb-1">
              {Math.round(day.tempMax)}°F
            </span>

            {/* Day */}
            <span className={`text-xs ${isWeekend ? 'text-yellow-500' : 'text-slate-400'}`}>
              {dayName}
            </span>
            <span className={`text-xs ${isWeekend ? 'text-yellow-500' : 'text-slate-500'}`}>
              {date.getDate()}
            </span>
          </div>
        )
      })}
    </div>
  )
}

export default ResortRow
