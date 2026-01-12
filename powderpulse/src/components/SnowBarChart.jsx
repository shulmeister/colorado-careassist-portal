import React from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell
} from 'recharts'
import useWeatherStore from '../stores/weatherStore'
import { resorts, PASS_COLORS } from '../data/resorts'
import { getSnowHexColor } from '../utils/helpers'

const SnowBarChart = () => {
  const { weatherData, isLoading } = useWeatherStore()

  if (isLoading) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-4">
        <div className="h-6 bg-slate-700 rounded w-48 mb-4" />
        <div className="h-64 bg-slate-700/50 rounded animate-pulse" />
      </div>
    )
  }

  // Prepare data sorted by snow amount
  const chartData = resorts
    .map(resort => ({
      name: resort.name,
      shortName: resort.name.split(' ')[0],
      snow: weatherData[resort.id]?.snow7Day || 0,
      pass: resort.pass
    }))
    .sort((a, b) => b.snow - a.snow)

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      return (
        <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-xl">
          <p className="font-semibold text-white">{data.name}</p>
          <p className="text-slate-300">
            <span className="font-bold" style={{ color: getSnowHexColor(data.snow) }}>
              {data.snow.toFixed(1)}"
            </span>
            {' '}expected (7-day)
          </p>
          <p className="text-xs text-slate-500 mt-1 uppercase">{data.pass} Pass</p>
        </div>
      )
    }
    return null
  }

  return (
    <div className="bg-slate-800/50 rounded-xl p-4">
      <h3 className="text-lg font-bold mb-4" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        7-Day Snowfall Forecast
      </h3>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 20, left: 60, bottom: 5 }}
          >
            <XAxis
              type="number"
              tickFormatter={(val) => `${val}"`}
              stroke="#64748B"
              fontSize={12}
            />
            <YAxis
              type="category"
              dataKey="shortName"
              stroke="#64748B"
              fontSize={12}
              width={55}
            />
            <Tooltip content={<CustomTooltip />} cursor={{ fill: '#1E293B' }} />
            <Bar dataKey="snow" radius={[0, 4, 4, 0]}>
              {chartData.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={getSnowHexColor(entry.snow)}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

export default SnowBarChart
