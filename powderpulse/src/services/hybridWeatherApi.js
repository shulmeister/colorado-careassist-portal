/**
 * Hybrid Weather API - Best of both worlds
 *
 * Strategy (Updated 2026-01-19):
 * - Days 1-10: met.no (yr.no) - verified most accurate
 * - Days 11-16: Open-Meteo with ski-optimized config - extended forecast
 *
 * This gives us:
 * - Highly accurate 10-day forecast from met.no
 * - Extended 15-day forecast using Open-Meteo
 * - Seamless merge with consistent data format
 */

import { fetchMetNoForResort } from './metNoApi.js'
import { fetchOpenMeteoWeather } from './ensembleWeatherApi.js'

// Delay helper
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Merge met.no (days 1-10) with Open-Meteo (days 11-16)
 * Creates a seamless 15-day forecast using the best data from each source
 */
function mergeForecasts(metNoData, openMeteoData, resort) {
  if (!metNoData && !openMeteoData) return null

  // If only one source available, use it
  if (!metNoData) return openMeteoData
  if (!openMeteoData) return metNoData

  // Merge daily forecasts: met.no for days 1-10, Open-Meteo for days 11-16
  const metNoDays = metNoData.dailyForecast || []
  const openMeteoDays = openMeteoData.dailyForecast || []

  // Get the dates from met.no to know where to splice
  const metNoDates = new Set(metNoDays.map(d => d.date))

  // Take met.no days 1-10, then add Open-Meteo days that are beyond met.no
  const extendedDays = openMeteoDays.filter(d => !metNoDates.has(d.date))
    .map(d => ({ ...d, source: 'open-meteo-extended' }))

  const mergedForecast = [...metNoDays, ...extendedDays].slice(0, 15)

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
    source: 'hybrid-met.no+open-meteo',
    lastUpdated: new Date().toISOString(),
    coordinates: metNoData.coordinates || openMeteoData.coordinates,
    // Use met.no current conditions (most accurate)
    current: metNoData.current || openMeteoData.current,
    // Snow totals from merged forecast
    snow24h: Math.round(snow24h * 10) / 10,
    snow48h: Math.round(snow48h * 10) / 10,
    snow5Day: Math.round(snow5Day * 10) / 10,
    snow7Day: Math.round(snow7Day * 10) / 10,
    snow10Day: Math.round(snow10Day * 10) / 10,
    snow15Day: Math.round(snow15Day * 10) / 10,
    // Merged 15-day forecast
    dailyForecast: mergedForecast,
    // Use Open-Meteo hourly (has freezing level, more parameters)
    hourlyForecast: openMeteoData.hourlyForecast || [],
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
 * Fetch weather for a single resort using hybrid approach
 * met.no for days 1-10, Open-Meteo for days 11-16
 */
export async function fetchResortWeather(resort) {
  try {
    // Fetch both sources in parallel
    const [metNoData, openMeteoData] = await Promise.all([
      fetchMetNoForResort(resort).catch(e => {
        console.warn(`Met.no failed for ${resort.name}:`, e.message)
        return null
      }),
      fetchOpenMeteoWeather(resort).catch(e => {
        console.warn(`Open-Meteo failed for ${resort.name}:`, e.message)
        return null
      })
    ])

    // Merge the forecasts
    const merged = mergeForecasts(metNoData, openMeteoData, resort)

    if (!merged) {
      console.error(`Both sources failed for ${resort.name}`)
      return null
    }

    return merged
  } catch (error) {
    console.error(`fetchResortWeather error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Fetch weather for ALL resorts using hybrid approach
 * Fetches met.no + Open-Meteo in parallel for each resort
 */
export async function fetchAllResortsWeatherHybrid(resorts) {
  const weatherData = {}

  console.log(`Fetching 15-day hybrid forecast for ${resorts.length} resorts (met.no + Open-Meteo)`)

  // Process resorts with small delay to be respectful to APIs
  const DELAY_MS = 100

  for (const resort of resorts) {
    try {
      const data = await fetchResortWeather(resort)
      if (data) {
        weatherData[resort.id] = data
      }
      await delay(DELAY_MS)
    } catch (e) {
      console.error(`Weather fetch failed for ${resort.name}:`, e.message)
    }
  }

  // Stats
  const hybridCount = Object.values(weatherData).filter(d => d.source === 'hybrid-met.no+open-meteo').length
  const metNoOnlyCount = Object.values(weatherData).filter(d => d.source === 'met-no').length
  const openMeteoOnlyCount = Object.values(weatherData).filter(d => d.source === 'open-meteo').length
  console.log(`Weather fetch complete: ${hybridCount} hybrid, ${metNoOnlyCount} met.no only, ${openMeteoOnlyCount} open-meteo only, ${resorts.length - Object.keys(weatherData).length} failed`)

  return weatherData
}

/**
 * Get weather source stats for debugging
 */
export function getSourceStats(weatherData) {
  const stats = {
    'hybrid-met.no+open-meteo': 0,
    'met-no': 0,
    'open-meteo': 0,
    failed: 0
  }

  for (const [resortId, data] of Object.entries(weatherData)) {
    if (!data) {
      stats.failed++
    } else {
      const source = data.source || 'unknown'
      stats[source] = (stats[source] || 0) + 1
    }
  }

  return stats
}

/**
 * Determine the best weather source for a resort
 */
export function getWeatherSource(resort) {
  return 'hybrid'
}

// Export as default for drop-in replacement
export default {
  fetchResortWeather,
  fetchAllResortsWeatherHybrid,
  fetchAllResortsWeather: fetchAllResortsWeatherHybrid,
  getWeatherSource,
  getSourceStats
}
