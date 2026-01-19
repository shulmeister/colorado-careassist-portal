/**
 * Hybrid Weather API - Routes to best source per region
 *
 * Strategy (Updated 2026-01-19):
 * - ALL REGIONS: yr.no / met.no (Norwegian Meteorological Institute)
 *   - Free, no API key required
 *   - Verified accurate for US, Japan, and Europe
 *   - Uses ECMWF and other high-quality models
 *   - Supports altitude parameter for mountain accuracy
 *
 * Fallback: Open-Meteo ECMWF if met.no fails
 */

import { fetchMetNoForResort } from './metNoApi.js'
import { fetchOpenMeteoWeather } from './ensembleWeatherApi.js'

// Delay helper
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Determine the best weather source for a resort
 * As of 2026-01-19: Using met.no (yr.no) for ALL regions
 * - Verified accurate for US, Japan, and Europe
 * - Free, no API key, supports altitude parameter
 */
export function getWeatherSource(resort) {
  // Use met.no for all regions - verified most accurate
  return 'met-no'
}

/**
 * Fetch weather for a single resort using met.no (yr.no)
 * Falls back to Open-Meteo if met.no fails
 */
export async function fetchResortWeather(resort) {
  try {
    // Primary: met.no (yr.no) - verified accurate for all regions
    let data = await fetchMetNoForResort(resort)

    if (!data) {
      console.log(`Met.no failed for ${resort.name}, falling back to Open-Meteo`)
      data = await fetchOpenMeteoWeather(resort)
      if (data) data.source = 'open-meteo-fallback'
    }

    return data
  } catch (error) {
    console.error(`fetchResortWeather error for ${resort.name}:`, error)
    // Last resort fallback
    try {
      const fallbackData = await fetchOpenMeteoWeather(resort)
      if (fallbackData) fallbackData.source = 'open-meteo-fallback'
      return fallbackData
    } catch (e) {
      return null
    }
  }
}

/**
 * Fetch weather for ALL resorts using met.no (yr.no)
 * Uses met.no as primary source for all regions
 * Falls back to Open-Meteo if met.no fails
 */
export async function fetchAllResortsWeatherHybrid(resorts) {
  const weatherData = {}

  console.log(`Fetching weather for ${resorts.length} resorts using met.no (yr.no)`)

  // Fetch all resorts with met.no
  // Small delay between requests to be respectful to the API
  const DELAY_MS = 150

  for (const resort of resorts) {
    try {
      let data = await fetchMetNoForResort(resort)

      if (!data) {
        console.log(`Met.no failed for ${resort.name}, using Open-Meteo fallback`)
        data = await fetchOpenMeteoWeather(resort)
        if (data) data.source = 'open-meteo-fallback'
      }

      if (data) weatherData[resort.id] = data
      await delay(DELAY_MS)
    } catch (e) {
      console.error(`Weather fetch failed for ${resort.name}:`, e.message)
      // Try Open-Meteo fallback
      try {
        const fallback = await fetchOpenMeteoWeather(resort)
        if (fallback) {
          fallback.source = 'open-meteo-fallback'
          weatherData[resort.id] = fallback
        }
      } catch (e2) {
        console.error(`Fallback also failed for ${resort.name}`)
      }
    }
  }

  const metNoCount = Object.values(weatherData).filter(d => d.source === 'met-no').length
  const fallbackCount = Object.values(weatherData).filter(d => d.source === 'open-meteo-fallback').length
  console.log(`Weather fetch complete: ${metNoCount} met.no, ${fallbackCount} fallback, ${resorts.length - Object.keys(weatherData).length} failed`)

  return weatherData
}

/**
 * Get weather source stats for debugging
 */
export function getSourceStats(weatherData) {
  const stats = {
    'met-no': 0,
    'open-meteo-fallback': 0,
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

// Export as default for drop-in replacement
export default {
  fetchResortWeather,
  fetchAllResortsWeatherHybrid,
  fetchAllResortsWeather: fetchAllResortsWeatherHybrid, // Alias for compatibility
  getWeatherSource,
  getSourceStats
}
