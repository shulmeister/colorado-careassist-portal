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
import { fetchMeteoblueWeather } from './meteoblueApi.js'
import { fetchMetNoForResort } from './metNoApi.js'

// Delay helper
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Determine the best weather source for a resort
 */
export function getWeatherSource(resort) {
  if (isUSResort(resort)) {
    // NWS API has issues from browser - use Open-Meteo ECMWF for now
    // Open-Meteo with elevation parameter is still very accurate for US mountains
    return 'open-meteo'
  }
  if (resort.region === 'canada') {
    // TODO: Environment Canada API
    return 'open-meteo'  // Fallback for now
  }
  if (resort.region === 'japan') {
    return 'meteoblue'  // Meteoblue has snowfraction data - accurate for Niseko
  }
  if (resort.region === 'europe') {
    return 'met-no'  // Norwegian Met Institute - excellent for Europe
  }
  // Others (fallback)
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

      case 'meteoblue':
        data = await fetchMeteoblueWeather(resort)
        // If Meteoblue fails, fall back to Open-Meteo
        if (!data) {
          console.log(`Meteoblue failed for ${resort.name}, falling back to Open-Meteo`)
          data = await fetchOpenMeteoWeather(resort)
          if (data) data.source = 'open-meteo-fallback'
        }
        break

      case 'met-no':
        data = await fetchMetNoForResort(resort)
        // If met.no fails, fall back to Open-Meteo
        if (!data) {
          console.log(`Met.no failed for ${resort.name}, falling back to Open-Meteo`)
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
  // US now uses Open-Meteo ECMWF (NWS has browser issues)
  const japanResorts = resorts.filter(r => r.region === 'japan')
  const europeResorts = resorts.filter(r => r.region === 'europe')
  const openMeteoResorts = resorts.filter(r => r.region !== 'japan' && r.region !== 'europe')

  console.log(`Hybrid fetch: ${openMeteoResorts.length} US/Canada (Open-Meteo ECMWF), ${japanResorts.length} Japan (Meteoblue), ${europeResorts.length} Europe (met.no)`)

  // Fetch Japan resorts with Meteoblue (has snowfraction data)
  if (japanResorts.length > 0) {
    for (const resort of japanResorts) {
      try {
        let data = await fetchMeteoblueWeather(resort)
        if (!data) {
          console.log(`Meteoblue failed for ${resort.name}, using Open-Meteo fallback`)
          data = await fetchOpenMeteoWeather(resort)
          if (data) data.source = 'open-meteo-fallback'
        }
        if (data) weatherData[resort.id] = data
      } catch (e) {
        console.error(`Japan fetch failed for ${resort.name}`)
      }
    }
  }

  // Fetch Europe resorts with met.no
  if (europeResorts.length > 0) {
    for (const resort of europeResorts) {
      try {
        let data = await fetchMetNoForResort(resort)
        if (!data) {
          console.log(`Met.no failed for ${resort.name}, using Open-Meteo fallback`)
          data = await fetchOpenMeteoWeather(resort)
          if (data) data.source = 'open-meteo-fallback'
        }
        if (data) weatherData[resort.id] = data
        await delay(200) // Small delay to be nice to met.no
      } catch (e) {
        console.error(`Europe fetch failed for ${resort.name}`)
      }
    }
  }

  // Fetch US/Canada resorts with Open-Meteo ECMWF
  if (openMeteoResorts.length > 0) {
    const BATCH_SIZE = 6
    const BATCH_DELAY = 300

    for (let i = 0; i < openMeteoResorts.length; i += BATCH_SIZE) {
      const batch = openMeteoResorts.slice(i, i + BATCH_SIZE)
      const promises = batch.map(resort => fetchOpenMeteoWeather(resort))
      const results = await Promise.allSettled(promises)

      results.forEach((result, index) => {
        if (result.status === 'fulfilled' && result.value) {
          weatherData[batch[index].id] = result.value
        }
      })

      if (i + BATCH_SIZE < openMeteoResorts.length) {
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
