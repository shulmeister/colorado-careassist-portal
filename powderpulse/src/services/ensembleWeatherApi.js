/**
 * Weather API - Open-Meteo with ECMWF Models (Primary)
 *
 * Strategy:
 * - PRIMARY: Open-Meteo with ECMWF models (free, unlimited, 16-day forecast + 7-day history)
 * - AUGMENTED: Tomorrow.io and Snow-Forecast only fetched on resort detail view
 *
 * This approach:
 * - Zero API rate limits for main resort list
 * - Uses mid-mountain GPS coordinates for accurate ski-area weather
 * - ECMWF is the gold standard for weather modeling
 * - Additional ski-specific data available on resort click
 */

// API Keys (only used for augmented detail data)
const TOMORROW_API_KEY = 'qyqlOXozeogt1fPFw6FIATxY5D1qOXqJ'
const RAPIDAPI_KEY = 'ce3b334075msh80fc4f61ed53886p1d70d8jsn943da04fc000'

// Open-Meteo endpoint
const OPEN_METEO_BASE = 'https://api.open-meteo.com/v1/forecast'

// Delay helper for rate limiting
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Get timezone for a resort region
 */
function getTimezone(resort) {
  return resort.timezone || 'auto'
}

/**
 * PRIMARY FORECAST: Fetch from Open-Meteo with ECMWF models
 * Uses mid-mountain coordinates for accurate ski-area weather
 * Includes 7 days history + 16 days forecast
 *
 * @param {Object} resort - Resort object with midMountain coordinates
 * @returns {Object} Weather data with daily and hourly forecasts
 */
export async function fetchOpenMeteoWeather(resort) {
  // Use mid-mountain coordinates if available, otherwise fall back to base
  const lat = resort.midMountain?.lat || resort.latitude
  const lng = resort.midMountain?.lng || resort.longitude

  const params = new URLSearchParams({
    latitude: lat,
    longitude: lng,
    // ECMWF IFS 0.25° - highest resolution ECMWF model, best for mountain weather
    models: 'ecmwf_ifs025',
    // Daily aggregates
    daily: [
      'snowfall_sum',
      'rain_sum',
      'showers_sum',
      'precipitation_sum',
      'precipitation_hours',
      'precipitation_probability_max',
      'wind_direction_10m_dominant',
      'wind_gusts_10m_max',
      'wind_speed_10m_max',
      'temperature_2m_max',
      'temperature_2m_min',
      'weather_code'
    ].join(','),
    // Hourly details for charts
    hourly: [
      'temperature_2m',
      'snowfall',
      'snow_depth',
      'precipitation',
      'precipitation_probability',
      'freezing_level_height',
      'rain',
      'showers',
      'relative_humidity_2m',
      'apparent_temperature',
      'cloud_cover',
      'visibility',
      'wind_speed_10m',
      'wind_direction_10m',
      'wind_gusts_10m'
    ].join(','),
    // Current conditions
    current: [
      'temperature_2m',
      'wind_speed_10m',
      'wind_direction_10m',
      'snowfall',
      'precipitation',
      'is_day',
      'rain',
      'showers',
      'wind_gusts_10m',
      'cloud_cover',
      'weather_code'
    ].join(','),
    timezone: getTimezone(resort),
    past_days: 7,
    forecast_days: 16,
    wind_speed_unit: 'mph',
    temperature_unit: 'fahrenheit',
    precipitation_unit: 'inch'
  })

  try {
    const response = await fetch(`${OPEN_METEO_BASE}?${params}`)
    if (!response.ok) {
      console.error(`Open-Meteo error for ${resort.name}: ${response.status}`)
      return null
    }

    const data = await response.json()

    // Process daily forecast
    const dailyForecast = data.daily.time.map((date, i) => ({
      date,
      tempMax: Math.round(data.daily.temperature_2m_max[i]),
      tempMin: Math.round(data.daily.temperature_2m_min[i]),
      snowfall: data.daily.snowfall_sum[i] || 0,
      rain: data.daily.rain_sum[i] || 0,
      precipitation: data.daily.precipitation_sum[i] || 0,
      precipHours: data.daily.precipitation_hours[i] || 0,
      precipProbability: data.daily.precipitation_probability_max[i] || 0,
      windSpeed: Math.round(data.daily.wind_speed_10m_max[i] || 0),
      windGusts: Math.round(data.daily.wind_gusts_10m_max[i] || 0),
      windDirection: data.daily.wind_direction_10m_dominant[i] || 0,
      weatherCode: data.daily.weather_code[i]
    }))

    // Split into history and forecast
    const historyDays = dailyForecast.slice(0, 7)
    const forecastDays = dailyForecast.slice(7)

    // Calculate snow totals from forecast (not history)
    const snow24h = forecastDays[0]?.snowfall || 0
    const snow48h = forecastDays.slice(0, 2).reduce((sum, d) => sum + d.snowfall, 0)
    const snow5Day = forecastDays.slice(0, 5).reduce((sum, d) => sum + d.snowfall, 0)
    const snow7Day = forecastDays.slice(0, 7).reduce((sum, d) => sum + d.snowfall, 0)
    const snow10Day = forecastDays.slice(0, 10).reduce((sum, d) => sum + d.snowfall, 0)
    const snow15Day = forecastDays.slice(0, 15).reduce((sum, d) => sum + d.snowfall, 0)

    // Historical snow (last 7 days)
    const snowLast7Days = historyDays.reduce((sum, d) => sum + d.snowfall, 0)

    // Find biggest snow day in forecast
    const biggestDay = forecastDays.reduce((max, day) =>
      day.snowfall > max.snowfall ? day : max, forecastDays[0] || { snowfall: 0, date: null })

    // Powder alert: 6"+ in next 48 hours
    const isPowderDay = snow48h >= 6

    // Current conditions
    const current = data.current ? {
      temp: Math.round(data.current.temperature_2m),
      windSpeed: Math.round(data.current.wind_speed_10m),
      windGusts: Math.round(data.current.wind_gusts_10m),
      windDirection: data.current.wind_direction_10m,
      snowfall: data.current.snowfall || 0,
      precipitation: data.current.precipitation || 0,
      cloudCover: data.current.cloud_cover,
      isDay: data.current.is_day === 1,
      weatherCode: data.current.weather_code
    } : null

    // Process hourly data (for charts)
    const hourlyForecast = data.hourly.time.map((time, i) => ({
      time,
      temp: Math.round(data.hourly.temperature_2m[i]),
      snowfall: data.hourly.snowfall[i] || 0,
      snowDepth: data.hourly.snow_depth[i] || 0,
      precipitation: data.hourly.precipitation[i] || 0,
      precipProbability: data.hourly.precipitation_probability[i] || 0,
      freezingLevel: data.hourly.freezing_level_height[i],
      humidity: data.hourly.relative_humidity_2m[i],
      feelsLike: Math.round(data.hourly.apparent_temperature[i]),
      cloudCover: data.hourly.cloud_cover[i],
      visibility: data.hourly.visibility[i],
      windSpeed: Math.round(data.hourly.wind_speed_10m[i] || 0),
      windDirection: data.hourly.wind_direction_10m[i],
      windGusts: Math.round(data.hourly.wind_gusts_10m[i] || 0)
    }))

    return {
      resortId: resort.id,
      source: 'open-meteo-ecmwf',
      lastUpdated: new Date().toISOString(),
      coordinates: { lat, lng },
      current,
      // Snow totals (from forecast, not history)
      snow24h: Math.round(snow24h * 10) / 10,
      snow48h: Math.round(snow48h * 10) / 10,
      snow5Day: Math.round(snow5Day * 10) / 10,
      snow7Day: Math.round(snow7Day * 10) / 10,
      snow10Day: Math.round(snow10Day * 10) / 10,
      snow15Day: Math.round(snow15Day * 10) / 10,
      // Historical
      snowLast7Days: Math.round(snowLast7Days * 10) / 10,
      history: historyDays,
      // Forecasts
      dailyForecast: forecastDays,
      hourlyForecast,
      // Alerts
      isPowderDay,
      biggestDay: biggestDay.date ? {
        date: biggestDay.date,
        snowfall: Math.round(biggestDay.snowfall * 10) / 10
      } : null,
      // For sparkline charts
      sparklineData: forecastDays.slice(0, 15).map(d => ({
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
 * Fetch weather for ALL resorts using Open-Meteo
 * No rate limits - can fetch all 36 resorts simultaneously
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
  const lat = resort.midMountain?.lat || resort.latitude
  const lng = resort.midMountain?.lng || resort.longitude

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
