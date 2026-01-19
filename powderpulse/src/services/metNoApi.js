/**
 * Met.no (Norwegian Meteorological Institute) API - Europe
 *
 * Free, no API key required
 * Excellent accuracy for European locations
 * https://api.met.no/weatherapi/locationforecast/2.0/documentation
 *
 * Requirements:
 * - Must identify your application in User-Agent (but browsers set their own)
 * - Must use HTTPS
 * - Should respect caching headers
 */

const BASE_URL = 'https://api.met.no/weatherapi/locationforecast/2.0'

/**
 * Fetch forecast from met.no
 * Returns complete forecast data
 */
export async function fetchMetNoForecast(lat, lng, altitude = null) {
  try {
    let url = `${BASE_URL}/complete?lat=${lat}&lon=${lng}`
    if (altitude) {
      url += `&altitude=${altitude}`
    }

    const response = await fetch(url, {
      headers: {
        'Accept': 'application/json'
      }
    })

    if (!response.ok) {
      console.error(`Met.no error: ${response.status}`)
      return null
    }

    return await response.json()
  } catch (error) {
    console.error('Met.no fetch error:', error)
    return null
  }
}

/**
 * Parse met.no timeseries into daily forecast
 */
function aggregateToDays(timeseries) {
  const days = {}

  for (const entry of timeseries) {
    const date = entry.time.split('T')[0]
    const data = entry.data

    if (!days[date]) {
      days[date] = {
        date,
        temps: [],
        snowfall: 0,
        precipitation: 0,
        windSpeeds: [],
        windGusts: []
      }
    }

    // Temperature
    if (data.instant?.details?.air_temperature !== undefined) {
      days[date].temps.push(data.instant.details.air_temperature)
    }

    // Wind
    if (data.instant?.details?.wind_speed !== undefined) {
      days[date].windSpeeds.push(data.instant.details.wind_speed)
    }
    if (data.instant?.details?.wind_speed_of_gust !== undefined) {
      days[date].windGusts.push(data.instant.details.wind_speed_of_gust)
    }

    // Precipitation (next 1 or 6 hours)
    const precip1h = data.next_1_hours?.details?.precipitation_amount || 0
    const precip6h = data.next_6_hours?.details?.precipitation_amount || 0
    days[date].precipitation += precip1h || (precip6h / 6) // Approximate if only 6h available
  }

  return days
}

/**
 * Estimate snowfall from precipitation and temperature
 * met.no doesn't always provide snowfall directly
 */
function estimateSnowfall(precipMm, tempC) {
  if (tempC > 2) return 0  // Rain
  if (tempC > 0) return precipMm * 0.5 / 25.4  // Mixed, convert mm to inches
  // Snow: typical ratio is 10:1 to 15:1 (snow:water) depending on temp
  const ratio = tempC < -10 ? 15 : 10
  return (precipMm * ratio) / 25.4  // Convert mm to inches of snow
}

/**
 * Fetch weather for a European resort using met.no
 * Converts to our standard format
 */
export async function fetchMetNoForResort(resort) {
  const lat = resort.latitude
  const lng = resort.longitude
  // Convert elevation from feet to meters
  const altitude = resort.elevation ? Math.round(resort.elevation * 0.3048) : null

  try {
    const data = await fetchMetNoForecast(lat, lng, altitude)
    if (!data || !data.properties?.timeseries) {
      return null
    }

    const timeseries = data.properties.timeseries
    const dayData = aggregateToDays(timeseries)
    const sortedDays = Object.values(dayData).sort((a, b) => a.date.localeCompare(b.date))

    // Build daily forecast (convert C to F, m/s to mph)
    const dailyForecast = sortedDays.slice(0, 10).map(day => {
      const avgTemp = day.temps.length > 0
        ? day.temps.reduce((a, b) => a + b, 0) / day.temps.length
        : 0

      const snowfall = estimateSnowfall(day.precipitation, avgTemp)

      return {
        date: day.date,
        tempMax: day.temps.length > 0 ? Math.round(Math.max(...day.temps) * 9/5 + 32) : null,
        tempMin: day.temps.length > 0 ? Math.round(Math.min(...day.temps) * 9/5 + 32) : null,
        snowfall: Math.round(snowfall * 10) / 10,
        precipitation: Math.round(day.precipitation / 25.4 * 10) / 10, // mm to inches
        windSpeed: day.windSpeeds.length > 0
          ? Math.round(Math.max(...day.windSpeeds) * 2.237)  // m/s to mph
          : 0,
        windGusts: day.windGusts.length > 0
          ? Math.round(Math.max(...day.windGusts) * 2.237)
          : 0,
        source: 'met-no'
      }
    })

    // Calculate snow totals
    const snow24h = dailyForecast[0]?.snowfall || 0
    const snow48h = dailyForecast.slice(0, 2).reduce((sum, d) => sum + (d.snowfall || 0), 0)
    const snow5Day = dailyForecast.slice(0, 5).reduce((sum, d) => sum + (d.snowfall || 0), 0)
    const snow7Day = dailyForecast.slice(0, 7).reduce((sum, d) => sum + (d.snowfall || 0), 0)

    // Powder alert
    const isPowderDay = snow48h >= 6

    // Current conditions from first timeseries entry
    const current = timeseries[0]?.data?.instant?.details
    const currentData = current ? {
      temp: Math.round(current.air_temperature * 9/5 + 32),
      windSpeed: Math.round((current.wind_speed || 0) * 2.237),
      windGusts: Math.round((current.wind_speed_of_gust || 0) * 2.237),
      humidity: current.relative_humidity || 0,
      cloudCover: current.cloud_area_fraction || 0
    } : null

    return {
      resortId: resort.id,
      source: 'met-no',
      lastUpdated: new Date().toISOString(),
      coordinates: { lat, lng },
      altitude,
      current: currentData,
      snow24h: Math.round(snow24h * 10) / 10,
      snow48h: Math.round(snow48h * 10) / 10,
      snow5Day: Math.round(snow5Day * 10) / 10,
      snow7Day: Math.round(snow7Day * 10) / 10,
      isPowderDay,
      dailyForecast,
      sparklineData: dailyForecast.slice(0, 7).map(d => ({
        day: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' }),
        date: d.date,
        snow: d.snowfall || 0
      }))
    }
  } catch (error) {
    console.error(`Met.no error for ${resort.name}:`, error)
    return null
  }
}

export default {
  fetchMetNoForecast,
  fetchMetNoForResort
}
