import React, { useEffect, useRef } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  ArrowLeft,
  Thermometer,
  Wind,
  Droplets,
  Eye,
  Cloud,
  Sun,
  CloudSnow,
  CloudRain,
  Snowflake,
  TrendingUp,
  ChevronLeft,
  ChevronRight,
  Mountain,
  Map,
  Gauge,
  Clock,
  Calendar
} from 'lucide-react'
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ComposedChart
} from 'recharts'
import useWeatherStore from '../stores/weatherStore'
import { getResortById, PASS_COLORS } from '../data/resorts'
import { getLiftStatusColor } from '../services/liftieApi'

const REGION_FLAGS = {
  colorado: '🇺🇸',
  utah: '🇺🇸',
  wyoming: '🇺🇸',
  canada: '🇨🇦',
  japan: '🇯🇵',
  europe: '🇪🇺'
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

// Get snow color based on amount
const getSnowColor = (inches) => {
  if (inches >= 12) return { bg: 'bg-purple-600', text: 'text-purple-300', hex: '#9333ea' }
  if (inches >= 8) return { bg: 'bg-blue-600', text: 'text-blue-300', hex: '#2563eb' }
  if (inches >= 4) return { bg: 'bg-blue-500', text: 'text-blue-400', hex: '#3b82f6' }
  if (inches >= 2) return { bg: 'bg-blue-400', text: 'text-blue-400', hex: '#60a5fa' }
  if (inches > 0) return { bg: 'bg-slate-500', text: 'text-slate-400', hex: '#64748b' }
  return { bg: 'bg-slate-700', text: 'text-slate-500', hex: '#334155' }
}

// Format snow display
const formatSnow = (inches) => {
  if (!inches || inches === 0) return '0"'
  if (inches < 1) return `${inches.toFixed(1)}"`
  return `${Math.round(inches)}"`
}

// Custom tooltip for charts
const CustomTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-slate-800 border border-slate-600 rounded-lg p-3 shadow-lg">
        <p className="text-slate-300 text-sm mb-1">{label}</p>
        {payload.map((entry, index) => (
          <p key={index} style={{ color: entry.color }} className="text-sm font-medium">
            {entry.name}: {entry.value}{entry.unit || ''}
          </p>
        ))}
      </div>
    )
  }
  return null
}

const ResortDetail = () => {
  const { resortId } = useParams()
  const navigate = useNavigate()
  const { getResortWeather, getResortLiftStatus, fetchWeather, isLoading } = useWeatherStore()
  const hourlyScrollRef = useRef(null)

  const resort = getResortById(resortId)
  const weather = getResortWeather(resortId)
  const liftStatus = getResortLiftStatus(resortId)

  useEffect(() => {
    if (!weather) {
      fetchWeather()
    }
  }, [weather, fetchWeather])

  if (!resort) {
    return (
      <div className="min-h-screen bg-[#0f1219] flex items-center justify-center">
        <div className="text-center">
          <Snowflake className="w-16 h-16 mx-auto mb-4 text-slate-600" />
          <h2 className="text-2xl font-bold text-white mb-2">Resort Not Found</h2>
          <p className="text-slate-400 mb-6">The resort you're looking for doesn't exist.</p>
          <Link to="/" className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-500 transition-colors">
            Back to All Resorts
          </Link>
        </div>
      </div>
    )
  }

  const passColor = PASS_COLORS[resort.pass] || PASS_COLORS.epic
  const liftStatusInfo = liftStatus ? getLiftStatusColor(liftStatus.lifts.percentage) : null
  const dailyForecast = weather?.dailyForecast || []
  const hourlyForecast = weather?.hourlyForecast || []

  // Calculate snow totals
  const snow24h = weather?.snow24h || 0
  const snow48h = dailyForecast.slice(0, 2).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow7Day = dailyForecast.slice(0, 7).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow15Day = dailyForecast.reduce((sum, d) => sum + (d.snowfall || 0), 0)

  // Prepare chart data
  const snowAccumulationData = dailyForecast.map((day, idx) => {
    const date = new Date(day.date)
    const cumulative = dailyForecast.slice(0, idx + 1).reduce((sum, d) => sum + (d.snowfall || 0), 0)
    return {
      day: date.toLocaleDateString('en-US', { weekday: 'short' }),
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      snow: day.snowfall || 0,
      cumulative: Math.round(cumulative * 10) / 10
    }
  })

  const temperatureData = dailyForecast.map((day) => {
    const date = new Date(day.date)
    return {
      day: date.toLocaleDateString('en-US', { weekday: 'short' }),
      date: date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
      high: Math.round(day.tempMax),
      low: Math.round(day.tempMin),
      avg: Math.round((day.tempMax + day.tempMin) / 2)
    }
  })

  const windData = dailyForecast.map((day) => {
    const date = new Date(day.date)
    return {
      day: date.toLocaleDateString('en-US', { weekday: 'short' }),
      wind: Math.round(day.windSpeed || 0),
      gusts: Math.round(day.windGusts || day.windSpeed * 1.5 || 0)
    }
  })

  const scrollHourly = (direction) => {
    if (hourlyScrollRef.current) {
      const scrollAmount = direction === 'left' ? -300 : 300
      hourlyScrollRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' })
    }
  }

  return (
    <div className="min-h-screen bg-[#0f1219]">
      {/* Header */}
      <header className="bg-[#1a1f2e] border-b border-slate-700/30">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => navigate('/')}
                className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700 transition-colors"
              >
                <ArrowLeft className="w-5 h-5 text-slate-300" />
              </button>
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-slate-700/50 flex items-center justify-center text-2xl">
                  {REGION_FLAGS[resort.region]}
                </div>
                <div>
                  <div className="flex items-center gap-3">
                    <h1 className="text-2xl font-bold text-white">{resort.name}</h1>
                    <span
                      className="px-2 py-1 rounded text-xs font-bold uppercase"
                      style={{
                        backgroundColor: passColor.bg,
                        color: passColor.primary
                      }}
                    >
                      {resort.pass}
                    </span>
                    {liftStatusInfo && (
                      <span
                        className={`flex items-center gap-1 px-2 py-1 rounded text-xs font-bold ${liftStatusInfo.bg} text-white`}
                      >
                        <Gauge className="w-3 h-3" />
                        {Math.round(liftStatus.lifts.percentage)}% Open
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 text-sm text-slate-400 mt-1">
                    <span className="flex items-center gap-1">
                      <Mountain className="w-4 h-4" />
                      {resort.elevation.toLocaleString()} ft
                    </span>
                    <span>•</span>
                    <a
                      href={`https://openskimap.org/#14/${resort.latitude}/${resort.longitude}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 text-emerald-400 hover:text-emerald-300 transition-colors"
                    >
                      <Map className="w-4 h-4" />
                      Trail Map
                    </a>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 py-6">
        {/* Loading State */}
        {isLoading && !weather && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <Snowflake className="w-12 h-12 mx-auto mb-4 text-blue-400 animate-pulse" />
              <p className="text-slate-400">Loading weather data...</p>
            </div>
          </div>
        )}

        {weather && (
          <>
            {/* Hero Stats Row */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              {/* Current Temperature */}
              <div className="bg-gradient-to-br from-orange-500/20 to-red-500/20 rounded-xl p-6 border border-orange-500/30">
                <div className="flex items-center gap-2 text-orange-400 mb-2">
                  <Thermometer className="w-5 h-5" />
                  <span className="text-sm font-medium uppercase tracking-wide">Temperature</span>
                </div>
                <div className="text-5xl font-bold text-white">
                  {weather?.current?.temp ? `${Math.round(weather.current.temp)}°` : '--'}
                </div>
                <div className="text-slate-400 text-sm mt-2">
                  Feels like {weather?.current?.feelsLike ? `${Math.round(weather.current.feelsLike)}°` : '--'}
                </div>
              </div>

              {/* 24h Snowfall */}
              <div className="bg-gradient-to-br from-blue-500/20 to-cyan-500/20 rounded-xl p-6 border border-blue-500/30">
                <div className="flex items-center gap-2 text-blue-400 mb-2">
                  <Snowflake className="w-5 h-5" />
                  <span className="text-sm font-medium uppercase tracking-wide">Last 24h</span>
                </div>
                <div className={`text-5xl font-bold ${getSnowColor(snow24h).text}`}>
                  {formatSnow(snow24h)}
                </div>
                <div className="text-slate-400 text-sm mt-2">
                  {snow24h > 0 ? 'Fresh snow!' : 'No new snow'}
                </div>
              </div>

              {/* 7-Day Snow */}
              <div className="bg-gradient-to-br from-purple-500/20 to-pink-500/20 rounded-xl p-6 border border-purple-500/30">
                <div className="flex items-center gap-2 text-purple-400 mb-2">
                  <TrendingUp className="w-5 h-5" />
                  <span className="text-sm font-medium uppercase tracking-wide">Next 7 Days</span>
                </div>
                <div className={`text-5xl font-bold ${getSnowColor(snow7Day).text}`}>
                  {formatSnow(snow7Day)}
                </div>
                <div className="text-slate-400 text-sm mt-2">
                  Expected snowfall
                </div>
              </div>

              {/* Wind */}
              <div className="bg-gradient-to-br from-emerald-500/20 to-teal-500/20 rounded-xl p-6 border border-emerald-500/30">
                <div className="flex items-center gap-2 text-emerald-400 mb-2">
                  <Wind className="w-5 h-5" />
                  <span className="text-sm font-medium uppercase tracking-wide">Wind</span>
                </div>
                <div className="text-5xl font-bold text-white">
                  {weather?.current?.windSpeed ? `${Math.round(weather.current.windSpeed)}` : '--'}
                </div>
                <div className="text-slate-400 text-sm mt-2">mph current</div>
              </div>
            </div>

            {/* 24-Hour Forecast */}
            {hourlyForecast.length > 0 && (
              <div className="bg-[#1e2536] rounded-xl p-6 border border-slate-700/30 mb-6">
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-semibold text-white flex items-center gap-2">
                    <Clock className="w-5 h-5 text-slate-400" />
                    24-Hour Forecast
                  </h2>
                  <div className="flex gap-2">
                    <button
                      onClick={() => scrollHourly('left')}
                      className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700 transition-colors"
                    >
                      <ChevronLeft className="w-4 h-4 text-slate-300" />
                    </button>
                    <button
                      onClick={() => scrollHourly('right')}
                      className="p-2 rounded-lg bg-slate-800/50 hover:bg-slate-700 transition-colors"
                    >
                      <ChevronRight className="w-4 h-4 text-slate-300" />
                    </button>
                  </div>
                </div>
                <div
                  ref={hourlyScrollRef}
                  className="flex overflow-x-auto scrollbar-hide gap-3 pb-2"
                >
                  {hourlyForecast.slice(0, 24).map((hour, idx) => {
                    const time = new Date(hour.time)
                    const hourStr = time.toLocaleTimeString('en-US', { hour: 'numeric' })
                    const snowColor = getSnowColor(hour.snowfall || 0)

                    return (
                      <div
                        key={idx}
                        className="flex flex-col items-center min-w-[80px] bg-slate-800/30 rounded-lg p-3"
                      >
                        <span className="text-xs text-slate-400">{hourStr}</span>
                        <WeatherIcon code={hour.weatherCode} className="w-8 h-8 my-2" />
                        <span className="text-white font-bold">{Math.round(hour.temp)}°</span>
                        {hour.snowfall > 0 && (
                          <span className={`text-xs font-bold mt-1 ${snowColor.text}`}>
                            {formatSnow(hour.snowfall)}
                          </span>
                        )}
                        <div className="flex items-center gap-1 mt-2 text-xs text-slate-500">
                          <Wind className="w-3 h-3" />
                          {Math.round(hour.windSpeed)} mph
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Charts Grid */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
              {/* Snow Accumulation Chart */}
              <div className="bg-[#1e2536] rounded-xl p-6 border border-slate-700/30">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Snowflake className="w-5 h-5 text-blue-400" />
                  Snow Accumulation
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                  <ComposedChart data={snowAccumulationData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="day" stroke="#64748b" fontSize={12} />
                    <YAxis stroke="#64748b" fontSize={12} unit='"' />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="snow" fill="#3b82f6" name="Daily Snow" unit='"' radius={[4, 4, 0, 0]} />
                    <Line
                      type="monotone"
                      dataKey="cumulative"
                      stroke="#9333ea"
                      strokeWidth={3}
                      dot={{ fill: '#9333ea', r: 4 }}
                      name="Total Accumulation"
                      unit='"'
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* Temperature Chart */}
              <div className="bg-[#1e2536] rounded-xl p-6 border border-slate-700/30">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Thermometer className="w-5 h-5 text-orange-400" />
                  Temperature Forecast
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={temperatureData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="day" stroke="#64748b" fontSize={12} />
                    <YAxis stroke="#64748b" fontSize={12} unit="°" />
                    <Tooltip content={<CustomTooltip />} />
                    <Area
                      type="monotone"
                      dataKey="high"
                      stackId="1"
                      stroke="#ef4444"
                      fill="#ef4444"
                      fillOpacity={0.3}
                      name="High"
                      unit="°F"
                    />
                    <Area
                      type="monotone"
                      dataKey="low"
                      stackId="2"
                      stroke="#3b82f6"
                      fill="#3b82f6"
                      fillOpacity={0.3}
                      name="Low"
                      unit="°F"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              {/* Wind Chart */}
              <div className="bg-[#1e2536] rounded-xl p-6 border border-slate-700/30">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Wind className="w-5 h-5 text-emerald-400" />
                  Wind & Gusts
                </h2>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={windData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="day" stroke="#64748b" fontSize={12} />
                    <YAxis stroke="#64748b" fontSize={12} unit=" mph" />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="wind" fill="#10b981" name="Wind" unit=" mph" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="gusts" fill="#f59e0b" name="Gusts" unit=" mph" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>

              {/* Mountain Insights */}
              <div className="bg-[#1e2536] rounded-xl p-6 border border-slate-700/30">
                <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                  <Mountain className="w-5 h-5 text-slate-400" />
                  Mountain Insights
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="bg-slate-800/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-slate-400 mb-2">
                      <Droplets className="w-4 h-4" />
                      <span className="text-sm">Humidity</span>
                    </div>
                    <div className="text-2xl font-bold text-white">
                      {weather?.current?.humidity || '--'}%
                    </div>
                  </div>
                  <div className="bg-slate-800/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-slate-400 mb-2">
                      <Eye className="w-4 h-4" />
                      <span className="text-sm">Visibility</span>
                    </div>
                    <div className="text-2xl font-bold text-white">
                      {weather?.current?.visibility ? `${Math.round(weather.current.visibility / 1000)} km` : '--'}
                    </div>
                  </div>
                  <div className="bg-slate-800/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-slate-400 mb-2">
                      <Cloud className="w-4 h-4" />
                      <span className="text-sm">Cloud Cover</span>
                    </div>
                    <div className="text-2xl font-bold text-white">
                      {weather?.current?.cloudCover || '--'}%
                    </div>
                  </div>
                  <div className="bg-slate-800/30 rounded-lg p-4">
                    <div className="flex items-center gap-2 text-slate-400 mb-2">
                      <Snowflake className="w-4 h-4" />
                      <span className="text-sm">Snow Depth</span>
                    </div>
                    <div className="text-2xl font-bold text-white">
                      {weather?.current?.snowDepth ? `${Math.round(weather.current.snowDepth)}"` : '--'}
                    </div>
                  </div>
                </div>

                {/* Lift Status Details */}
                {liftStatus && (
                  <div className="mt-4 pt-4 border-t border-slate-700/30">
                    <h3 className="text-sm font-medium text-slate-400 mb-3">Lift Status</h3>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-6">
                        <div>
                          <div className="text-2xl font-bold text-green-400">{liftStatus.lifts.open}</div>
                          <div className="text-xs text-slate-500">Open</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-red-400">{liftStatus.lifts.closed}</div>
                          <div className="text-xs text-slate-500">Closed</div>
                        </div>
                        <div>
                          <div className="text-2xl font-bold text-yellow-400">{liftStatus.lifts.hold || 0}</div>
                          <div className="text-xs text-slate-500">On Hold</div>
                        </div>
                      </div>
                      <div className={`px-4 py-2 rounded-lg ${liftStatusInfo?.bg} text-white font-bold`}>
                        {Math.round(liftStatus.lifts.percentage)}% Open
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* 15-Day Forecast */}
            <div className="bg-[#1e2536] rounded-xl p-6 border border-slate-700/30">
              <h2 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
                <Calendar className="w-5 h-5 text-slate-400" />
                15-Day Extended Forecast
              </h2>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 uppercase tracking-wide border-b border-slate-700/30">
                      <th className="pb-3 pr-4">Day</th>
                      <th className="pb-3 px-4">Conditions</th>
                      <th className="pb-3 px-4 text-center">High / Low</th>
                      <th className="pb-3 px-4 text-center">Snow</th>
                      <th className="pb-3 px-4 text-center">Wind</th>
                      <th className="pb-3 pl-4 text-center">Precip %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dailyForecast.map((day, idx) => {
                      const date = new Date(day.date)
                      const dayName = date.toLocaleDateString('en-US', { weekday: 'long' })
                      const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
                      const isWeekend = date.getDay() === 0 || date.getDay() === 6
                      const snowColor = getSnowColor(day.snowfall)

                      return (
                        <tr
                          key={idx}
                          className={`border-b border-slate-700/20 ${isWeekend ? 'bg-yellow-500/5' : ''}`}
                        >
                          <td className="py-4 pr-4">
                            <div className={`font-medium ${isWeekend ? 'text-yellow-400' : 'text-white'}`}>
                              {dayName}
                            </div>
                            <div className="text-xs text-slate-500">{monthDay}</div>
                          </td>
                          <td className="py-4 px-4">
                            <div className="flex items-center gap-3">
                              <WeatherIcon code={day.weatherCode} className="w-8 h-8" />
                              <span className="text-slate-300 text-sm">
                                {day.weatherCode === 0 ? 'Clear' :
                                 [71, 73, 75, 77, 85, 86].includes(day.weatherCode) ? 'Snow' :
                                 [61, 63, 65, 66, 67, 80, 81, 82].includes(day.weatherCode) ? 'Rain' :
                                 'Cloudy'}
                              </span>
                            </div>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className="text-white font-medium">{Math.round(day.tempMax)}°</span>
                            <span className="text-slate-500 mx-1">/</span>
                            <span className="text-slate-400">{Math.round(day.tempMin)}°</span>
                          </td>
                          <td className="py-4 px-4 text-center">
                            <span className={`font-bold ${snowColor.text}`}>
                              {formatSnow(day.snowfall)}
                            </span>
                          </td>
                          <td className="py-4 px-4 text-center text-slate-300">
                            {Math.round(day.windSpeed || 0)} mph
                          </td>
                          <td className="py-4 pl-4 text-center text-slate-300">
                            {Math.round(day.precipProbability || 0)}%
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Snow Totals Summary */}
            <div className="mt-6 grid grid-cols-4 gap-4">
              <div className="bg-[#1e2536] rounded-xl p-4 border border-slate-700/30 text-center">
                <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Last 24h</div>
                <div className={`text-3xl font-bold ${getSnowColor(snow24h).text}`}>
                  {formatSnow(snow24h)}
                </div>
              </div>
              <div className="bg-[#1e2536] rounded-xl p-4 border border-slate-700/30 text-center">
                <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Next 48h</div>
                <div className={`text-3xl font-bold ${getSnowColor(snow48h).text}`}>
                  {formatSnow(snow48h)}
                </div>
              </div>
              <div className="bg-[#1e2536] rounded-xl p-4 border border-slate-700/30 text-center">
                <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Next 7 Days</div>
                <div className={`text-3xl font-bold ${getSnowColor(snow7Day).text}`}>
                  {formatSnow(snow7Day)}
                </div>
              </div>
              <div className="bg-[#1e2536] rounded-xl p-4 border border-slate-700/30 text-center">
                <div className="text-xs text-slate-500 uppercase tracking-wide mb-2">Next 15 Days</div>
                <div className={`text-3xl font-bold ${getSnowColor(snow15Day).text}`}>
                  {formatSnow(snow15Day)}
                </div>
              </div>
            </div>
          </>
        )}
      </main>

      {/* Footer */}
      <footer className="mt-12 py-6 border-t border-slate-800 text-center text-xs text-slate-500">
        <p>Weather data from Open-Meteo API • Lift status from Liftie</p>
      </footer>
    </div>
  )
}

export default ResortDetail
