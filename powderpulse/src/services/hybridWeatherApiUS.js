/**
 * US Resort Weather API - NWS + ECMWF Hybrid
 *
 * Strategy:
 * - Days 1-7: NWS (National Weather Service) gridpoint data
 *   - 2.5km resolution, human-corrected for mountain terrain
 *   - NWS forecasters incorporate HRRR (3km) model runs
 *   - Best available source for US mountain snowfall
 * - Days 8-15: ECMWF via Open-Meteo
 *   - Best synoptic storm prediction for extended range
 * - Fallback: met.no + ECMWF (previous behavior) if NWS fails
 */

import { fetchNWSWeather } from './nwsApi.js'
import { fetchOpenMeteoWeather } from './ensembleWeatherApi.js'
import { fetchMetNoForResort } from './metNoApi.js'

/**
 * Merge NWS (days 1-7) with ECMWF (days 8-15)
 * NWS provides terrain-corrected short-range, ECMWF extends to 15 days
 */
function mergeUSForecasts(nwsData, ecmwfData, resort) {
  if (!nwsData && !ecmwfData) return null
  if (!nwsData) return ecmwfData
  if (!ecmwfData) return nwsData

  // NWS provides days 1-7
  const nwsDays = nwsData.dailyForecast || []

  // ECMWF provides days 1-15, we only want dates beyond NWS coverage
  const ecmwfDays = ecmwfData.dailyForecast || []
  const nwsDates = new Set(nwsDays.map(d => d.date))
  const extendedDays = ecmwfDays
    .filter(d => !nwsDates.has(d.date))
    .map(d => ({ ...d, source: 'ecmwf-extended' }))

  const mergedForecast = [...nwsDays, ...extendedDays].slice(0, 15)

  // Recalculate snow totals from merged forecast
  const snow24h = mergedForecast[0]?.snowfall || 0
  const snow48h = mergedForecast.slice(0, 2).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow5Day = mergedForecast.slice(0, 5).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow7Day = mergedForecast.slice(0, 7).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow10Day = mergedForecast.slice(0, 10).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow15Day = mergedForecast.slice(0, 15).reduce((sum, d) => sum + (d.snowfall || 0), 0)

  // Find biggest snow day
  const biggestDay = mergedForecast.reduce((max, day) =>
    (day.snowfall || 0) > (max.snowfall || 0) ? day : max,
    mergedForecast[0] || { snowfall: 0, date: null }
  )

  // Powder alert: 6"+ in next 48 hours
  const isPowderDay = snow48h >= 6

  return {
    resortId: resort.id,
    source: 'hybrid-nws+ecmwf',
    lastUpdated: new Date().toISOString(),
    coordinates: nwsData.coordinates || ecmwfData.coordinates,
    // Use NWS current conditions (more accurate for US mountains)
    current: nwsData.current || ecmwfData.current,
    // Snow totals from merged forecast
    snow24h: Math.round(snow24h * 10) / 10,
    snow48h: Math.round(snow48h * 10) / 10,
    snow5Day: Math.round(snow5Day * 10) / 10,
    snow7Day: Math.round(snow7Day * 10) / 10,
    snow10Day: Math.round(snow10Day * 10) / 10,
    snow15Day: Math.round(snow15Day * 10) / 10,
    // Merged 15-day forecast
    dailyForecast: mergedForecast,
    // Use ECMWF hourly (has freezing level height, snow depth, more parameters)
    hourlyForecast: ecmwfData.hourlyForecast || [],
    // Alerts
    isPowderDay,
    biggestDay: biggestDay.date ? {
      date: biggestDay.date,
      snowfall: Math.round((biggestDay.snowfall || 0) * 10) / 10
    } : null,
    // Sparkline data
    sparklineData: mergedForecast.slice(0, 15).map(d => ({
      day: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' }),
      date: d.date,
      snow: Math.round((d.snowfall || 0) * 10) / 10
    }))
  }
}

/**
 * Merge met.no + ECMWF as fallback (same as international pipeline)
 */
function mergeFallbackForecasts(metNoData, ecmwfData, resort) {
  if (!metNoData && !ecmwfData) return null
  if (!metNoData) return ecmwfData
  if (!ecmwfData) return metNoData

  const metNoDays = metNoData.dailyForecast || []
  const ecmwfDays = ecmwfData.dailyForecast || []
  const metNoDates = new Set(metNoDays.map(d => d.date))
  const extendedDays = ecmwfDays
    .filter(d => !metNoDates.has(d.date))
    .map(d => ({ ...d, source: 'open-meteo-extended' }))

  const mergedForecast = [...metNoDays, ...extendedDays].slice(0, 15)

  const snow24h = mergedForecast[0]?.snowfall || 0
  const snow48h = mergedForecast.slice(0, 2).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow5Day = mergedForecast.slice(0, 5).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow7Day = mergedForecast.slice(0, 7).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow10Day = mergedForecast.slice(0, 10).reduce((sum, d) => sum + (d.snowfall || 0), 0)
  const snow15Day = mergedForecast.slice(0, 15).reduce((sum, d) => sum + (d.snowfall || 0), 0)

  const biggestDay = mergedForecast.reduce((max, day) =>
    (day.snowfall || 0) > (max.snowfall || 0) ? day : max,
    mergedForecast[0] || { snowfall: 0, date: null }
  )

  const isPowderDay = snow48h >= 6

  return {
    resortId: resort.id,
    source: 'hybrid-met.no+open-meteo',
    lastUpdated: new Date().toISOString(),
    coordinates: metNoData.coordinates || ecmwfData.coordinates,
    current: metNoData.current || ecmwfData.current,
    snow24h: Math.round(snow24h * 10) / 10,
    snow48h: Math.round(snow48h * 10) / 10,
    snow5Day: Math.round(snow5Day * 10) / 10,
    snow7Day: Math.round(snow7Day * 10) / 10,
    snow10Day: Math.round(snow10Day * 10) / 10,
    snow15Day: Math.round(snow15Day * 10) / 10,
    dailyForecast: mergedForecast,
    hourlyForecast: ecmwfData.hourlyForecast || [],
    isPowderDay,
    biggestDay: biggestDay.date ? {
      date: biggestDay.date,
      snowfall: Math.round((biggestDay.snowfall || 0) * 10) / 10
    } : null,
    sparklineData: mergedForecast.slice(0, 15).map(d => ({
      day: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' }),
      date: d.date,
      snow: Math.round((d.snowfall || 0) * 10) / 10
    }))
  }
}

/**
 * Fetch weather for a US resort using NWS + ECMWF hybrid
 * Falls back to met.no + ECMWF if NWS fails
 */
export async function fetchUSResortWeather(resort) {
  try {
    // Always fetch ECMWF (needed for days 8-15 and hourly data)
    const ecmwfPromise = fetchOpenMeteoWeather(resort).catch(e => {
      console.warn(`Open-Meteo failed for ${resort.name}:`, e.message)
      return null
    })

    // Try NWS first (primary source for US)
    const nwsData = await fetchNWSWeather(resort).catch(e => {
      console.warn(`NWS failed for ${resort.name}:`, e.message)
      return null
    })

    const ecmwfData = await ecmwfPromise

    if (nwsData) {
      // Success: NWS days 1-7 + ECMWF days 8-15
      const merged = mergeUSForecasts(nwsData, ecmwfData, resort)
      if (merged) {
        console.log(`${resort.name}: NWS+ECMWF hybrid (${nwsData.dailyForecast?.length || 0} NWS days)`)
        return merged
      }
    }

    // Fallback: met.no + ECMWF (previous behavior)
    console.warn(`${resort.name}: NWS unavailable, falling back to met.no`)
    const metNoData = await fetchMetNoForResort(resort).catch(e => {
      console.warn(`Met.no fallback also failed for ${resort.name}:`, e.message)
      return null
    })

    const fallback = mergeFallbackForecasts(metNoData, ecmwfData, resort)
    if (fallback) return fallback

    // Last resort: ECMWF only
    if (ecmwfData) return ecmwfData

    console.error(`All sources failed for ${resort.name}`)
    return null
  } catch (error) {
    console.error(`fetchUSResortWeather error for ${resort.name}:`, error)
    return null
  }
}

export default {
  fetchUSResortWeather,
  mergeUSForecasts
}
