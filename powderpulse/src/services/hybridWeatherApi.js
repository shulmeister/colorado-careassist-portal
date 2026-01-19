/**
 * Hybrid Weather API - Routes to best source per region
 *
 * Strategy:
 * - US Resorts (30): NWS API (most accurate for US, free)
 * - Canada (3): Environment Canada API (TODO) → fallback to Open-Meteo
 * - Japan (1): JMA API (TODO) → fallback to Open-Meteo
 * - Europe (6): Open-Meteo with ECMWF (gold standard for EU)
 *
 * Benefits:
 * - NWS is significantly more accurate for mountain weather in the US
 * - ECMWF is the best global model, especially for Europe
 * - Free APIs with generous rate limits
 */

import { fetchNWSWeather, fetchAllUSResortsWeather, isUSResort } from './nwsApi.js'
import { fetchOpenMeteoWeather } from './ensembleWeatherApi.js'

// Delay helper
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Determine the best weather source for a resort
 */
export function getWeatherSource(resort) {
  if (isUSResort(resort)) {
    return 'nws'
  }
  if (resort.region === 'canada') {
    // TODO: Environment Canada API
    return 'open-meteo'  // Fallback for now
  }
  if (resort.region === 'japan') {
    // TODO: JMA API
    return 'open-meteo'  // Fallback for now
  }
  // Europe and others
  return 'open-meteo'
}

/**
 * Fetch weather for a single resort using the best source
 */
export async function fetchResortWeather(resort) {
  const source = getWeatherSource(resort)

  try {
    let data

    switch (source) {
      case 'nws':
        data = await fetchNWSWeather(resort)
        // If NWS fails, fall back to Open-Meteo
        if (!data) {
          console.log(`NWS failed for ${resort.name}, falling back to Open-Meteo`)
          data = await fetchOpenMeteoWeather(resort)
          if (data) data.source = 'open-meteo-fallback'
        }
        break

      case 'open-meteo':
      default:
        data = await fetchOpenMeteoWeather(resort)
        break
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
 * Fetch weather for ALL resorts using hybrid routing
 * Groups resorts by source for efficient batch fetching
 */
export async function fetchAllResortsWeatherHybrid(resorts) {
  const weatherData = {}

  // Group resorts by source
  const usResorts = resorts.filter(r => isUSResort(r))
  const otherResorts = resorts.filter(r => !isUSResort(r))

  console.log(`Hybrid fetch: ${usResorts.length} US resorts (NWS), ${otherResorts.length} other resorts (Open-Meteo)`)

  // Fetch US resorts with NWS (with fallback)
  if (usResorts.length > 0) {
    const nwsResults = await fetchAllUSResortsWeather(usResorts)

    // Check for failures and retry with Open-Meteo
    const failedResorts = usResorts.filter(r => !nwsResults[r.id])

    if (failedResorts.length > 0) {
      console.log(`NWS failed for ${failedResorts.length} resorts, using Open-Meteo fallback`)
      for (const resort of failedResorts) {
        try {
          const fallbackData = await fetchOpenMeteoWeather(resort)
          if (fallbackData) {
            fallbackData.source = 'open-meteo-fallback'
            nwsResults[resort.id] = fallbackData
          }
          await delay(200) // Small delay for Open-Meteo
        } catch (e) {
          console.error(`Fallback failed for ${resort.name}`)
        }
      }
    }

    Object.assign(weatherData, nwsResults)
  }

  // Fetch other resorts with Open-Meteo
  if (otherResorts.length > 0) {
    const BATCH_SIZE = 6
    const BATCH_DELAY = 500

    for (let i = 0; i < otherResorts.length; i += BATCH_SIZE) {
      const batch = otherResorts.slice(i, i + BATCH_SIZE)
      const promises = batch.map(resort => fetchOpenMeteoWeather(resort))
      const results = await Promise.allSettled(promises)

      results.forEach((result, index) => {
        if (result.status === 'fulfilled' && result.value) {
          weatherData[batch[index].id] = result.value
        }
      })

      if (i + BATCH_SIZE < otherResorts.length) {
        await delay(BATCH_DELAY)
      }
    }
  }

  return weatherData
}

/**
 * Get weather source stats for debugging
 */
export function getSourceStats(weatherData) {
  const stats = {
    nws: 0,
    'open-meteo-ecmwf': 0,
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
