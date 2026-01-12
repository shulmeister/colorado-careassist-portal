import React from 'react'
import { AlertTriangle, Snowflake } from 'lucide-react'
import useWeatherStore from '../stores/weatherStore'
import { formatSnowAmount } from '../utils/helpers'

const PowderAlert = () => {
  const { powderAlerts } = useWeatherStore()

  if (powderAlerts.length === 0) return null

  return (
    <div className="bg-gradient-to-r from-purple-900/50 to-blue-900/50 border border-purple-500/30 rounded-xl p-4 powder-alert-glow">
      <div className="flex items-start gap-3">
        <div className="flex items-center justify-center w-10 h-10 bg-purple-500/20 rounded-lg flex-shrink-0">
          <AlertTriangle className="w-5 h-5 text-purple-400" />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="text-lg font-bold text-purple-300 flex items-center gap-2" style={{ fontFamily: 'Space Grotesk, sans-serif' }}>
            <Snowflake className="w-5 h-5" />
            POWDER ALERT!
          </h3>
          <p className="text-slate-300 mt-1">
            {powderAlerts.length === 1 ? (
              <>
                <span className="font-semibold text-white">{powderAlerts[0].name}</span>
                {' '}expecting{' '}
                <span className="font-semibold text-purple-300">{formatSnowAmount(powderAlerts[0].snow48h)}</span>
                {' '}in the next 48 hours!
              </>
            ) : (
              <>
                <span className="font-semibold text-white">{powderAlerts.length} resorts</span>
                {' '}expecting 6"+ in the next 48 hours:{' '}
                {powderAlerts.map((r, i) => (
                  <span key={r.id}>
                    <span className="text-purple-300">{r.name}</span>
                    {' '}({formatSnowAmount(r.snow48h)})
                    {i < powderAlerts.length - 1 ? ', ' : ''}
                  </span>
                ))}
              </>
            )}
          </p>
        </div>
      </div>
    </div>
  )
}

export default PowderAlert
