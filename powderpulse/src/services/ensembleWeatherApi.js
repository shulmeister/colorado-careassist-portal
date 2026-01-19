/**
 * Weather API - Open-Meteo Regional Endpoints for Ski Forecasting
 *
 * Strategy:
 * - Use dedicated regional endpoints for accuracy:
 *   - /v1/jma for Japan (JMA model - 11 days)
 *   - /v1/gem for Canada (GEM model - 16 days)
 *   - /v1/gfs for US (GFS/HRRR model - 16 days)
 *   - /v1/ecmwf for Europe (ECMWF model - 15 days)
 * - Summit elevation parameter for accurate mountain weather
 * - 10:1 precipitation-to-snow conversion when temp is below freezing
 *
 * Key ski parameters:
 * - snowfall, precipitation, freezing_level_height
 * - temperature_2m, wind_speed_10m, wind_gusts_10m
 */

import { REGIONS } from '../data/resorts'

// API Keys (only used for augmented detail data)
const TOMORROW_API_KEY = 'qyqlOXozeogt1fPFw6FIATxY5D1qOXqJ'
const RAPIDAPI_KEY = 'ce3b334075msh80fc4f61ed53886p1d70d8jsn943da04fc000'

// Regional Open-Meteo endpoints
const OPEN_METEO_ENDPOINTS = {
  jma: 'https://api.open-meteo.com/v1/jma',      // Japan - 11 days
  gem: 'https://api.open-meteo.com/v1/gem',      // Canada - 16 days
  gfs: 'https://api.open-meteo.com/v1/gfs',      // US - 16 days
  ecmwf: 'https://api.open-meteo.com/v1/ecmwf'   // Europe - 15 days
}

// Open-Meteo utility APIs
const OPEN_METEO_ELEVATION = 'https://api.open-meteo.com/v1/elevation'
const OPEN_METEO_GEOCODING = 'https://geocoding-api.open-meteo.com/v1/search'

// Cache for elevation lookups (avoid repeated API calls)
const elevationCache = new Map()

/**
 * Get elevation at coordinates using Open-Meteo Elevation API
 * 90-meter resolution Copernicus DEM
 *
 * @param {number} lat - Latitude
 * @param {number} lng - Longitude
 * @returns {number|null} Elevation in meters
 */
async function getElevationAtCoords(lat, lng) {
  const cacheKey = `${lat},${lng}`
  if (elevationCache.has(cacheKey)) {
    return elevationCache.get(cacheKey)
  }

  try {
    const response = await fetch(`${OPEN_METEO_ELEVATION}?latitude=${lat}&longitude=${lng}`)
    if (!response.ok) return null

    const data = await response.json()
    const elevation = data.elevation?.[0]
    if (elevation != null) {
      elevationCache.set(cacheKey, elevation)
      return elevation
    }
    return null
  } catch (error) {
    console.error('Elevation API error:', error)
    return null
  }
}

/**
 * Search for a location using Open-Meteo Geocoding API
 * Returns coordinates and elevation
 *
 * @param {string} name - Location name to search
 * @returns {Object|null} { latitude, longitude, elevation, name }
 */
async function searchLocation(name) {
  try {
    const response = await fetch(`${OPEN_METEO_GEOCODING}?name=${encodeURIComponent(name)}&count=1`)
    if (!response.ok) return null

    const data = await response.json()
    const result = data.results?.[0]
    if (result) {
      return {
        latitude: result.latitude,
        longitude: result.longitude,
        elevation: result.elevation,
        name: result.name,
        country: result.country
      }
    }
    return null
  } catch (error) {
    console.error('Geocoding API error:', error)
    return null
  }
}

// Map regions to endpoints
function getEndpointForRegion(region) {
  switch (region) {
    case REGIONS.JAPAN:
      return { endpoint: OPEN_METEO_ENDPOINTS.jma, maxDays: 11 }
    case REGIONS.CANADA:
      return { endpoint: OPEN_METEO_ENDPOINTS.gem, maxDays: 16 }
    case REGIONS.EUROPE:
      return { endpoint: OPEN_METEO_ENDPOINTS.ecmwf, maxDays: 15 }
    // All US regions use GFS
    case REGIONS.COLORADO:
    case REGIONS.NEW_MEXICO:
    case REGIONS.UTAH:
    case REGIONS.CALIFORNIA:
    case REGIONS.IDAHO:
    case REGIONS.WYOMING:
    case REGIONS.MONTANA:
    case REGIONS.ALASKA:
    case REGIONS.MAINE:
    case REGIONS.VERMONT:
    default:
      return { endpoint: OPEN_METEO_ENDPOINTS.gfs, maxDays: 16 }
  }
}

// Delay helper for rate limiting
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Get timezone for a resort region
 */
function getTimezone(resort) {
  return resort.timezone || 'auto'
}

/**
 * Convert precipitation to snow using 10:1 ratio
 * Standard meteorological conversion: 10mm water = ~1 inch snow (or 25.4mm = 1 inch)
 * In centimeters: 1cm precip = 10cm snow
 *
 * @param {number} precipInches - Precipitation in inches
 * @param {number} tempF - Temperature in Fahrenheit
 * @returns {number} - Snow in inches
 */
function precipToSnow(precipInches, tempF) {
  // Only convert if temperature is below freezing (32°F)
  // And if there's actual precipitation
  if (precipInches > 0 && tempF <= 32) {
    return precipInches * 10  // 10:1 ratio
  }
  return 0
}

/**
 * REGIONAL SKI FORECAST: Fetch from Open-Meteo using dedicated regional endpoints
 * Uses summit coordinates + elevation for accurate mountain weather
 *
 * @param {Object} resort - Resort object with summit coordinates
 * @returns {Object} Weather data with daily and hourly forecasts
 */
export async function fetchOpenMeteoWeather(resort) {
  // Use summit coordinates (main lat/lng in resort data)
  const lat = resort.latitude
  const lng = resort.longitude

  // Get elevation in meters for accurate mountain weather
  // Priority: 1) Resort's hardcoded summit elevation (converted from feet)
  //           2) Elevation API lookup at coordinates (90m DEM)
  let elevationMeters = null
  if (resort.elevation) {
    // Convert summit elevation from feet to meters
    elevationMeters = Math.round(resort.elevation * 0.3048)
  } else {
    // Fallback: fetch from Elevation API
    const apiElevation = await getElevationAtCoords(lat, lng)
    if (apiElevation != null) {
      elevationMeters = Math.round(apiElevation)
      console.log(`${resort.name}: Using API elevation ${elevationMeters}m`)
    }
  }

  // Get the appropriate regional endpoint
  const { endpoint, maxDays } = getEndpointForRegion(resort.region)

  const params = new URLSearchParams({
    latitude: lat,
    longitude: lng,
    // Pass actual summit elevation for accurate mountain weather
    ...(elevationMeters && { elevation: elevationMeters }),
    // Daily aggregates - ski-optimized
    daily: [
      'snowfall_sum',
      'precipitation_sum',
      'precipitation_probability_max',
      'wind_speed_10m_max',
      'wind_gusts_10m_max',
      'temperature_2m_max',
      'temperature_2m_min',
      'weather_code'
    ].join(','),
    // Hourly details - ski-critical parameters
    hourly: [
      'snowfall',              // Hourly snowfall in cm (converted to inches)
      'snow_depth',            // Total snow depth on ground
      'freezing_level_height', // Critical: snow vs rain threshold
      'precipitation',
      'precipitation_probability',
      'temperature_2m',
      'apparent_temperature',
      'wind_speed_10m',
      'wind_gusts_10m',
      'cloud_cover',
      'visibility'
    ].join(','),
    // Current conditions
    current: [
      'temperature_2m',
      'wind_speed_10m',
      'wind_gusts_10m',
      'snowfall',
      'precipitation',
      'is_day',
      'cloud_cover',
      'weather_code'
    ].join(','),
    timezone: getTimezone(resort),
    forecast_days: maxDays,   // Use max days for this endpoint
    temperature_unit: 'fahrenheit',
    windspeed_unit: 'mph',
    precipitation_unit: 'inch'
  })

  try {
    const response = await fetch(`${endpoint}?${params}`)
    if (!response.ok) {
      console.error(`Open-Meteo ${resort.region} error for ${resort.name}: ${response.status}`)
      return null
    }

    const data = await response.json()

    // Process daily forecast
    const dailyForecast = data.daily.time.map((date, i) => {
      const snowfall = data.daily.snowfall_sum[i] || 0
      const precipitation = data.daily.precipitation_sum[i] || 0
      const tempMax = Math.round(data.daily.temperature_2m_max[i])
      const tempMin = Math.round(data.daily.temperature_2m_min[i])
      const avgTemp = (tempMax + tempMin) / 2

      // If snowfall is reported as 0 but there's precipitation and it's cold,
      // use the 10:1 ratio to estimate snow
      let finalSnowfall = snowfall
      if (snowfall < 0.1 && precipitation > 0 && avgTemp <= 32) {
        const estimatedSnow = precipToSnow(precipitation, avgTemp)
        if (estimatedSnow > snowfall) {
          finalSnowfall = estimatedSnow
          console.log(`${resort.name} ${date}: Using 10:1 conversion - ${precipitation.toFixed(2)}" precip @ ${avgTemp}°F = ${estimatedSnow.toFixed(1)}" snow`)
        }
      }

      return {
        date,
        tempMax,
        tempMin,
        snowfall: finalSnowfall,
        precipitation,
        precipProbability: data.daily.precipitation_probability_max[i] || 0,
        windSpeed: Math.round(data.daily.wind_speed_10m_max[i] || 0),
        windGusts: Math.round(data.daily.wind_gusts_10m_max[i] || 0),
        weatherCode: data.daily.weather_code[i],
        source: `open-meteo-${resort.region}`
      }
    })

    // Calculate snow totals
    const snow24h = dailyForecast[0]?.snowfall || 0
    const snow48h = dailyForecast.slice(0, 2).reduce((sum, d) => sum + d.snowfall, 0)
    const snow5Day = dailyForecast.slice(0, 5).reduce((sum, d) => sum + d.snowfall, 0)
    const snow7Day = dailyForecast.slice(0, 7).reduce((sum, d) => sum + d.snowfall, 0)
    const snow10Day = dailyForecast.slice(0, 10).reduce((sum, d) => sum + d.snowfall, 0)
    const snow15Day = dailyForecast.slice(0, 15).reduce((sum, d) => sum + d.snowfall, 0)

    // Find biggest snow day in forecast
    const biggestDay = dailyForecast.reduce((max, day) =>
      day.snowfall > max.snowfall ? day : max, dailyForecast[0] || { snowfall: 0, date: null })

    // Powder alert: 6"+ in next 48 hours
    const isPowderDay = snow48h >= 6

    // Current conditions
    const current = data.current ? {
      temp: Math.round(data.current.temperature_2m),
      windSpeed: Math.round(data.current.wind_speed_10m),
      windGusts: Math.round(data.current.wind_gusts_10m || 0),
      snowfall: data.current.snowfall || 0,
      precipitation: data.current.precipitation || 0,
      cloudCover: data.current.cloud_cover,
      isDay: data.current.is_day === 1,
      weatherCode: data.current.weather_code
    } : null

    // Process hourly data (for charts) - ski-critical parameters
    const hourlyForecast = data.hourly.time.map((time, i) => ({
      time,
      temp: Math.round(data.hourly.temperature_2m[i]),
      snowfall: data.hourly.snowfall[i] || 0,
      snowDepth: data.hourly.snow_depth?.[i] || 0,
      precipitation: data.hourly.precipitation[i] || 0,
      precipProbability: data.hourly.precipitation_probability[i] || 0,
      freezingLevel: data.hourly.freezing_level_height?.[i],  // Key for snow vs rain
      feelsLike: Math.round(data.hourly.apparent_temperature[i]),
      cloudCover: data.hourly.cloud_cover?.[i],
      visibility: data.hourly.visibility?.[i],
      windSpeed: Math.round(data.hourly.wind_speed_10m[i] || 0),
      windGusts: Math.round(data.hourly.wind_gusts_10m[i] || 0)
    }))

    return {
      resortId: resort.id,
      source: `open-meteo-${resort.region}`,
      endpoint: endpoint,
      lastUpdated: new Date().toISOString(),
      coordinates: { lat, lng },
      elevationMeters,
      current,
      // Snow totals
      snow24h: Math.round(snow24h * 10) / 10,
      snow48h: Math.round(snow48h * 10) / 10,
      snow5Day: Math.round(snow5Day * 10) / 10,
      snow7Day: Math.round(snow7Day * 10) / 10,
      snow10Day: Math.round(snow10Day * 10) / 10,
      snow15Day: Math.round(snow15Day * 10) / 10,
      // Forecasts
      dailyForecast,
      hourlyForecast,
      // Alerts
      isPowderDay,
      biggestDay: biggestDay.date ? {
        date: biggestDay.date,
        snowfall: Math.round(biggestDay.snowfall * 10) / 10
      } : null,
      // For sparkline charts
      sparklineData: dailyForecast.slice(0, 15).map(d => ({
        day: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' }),
        date: d.date,
        snow: Math.round(d.snowfall * 10) / 10
      }))
    }
  } catch (error) {
    console.error(`Open-Meteo fetch error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Fetch weather for ALL resorts using regional Open-Meteo endpoints
 * No rate limits - can fetch all resorts simultaneously
 *
 * @param {Array} resorts - Array of resort objects
 * @returns {Object} Map of resortId -> weather data
 */
export async function fetchAllResortsWeather(resorts) {
  const weatherData = {}

  // Open-Meteo is free and unlimited, but let's batch to be nice
  const BATCH_SIZE = 6
  const BATCH_DELAY = 500

  for (let i = 0; i < resorts.length; i += BATCH_SIZE) {
    const batch = resorts.slice(i, i + BATCH_SIZE)
    const promises = batch.map(resort => fetchOpenMeteoWeather(resort))
    const results = await Promise.allSettled(promises)

    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value) {
        weatherData[batch[index].id] = result.value
      }
    })

    // Small delay between batches
    if (i + BATCH_SIZE < resorts.length) {
      await delay(BATCH_DELAY)
    }
  }

  return weatherData
}

// ============================================================================
// AUGMENTED DATA - Only fetched when viewing resort detail
// These APIs have rate limits, so only call when user clicks on a resort
// ============================================================================

/**
 * Snow-forecast.com resort slug mapping
 */
const SNOW_FORECAST_SLUGS = {
  // Colorado
  'vail': 'Vail',
  'beaver-creek': 'Beaver-Creek',
  'breckenridge': 'Breckenridge',
  'keystone': 'Keystone',
  'crested-butte': 'Crested-Butte-Mountain-Resort',
  'telluride': 'Telluride',
  'steamboat': 'Steamboat',
  'aspen-snowmass': 'Snowmass',
  'winter-park': 'Winter-Park-Resort',
  'copper-mountain': 'Copper-Mountain',
  'eldora': 'Eldora-Mountain-Resort',
  'arapahoe-basin': 'Arapahoe-Basin',
  'wolf-creek': 'Wolf-Creek',
  // New Mexico
  'taos': 'Taos-Ski-Valley',
  // Utah
  'snowbird': 'Snowbird',
  'alta': 'Alta',
  // California
  'mammoth': 'Mammoth',
  'kirkwood': 'Kirkwood',
  'palisades-tahoe': 'Squaw-Valley',
  'sugar-bowl': 'Sugar-Bowl',
  // Idaho/Wyoming/Montana
  'jackson-hole': 'Jackson-Hole',
  'big-sky': 'Big-Sky',
  'sun-valley': 'Sun-Valley',
  // Alaska
  'alyeska': 'Alyeska',
  // East Coast
  'sugarloaf': 'Sugarloaf',
  'jay-peak': 'Jay-Peak',
  // Canada
  'whistler': 'Whistler-Blackcomb',
  'revelstoke': 'Revelstoke-Mountain-Resort',
  'kicking-horse': 'Kicking-Horse',
  // Japan
  'niseko': 'Niseko',
  // Europe
  'chamonix': 'Chamonix',
  'verbier': 'Verbier',
  'val-disere': 'Val-d-Isere',
  'st-anton': 'St-Anton',
  'cervinia': 'Cervinia',
  'courmayeur': 'Courmayeur'
}

/**
 * AUGMENTED: Fetch from Tomorrow.io (called only on resort detail view)
 * Great for storm tracking and marine/mountain weather
 */
export async function fetchTomorrowIoDetail(resort) {
  const lat = resort.latitude
  const lng = resort.longitude

  const params = new URLSearchParams({
    location: `${lat},${lng}`,
    apikey: TOMORROW_API_KEY,
    units: 'imperial',
    timesteps: '1d',
    fields: 'temperatureMax,temperatureMin,precipitationIntensityAvg,precipitationProbabilityAvg,snowAccumulation,weatherCodeMax'
  })

  try {
    const response = await fetch(`https://api.tomorrow.io/v4/timelines?${params}`)
    if (!response.ok) {
      if (response.status === 429) {
        console.warn(`Tomorrow.io rate limited for ${resort.name}`)
      }
      return null
    }

    const data = await response.json()
    const intervals = data.data?.timelines?.[0]?.intervals || []

    return {
      source: 'tomorrow.io',
      forecast: intervals.map(interval => ({
        date: interval.startTime.split('T')[0],
        tempMax: Math.round(interval.values.temperatureMax),
        tempMin: Math.round(interval.values.temperatureMin),
        precipIntensity: interval.values.precipitationIntensityAvg || 0,
        precipProbability: interval.values.precipitationProbabilityAvg || 0,
        snowfall: interval.values.snowAccumulation || 0,
        weatherCode: interval.values.weatherCodeMax
      }))
    }
  } catch (error) {
    console.error(`Tomorrow.io error for ${resort.name}:`, error)
    return null
  }
}

/**
 * AUGMENTED: Fetch from Snow-Forecast.com (called only on resort detail view)
 * Ski-specific forecasts with AM/PM/Night breakdowns
 */
export async function fetchSnowForecastDetail(resort) {
  const slug = SNOW_FORECAST_SLUGS[resort.id]
  if (!slug) {
    return null
  }

  try {
    const response = await fetch(`https://ski-resort-forecast.p.rapidapi.com/${slug}/forecast?units=i&el=top`, {
      headers: {
        'x-rapidapi-host': 'ski-resort-forecast.p.rapidapi.com',
        'x-rapidapi-key': RAPIDAPI_KEY
      }
    })

    if (!response.ok) {
      if (response.status === 429) {
        console.warn(`Snow-Forecast rate limited for ${resort.name}`)
      }
      return null
    }

    const data = await response.json()
    const forecast5Day = data.forecast5Day || []

    // Parse the 5-day forecast with AM/PM/Night detail
    const detailedForecast = forecast5Day.map(day => {
      const parseSnow = (str) => parseFloat(str?.replace('in', '') || 0)
      const parseTemp = (str) => parseFloat(str?.replace('°F', '') || 0)

      return {
        dayOfWeek: day.dayOfWeek,
        am: {
          snow: parseSnow(day.am?.snow),
          tempMax: parseTemp(day.am?.maxTemp),
          tempMin: parseTemp(day.am?.minTemp),
          wind: day.am?.wind,
          weather: day.am?.weather
        },
        pm: {
          snow: parseSnow(day.pm?.snow),
          tempMax: parseTemp(day.pm?.maxTemp),
          tempMin: parseTemp(day.pm?.minTemp),
          wind: day.pm?.wind,
          weather: day.pm?.weather
        },
        night: {
          snow: parseSnow(day.night?.snow),
          tempMax: parseTemp(day.night?.maxTemp),
          tempMin: parseTemp(day.night?.minTemp),
          wind: day.night?.wind,
          weather: day.night?.weather
        },
        totalSnow: parseSnow(day.am?.snow) + parseSnow(day.pm?.snow) + parseSnow(day.night?.snow)
      }
    })

    return {
      source: 'snow-forecast',
      forecast: detailedForecast,
      basicInfo: data.basicInfo || null
    }
  } catch (error) {
    console.error(`Snow-Forecast error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Fetch ALL augmented data for a single resort (detail view)
 * Combines Tomorrow.io and Snow-Forecast data
 */
export async function fetchResortDetailData(resort) {
  const [tomorrowData, snowForecastData] = await Promise.all([
    fetchTomorrowIoDetail(resort),
    fetchSnowForecastDetail(resort)
  ])

  return {
    resortId: resort.id,
    tomorrow: tomorrowData,
    snowForecast: snowForecastData
  }
}

// Legacy export for backward compatibility
export const fetchAllResortsEnsemble = fetchAllResortsWeather

export default {
  fetchOpenMeteoWeather,
  fetchAllResortsWeather,
  fetchAllResortsEnsemble: fetchAllResortsWeather,
  fetchTomorrowIoDetail,
  fetchSnowForecastDetail,
  fetchResortDetailData
}
