/**
 * NWS (National Weather Service) API - US Resorts
 *
 * Free public API, no key required
 * More accurate for US locations than global models
 *
 * API Flow:
 * 1. GET /points/{lat},{lon} → returns forecast office + grid coordinates
 * 2. GET /gridpoints/{office}/{gridX},{gridY}/forecast → 7-day forecast
 * 3. GET /gridpoints/{office}/{gridX},{gridY} → detailed quantitative data
 */

const NWS_BASE = 'https://api.weather.gov'
const USER_AGENT = 'PowderPulse/1.0 (contact@coloradocareassist.com)'

// Delay helper
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

// Cache for grid point lookups (lat,lng -> gridpoint data)
const gridPointCache = new Map()

/**
 * Get NWS grid point data for coordinates
 * This maps lat/lng to the NWS forecast grid
 */
async function getGridPoint(lat, lng) {
  const cacheKey = `${lat.toFixed(4)},${lng.toFixed(4)}`

  if (gridPointCache.has(cacheKey)) {
    return gridPointCache.get(cacheKey)
  }

  try {
    const response = await fetch(`${NWS_BASE}/points/${lat},${lng}`, {
      headers: {
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json'
      }
    })

    if (!response.ok) {
      console.error(`NWS points error: ${response.status} for ${lat},${lng}`)
      return null
    }

    const data = await response.json()
    const gridData = {
      office: data.properties.gridId,
      gridX: data.properties.gridX,
      gridY: data.properties.gridY,
      forecastUrl: data.properties.forecast,
      forecastHourlyUrl: data.properties.forecastHourly,
      forecastGridDataUrl: data.properties.forecastGridData,
      timezone: data.properties.timeZone
    }

    gridPointCache.set(cacheKey, gridData)
    return gridData
  } catch (error) {
    console.error(`NWS getGridPoint error for ${lat},${lng}:`, error)
    return null
  }
}

/**
 * Fetch quantitative forecast data from NWS gridpoints endpoint
 * This gives us actual snowfall amounts, temperatures, etc.
 */
async function fetchGridData(gridPoint) {
  try {
    const response = await fetch(gridPoint.forecastGridDataUrl, {
      headers: {
        'User-Agent': USER_AGENT,
        'Accept': 'application/geo+json'
      }
    })

    if (!response.ok) {
      console.error(`NWS gridData error: ${response.status}`)
      return null
    }

    return await response.json()
  } catch (error) {
    console.error('NWS fetchGridData error:', error)
    return null
  }
}

/**
 * Parse NWS time-value pairs into daily aggregates
 * NWS returns data in ISO 8601 duration format
 */
function parseNWSTimeSeries(values, aggregateFunc = 'sum') {
  if (!values || !values.length) return []

  const dailyData = {}

  for (const item of values) {
    // Parse ISO 8601 interval: "2024-01-15T06:00:00+00:00/PT6H"
    const dateStr = item.validTime.split('T')[0]
    const value = item.value

    if (value === null || value === undefined) continue

    if (!dailyData[dateStr]) {
      dailyData[dateStr] = { values: [], date: dateStr }
    }
    dailyData[dateStr].values.push(value)
  }

  // Aggregate values per day
  return Object.values(dailyData).map(day => {
    let aggregated
    switch (aggregateFunc) {
      case 'sum':
        aggregated = day.values.reduce((a, b) => a + b, 0)
        break
      case 'max':
        aggregated = Math.max(...day.values)
        break
      case 'min':
        aggregated = Math.min(...day.values)
        break
      case 'avg':
        aggregated = day.values.reduce((a, b) => a + b, 0) / day.values.length
        break
      default:
        aggregated = day.values[0]
    }
    return { date: day.date, value: aggregated }
  }).sort((a, b) => a.date.localeCompare(b.date))
}

/**
 * Convert Celsius to Fahrenheit
 */
function celsiusToFahrenheit(c) {
  if (c === null || c === undefined) return null
  return Math.round((c * 9/5) + 32)
}

/**
 * Convert mm to inches
 */
function mmToInches(mm) {
  if (mm === null || mm === undefined) return 0
  return Math.round((mm / 25.4) * 10) / 10
}

/**
 * Convert km/h to mph
 */
function kmhToMph(kmh) {
  if (kmh === null || kmh === undefined) return 0
  return Math.round(kmh * 0.621371)
}

/**
 * Fetch weather for a single US resort using NWS API
 */
export async function fetchNWSWeather(resort) {
  const lat = resort.latitude
  const lng = resort.longitude

  // Step 1: Get grid point
  const gridPoint = await getGridPoint(lat, lng)
  if (!gridPoint) {
    console.warn(`NWS: Could not get grid point for ${resort.name}, falling back`)
    return null
  }

  // Small delay to be nice to NWS API
  await delay(100)

  // Step 2: Get quantitative grid data
  const gridData = await fetchGridData(gridPoint)
  if (!gridData) {
    console.warn(`NWS: Could not get grid data for ${resort.name}`)
    return null
  }

  const props = gridData.properties

  // Parse snowfall (NWS gives mm, convert to inches)
  const snowfallRaw = parseNWSTimeSeries(props.snowfallAmount, 'sum')
  const snowfall = snowfallRaw.map(d => ({
    date: d.date,
    snowfall: mmToInches(d.value)
  }))

  // Parse temperatures (NWS gives Celsius)
  const tempMax = parseNWSTimeSeries(props.maxTemperature, 'max')
  const tempMin = parseNWSTimeSeries(props.minTemperature, 'min')

  // Parse wind
  const windSpeed = parseNWSTimeSeries(props.windSpeed, 'max')
  const windGust = parseNWSTimeSeries(props.windGust, 'max')

  // Parse precipitation probability
  const precipProb = parseNWSTimeSeries(props.probabilityOfPrecipitation, 'max')

  // Build daily forecast (NWS typically provides 7 days)
  const dailyForecast = []
  const today = new Date().toISOString().split('T')[0]

  for (let i = 0; i < Math.min(snowfall.length, 7); i++) {
    const date = snowfall[i]?.date
    if (!date) continue

    const maxT = tempMax.find(t => t.date === date)
    const minT = tempMin.find(t => t.date === date)
    const wind = windSpeed.find(w => w.date === date)
    const gust = windGust.find(g => g.date === date)
    const prob = precipProb.find(p => p.date === date)

    dailyForecast.push({
      date,
      tempMax: celsiusToFahrenheit(maxT?.value),
      tempMin: celsiusToFahrenheit(minT?.value),
      snowfall: snowfall[i]?.snowfall || 0,
      windSpeed: kmhToMph(wind?.value) || 0,
      windGusts: kmhToMph(gust?.value) || 0,
      precipProbability: prob?.value || 0,
      source: 'nws'
    })
  }

  // Calculate snow totals
  const snow24h = dailyForecast[0]?.snowfall || 0
  const snow48h = dailyForecast.slice(0, 2).reduce((sum, d) => sum + d.snowfall, 0)
  const snow5Day = dailyForecast.slice(0, 5).reduce((sum, d) => sum + d.snowfall, 0)
  const snow7Day = dailyForecast.slice(0, 7).reduce((sum, d) => sum + d.snowfall, 0)

  // Powder alert: 6"+ in next 48 hours
  const isPowderDay = snow48h >= 6

  // Current conditions (use first available data point)
  const currentTemp = tempMax[0]?.value !== undefined
    ? celsiusToFahrenheit((tempMax[0].value + (tempMin[0]?.value || tempMax[0].value)) / 2)
    : null
  const currentWind = windSpeed[0]?.value ? kmhToMph(windSpeed[0].value) : 0

  return {
    resortId: resort.id,
    source: 'nws',
    lastUpdated: new Date().toISOString(),
    coordinates: { lat, lng },
    gridPoint: {
      office: gridPoint.office,
      gridX: gridPoint.gridX,
      gridY: gridPoint.gridY
    },
    current: {
      temp: currentTemp,
      windSpeed: currentWind,
      windGusts: windGust[0]?.value ? kmhToMph(windGust[0].value) : 0
    },
    snow24h: Math.round(snow24h * 10) / 10,
    snow48h: Math.round(snow48h * 10) / 10,
    snow5Day: Math.round(snow5Day * 10) / 10,
    snow7Day: Math.round(snow7Day * 10) / 10,
    isPowderDay,
    dailyForecast,
    // For sparkline charts
    sparklineData: dailyForecast.slice(0, 7).map(d => ({
      day: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' }),
      date: d.date,
      snow: Math.round(d.snowfall * 10) / 10
    }))
  }
}

/**
 * Fetch weather for all US resorts using NWS API
 * Uses batching to respect rate limits
 */
export async function fetchAllUSResortsWeather(resorts) {
  const weatherData = {}
  const BATCH_SIZE = 4  // NWS is more sensitive to rate limits
  const BATCH_DELAY = 1000  // 1 second between batches

  for (let i = 0; i < resorts.length; i += BATCH_SIZE) {
    const batch = resorts.slice(i, i + BATCH_SIZE)
    const promises = batch.map(resort => fetchNWSWeather(resort))
    const results = await Promise.allSettled(promises)

    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value) {
        weatherData[batch[index].id] = result.value
      } else {
        console.warn(`NWS fetch failed for ${batch[index].name}:`, result.reason || 'null result')
      }
    })

    // Delay between batches
    if (i + BATCH_SIZE < resorts.length) {
      await delay(BATCH_DELAY)
    }
  }

  return weatherData
}

/**
 * Check if a resort is in the US (for routing)
 */
export function isUSResort(resort) {
  const usRegions = [
    'colorado', 'new-mexico', 'utah', 'california',
    'idaho', 'wyoming', 'montana', 'alaska', 'maine', 'vermont'
  ]
  return usRegions.includes(resort.region)
}

export default {
  fetchNWSWeather,
  fetchAllUSResortsWeather,
  isUSResort
}
