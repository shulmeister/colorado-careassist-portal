import React from 'react'
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  ZAxis
} from 'recharts'
import useWeatherStore from '../stores/weatherStore'
import { resorts, PASS_COLORS } from '../data/resorts'
import { formatSnowAmount } from '../utils/helpers'

const ValueScatterPlot = () => {
  const { weatherData, isLoading } = useWeatherStore()

  if (isLoading) {
    return (
      <div className="bg-slate-800/50 rounded-xl p-4">
        <div className="h-6 bg-slate-700 rounded w-48 mb-4" />
        <div className="h-64 bg-slate-700/50 rounded animate-pulse" />
      </div>
    )
  }

  // Prepare data with snow and distance
  const epicData = resorts
    .filter(r => r.pass === 'epic')
    .map(resort => ({
      name: resort.name,
      distance: resort.distanceFromBoulder,
      snow: weatherData[resort.id]?.snow7Day || 0,
      pass: resort.pass
    }))

  const ikonData = resorts
    .filter(r => r.pass === 'ikon')
    .map(resort => ({
      name: resort.name,
      distance: resort.distanceFromBoulder,
      snow: weatherData[resort.id]?.snow7Day || 0,
      pass: resort.pass
    }))

  const CustomTooltip = ({ active, payload }) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload
      const valueRatio = (data.snow / data.distance * 100).toFixed(1)

      return (
        <div className="bg-slate-900 border border-slate-700 rounded-lg p-3 shadow-xl">
          <p className="font-semibold text-white">{data.name}</p>
          <p className="text-slate-300 text-sm">Distance: {data.distance} mi</p>
          <p className="text-slate-300 text-sm">Snow: {formatSnowAmount(data.snow)}</p>
          <p className="text-sm mt-1">
            Value: <span className="font-semibold text-green-400">{valueRatio}"/100mi</span>
          </p>
        </div>
      )
    }
    return null
  }

  // Calculate average snow for reference line
  const avgSnow = resorts.reduce((sum, r) => sum + (weatherData[r.id]?.snow7Day || 0), 0) / resorts.length

  return (
    <div className="bg-slate-800/50 rounded-xl p-4">
      <h3 className="text-lg font-bold mb-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
        Drive Value Analysis
      </h3>
      <p className="text-slate-400 text-sm mb-4">
        Distance vs. expected snow — find the best powder for your drive
      </p>

      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
            <XAxis
              type="number"
              dataKey="distance"
              name="Distance"
              unit=" mi"
              stroke="#64748B"
              fontSize={12}
              domain={[0, 'dataMax + 20']}
              label={{
                value: 'Distance from Boulder (mi)',
                position: 'bottom',
                fill: '#64748B',
                fontSize: 11
              }}
            />
            <YAxis
              type="number"
              dataKey="snow"
              name="Snow"
              unit='"'
              stroke="#64748B"
              fontSize={12}
              domain={[0, 'dataMax + 2']}
              label={{
                value: '7-Day Snow (in)',
                angle: -90,
                position: 'insideLeft',
                fill: '#64748B',
                fontSize: 11
              }}
            />
            <ZAxis range={[100, 400]} />
            <Tooltip content={<CustomTooltip />} cursor={{ strokeDasharray: '3 3' }} />
            <ReferenceLine
              y={avgSnow}
              stroke="#475569"
              strokeDasharray="5 5"
              label={{
                value: `Avg: ${avgSnow.toFixed(1)}"`,
                fill: '#64748B',
                fontSize: 10
              }}
            />
            <Scatter
              name="Epic Pass"
              data={epicData}
              fill={PASS_COLORS.epic.primary}
            />
            <Scatter
              name="Ikon Pass"
              data={ikonData}
              fill={PASS_COLORS.ikon.primary}
            />
          </ScatterChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 mt-2">
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PASS_COLORS.epic.primary }} />
          <span className="text-sm text-slate-400">Epic Pass</span>
        </div>
        <div className="flex items-center gap-2">
          <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PASS_COLORS.ikon.primary }} />
          <span className="text-sm text-slate-400">Ikon Pass</span>
        </div>
      </div>

      <p className="text-center text-xs text-slate-500 mt-2">
        Top-left = best value (more snow, less driving)
      </p>
    </div>
  )
}

export default ValueScatterPlot
