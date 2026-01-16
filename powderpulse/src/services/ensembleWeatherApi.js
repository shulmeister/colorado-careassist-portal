/**
 * Ensemble Weather API - Aggregates multiple weather sources for accurate snow forecasting
 *
 * Sources:
 * - Open-Meteo (free, good baseline)
 * - Tomorrow.io (excellent for storms, marine/mountain weather)
 * - OpenWeather (solid general forecasts)
 *
 * The ensemble approach:
 * 1. Fetch from all available APIs
 * 2. Apply elevation-based snow:liquid ratios
 * 3. Weight forecasts based on conditions and source reliability
 * 4. Take weighted average, biased toward higher snow predictions during storm events
 */

// API Keys
const TOMORROW_API_KEY = 'qyqlOXozeogt1fPFw6FIATxY5D1qOXqJ'
const OPENWEATHER_API_KEY = '14fbd2e16392159424b09d4c8b26cec3'

// API endpoints
const OPEN_METEO_BASE = 'https://api.open-meteo.com/v1/forecast'
const TOMORROW_BASE = 'https://api.tomorrow.io/v4/timelines'
const OPENWEATHER_BASE = 'https://api.openweathermap.org/data/3.0/onecall'

// Delay helper for rate limiting
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

/**
 * Snow:Liquid Ratio based on temperature
 * Colder temps = fluffier snow = higher ratio
 * This is critical for accurate snow depth forecasting
 */
const getSnowLiquidRatio = (tempF) => {
  if (tempF <= 0) return 20      // Very cold = very fluffy (20:1)
  if (tempF <= 10) return 18     // Cold = fluffy (18:1)
  if (tempF <= 20) return 15     // Cool = light (15:1)
  if (tempF <= 28) return 12     // Near freezing = moderate (12:1)
  if (tempF <= 32) return 10     // At freezing = standard (10:1)
  return 8                        // Above freezing = heavy/wet (8:1)
}

/**
 * Elevation adjustment factor
 * Higher elevations get significantly more snow due to orographic lift
 * Research shows orographic enhancement can be 1.5-2x at summit levels
 */
const getElevationMultiplier = (elevationFt) => {
  if (elevationFt >= 12000) return 1.5   // Ultra high (12k+) - serious orographic lift
  if (elevationFt >= 11000) return 1.4   // Very high (11k-12k)
  if (elevationFt >= 9000) return 1.3    // High (9k-11k)
  if (elevationFt >= 7000) return 1.2    // Moderate (7k-9k)
  if (elevationFt >= 5000) return 1.1    // Low mountain (5k-7k)
  return 1.0                              // Base level
}

/**
 * Get the best weather model for a region
 * Different models are more accurate for different parts of the world
 */
function getRegionalModel(region) {
  switch (region) {
    case 'japan':
      return 'jma_seamless'  // Japanese Meteorological Agency - best for Japan
    case 'europe':
      return 'ecmwf_ifs04'   // European Centre - best for Europe/Alps
    case 'canada':
      return 'gem_seamless'  // Canadian model - good for BC/Alberta
    default:
      return 'gfs_seamless'  // US GFS model - good for North America
  }
}

/**
 * Fetch from Open-Meteo (free, no key required)
 * CRITICAL: snowfall_sum is in CENTIMETERS, must convert to inches!
 */
async function fetchOpenMeteo(resort) {
  // Use regional model for better accuracy
  const model = getRegionalModel(resort.region)

  const params = new URLSearchParams({
    latitude: resort.latitude,
    longitude: resort.longitude,
    models: model,
    hourly: 'temperature_2m,precipitation,snowfall,precipitation_probability',
    daily: 'temperature_2m_max,temperature_2m_min,precipitation_sum,snowfall_sum,precipitation_probability_max,weather_code',
    forecast_days: 16,
    temperature_unit: 'fahrenheit',
    precipitation_unit: 'inch',
    timezone: resort.timezone || 'auto'
  })

  try {
    const response = await fetch(`${OPEN_METEO_BASE}?${params}`)
    if (!response.ok) return null
    const data = await response.json()

    return {
      source: 'open-meteo',
      model: model,
      daily: data.daily.time.map((date, i) => ({
        date,
        tempMax: data.daily.temperature_2m_max[i],
        tempMin: data.daily.temperature_2m_min[i],
        precipInches: data.daily.precipitation_sum[i] || 0,
        // CRITICAL FIX: Open-Meteo snowfall_sum is in CENTIMETERS, convert to inches!
        snowfallRaw: (data.daily.snowfall_sum[i] || 0) / 2.54,
        precipProb: data.daily.precipitation_probability_max[i] || 0,
        weatherCode: data.daily.weather_code[i]
      }))
    }
  } catch (error) {
    console.error(`Open-Meteo error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Fetch from Tomorrow.io (excellent for storms)
 */
async function fetchTomorrowIo(resort) {
  const params = new URLSearchParams({
    location: `${resort.latitude},${resort.longitude}`,
    apikey: TOMORROW_API_KEY,
    units: 'imperial',
    timesteps: '1d',
    fields: 'temperatureMax,temperatureMin,precipitationIntensityAvg,precipitationProbabilityAvg,snowAccumulation,weatherCodeMax'
  })

  try {
    const response = await fetch(`${TOMORROW_BASE}?${params}`)
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
      daily: intervals.map(interval => ({
        date: interval.startTime.split('T')[0],
        tempMax: interval.values.temperatureMax,
        tempMin: interval.values.temperatureMin,
        precipInches: (interval.values.precipitationIntensityAvg || 0) * 24, // Convert rate to daily total
        snowfallRaw: interval.values.snowAccumulation || 0,
        precipProb: interval.values.precipitationProbabilityAvg || 0,
        weatherCode: interval.values.weatherCodeMax
      }))
    }
  } catch (error) {
    console.error(`Tomorrow.io error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Fetch from OpenWeather (solid forecasts)
 */
async function fetchOpenWeather(resort) {
  const params = new URLSearchParams({
    lat: resort.latitude,
    lon: resort.longitude,
    appid: OPENWEATHER_API_KEY,
    units: 'imperial',
    exclude: 'minutely,alerts'
  })

  try {
    const response = await fetch(`${OPENWEATHER_BASE}?${params}`)
    if (!response.ok) {
      // Try fallback to 5-day forecast API (free tier)
      return await fetchOpenWeatherFallback(resort)
    }
    const data = await response.json()

    return {
      source: 'openweather',
      daily: data.daily?.slice(0, 8).map(day => ({
        date: new Date(day.dt * 1000).toISOString().split('T')[0],
        tempMax: day.temp.max,
        tempMin: day.temp.min,
        precipInches: ((day.rain || 0) + (day.snow || 0)) / 25.4, // Convert mm to inches
        snowfallRaw: (day.snow || 0) / 25.4,
        precipProb: (day.pop || 0) * 100,
        weatherCode: day.weather?.[0]?.id
      })) || []
    }
  } catch (error) {
    console.error(`OpenWeather error for ${resort.name}:`, error)
    return await fetchOpenWeatherFallback(resort)
  }
}

/**
 * OpenWeather 5-day forecast fallback (free tier)
 */
async function fetchOpenWeatherFallback(resort) {
  const params = new URLSearchParams({
    lat: resort.latitude,
    lon: resort.longitude,
    appid: OPENWEATHER_API_KEY,
    units: 'imperial'
  })

  try {
    const response = await fetch(`https://api.openweathermap.org/data/2.5/forecast?${params}`)
    if (!response.ok) return null
    const data = await response.json()

    // Group 3-hour forecasts into daily
    const dailyMap = {}
    data.list?.forEach(item => {
      const date = item.dt_txt.split(' ')[0]
      if (!dailyMap[date]) {
        dailyMap[date] = {
          temps: [],
          precip: 0,
          snow: 0,
          pop: 0,
          weatherCodes: []
        }
      }
      dailyMap[date].temps.push(item.main.temp)
      dailyMap[date].precip += (item.rain?.['3h'] || 0) + (item.snow?.['3h'] || 0)
      dailyMap[date].snow += item.snow?.['3h'] || 0
      dailyMap[date].pop = Math.max(dailyMap[date].pop, item.pop || 0)
      dailyMap[date].weatherCodes.push(item.weather?.[0]?.id)
    })

    return {
      source: 'openweather-5day',
      daily: Object.entries(dailyMap).map(([date, data]) => ({
        date,
        tempMax: Math.max(...data.temps),
        tempMin: Math.min(...data.temps),
        precipInches: data.precip / 25.4,
        snowfallRaw: data.snow / 25.4,
        precipProb: data.pop * 100,
        weatherCode: data.weatherCodes[0]
      }))
    }
  } catch (error) {
    console.error(`OpenWeather fallback error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Calculate snow from precipitation using temperature-based snow:liquid ratio
 */
function calculateSnowFromPrecip(precipInches, avgTempF, elevationFt) {
  const ratio = getSnowLiquidRatio(avgTempF)
  const elevationMult = getElevationMultiplier(elevationFt)
  return precipInches * ratio * elevationMult
}

/**
 * Ensemble the forecasts from multiple sources
 * Strategy: Bias toward higher snow predictions during cold, high-probability events
 */
function ensembleForecasts(forecasts, resort) {
  if (!forecasts.length) return null

  // Build a map of dates to all available predictions
  const dateMap = {}

  forecasts.forEach(forecast => {
    if (!forecast?.daily) return

    forecast.daily.forEach(day => {
      if (!dateMap[day.date]) {
        dateMap[day.date] = {
          sources: [],
          tempMaxes: [],
          tempMins: [],
          precipValues: [],
          snowValues: [],
          precipProbs: []
        }
      }
      dateMap[day.date].sources.push(forecast.source)
      dateMap[day.date].tempMaxes.push(day.tempMax)
      dateMap[day.date].tempMins.push(day.tempMin)
      dateMap[day.date].precipValues.push(day.precipInches)
      dateMap[day.date].snowValues.push(day.snowfallRaw)
      dateMap[day.date].precipProbs.push(day.precipProb)
    })
  })

  // Create ensemble daily forecast
  const dailyForecast = Object.entries(dateMap)
    .sort(([a], [b]) => a.localeCompare(b))
    .slice(0, 16)  // Max 16 days
    .map(([date, data], index) => {
      // Average temperatures
      const tempMax = average(data.tempMaxes)
      const tempMin = average(data.tempMins)
      const avgTemp = (tempMax + tempMin) / 2

      // For precipitation and snow, use weighted approach
      // Bias toward higher values during storm events (high precip prob)
      const avgPrecipProb = average(data.precipProbs)
      const isStormEvent = avgPrecipProb > 60

      // Calculate snow estimates from each source
      // Now that Open-Meteo cm->inches conversion is fixed, trust the raw API values more
      const snowEstimates = data.precipValues.map((precip, i) => {
        // Raw snow from API (now properly converted from cm to inches)
        const rawSnow = data.snowValues[i] || 0

        // Calculated snow from precip with proper snow:liquid ratio
        // Used as a sanity check / enhancement for cold temps
        const calcSnow = avgTemp <= 35
          ? calculateSnowFromPrecip(precip, avgTemp, resort.elevation)
          : 0

        // Trust raw snow values more now that units are correct
        // Only enhance with calculation if it significantly exceeds raw value
        if (rawSnow > 0) {
          // If calculated snow is much higher (like 2x+), use blend
          // This helps catch cases where API underestimates fluffy powder
          if (calcSnow > rawSnow * 1.5) {
            return rawSnow * 0.6 + calcSnow * 0.4  // Blend toward higher
          }
          return rawSnow  // Trust API value
        }

        // No raw snow but we have precip - calculate from precip
        if (precip > 0 && avgTemp <= 32) {
          return calcSnow * 0.8  // Use calculation but slightly conservative
        }

        return 0
      })

      // Ensemble strategy:
      // - During storms: bias toward higher predictions (take max of credible values)
      // - Normal conditions: weighted average biased toward higher
      let ensembleSnow
      if (isStormEvent && snowEstimates.length > 1) {
        // During storm events, trust the higher predictions
        // Models often underestimate mountain snow during storms
        const maxSnow = Math.max(...snowEstimates)
        const avgSnow = average(snowEstimates)
        ensembleSnow = avgSnow * 0.4 + maxSnow * 0.6  // Bias toward max during storms
      } else {
        // Normal conditions: weighted average with moderate max bias
        const maxSnow = Math.max(...snowEstimates)
        const avgSnow = average(snowEstimates)
        ensembleSnow = avgSnow * 0.5 + maxSnow * 0.5
      }

      // Confidence based on forecast distance and source agreement
      const variance = standardDeviation(snowEstimates)
      const sourceCount = data.sources.length
      let confidence = 'high'
      if (index > 10 || variance > 3 || sourceCount < 2) {
        confidence = 'low'
      } else if (index > 5 || variance > 1.5) {
        confidence = 'medium'
      }

      return {
        date,
        tempMax: Math.round(tempMax),
        tempMin: Math.round(tempMin),
        snowfall: Math.round(ensembleSnow * 10) / 10,  // Round to 0.1"
        precipProbability: Math.round(avgPrecipProb),
        confidence,
        sources: data.sources,
        sourceAgreement: variance < 1 ? 'high' : variance < 3 ? 'medium' : 'low'
      }
    })

  return dailyForecast
}

// Helper functions
function average(arr) {
  if (!arr.length) return 0
  return arr.reduce((a, b) => a + b, 0) / arr.length
}

function standardDeviation(arr) {
  if (arr.length < 2) return 0
  const avg = average(arr)
  const squareDiffs = arr.map(value => Math.pow(value - avg, 2))
  return Math.sqrt(average(squareDiffs))
}

/**
 * Main function: Fetch and ensemble weather for a resort
 */
export async function fetchEnsembleWeather(resort) {
  try {
    // Fetch from all sources in parallel
    const [openMeteo, tomorrowIo, openWeather] = await Promise.all([
      fetchOpenMeteo(resort),
      fetchTomorrowIo(resort),
      fetchOpenWeather(resort)
    ])

    // Filter out failed fetches
    const validForecasts = [openMeteo, tomorrowIo, openWeather].filter(f => f !== null)

    if (validForecasts.length === 0) {
      console.error(`No weather data available for ${resort.name}`)
      return null
    }

    // Log which sources we got
    console.log(`${resort.name}: Got data from ${validForecasts.map(f => f.source).join(', ')}`)

    // Ensemble the forecasts
    const dailyForecast = ensembleForecasts(validForecasts, resort)

    if (!dailyForecast || dailyForecast.length === 0) {
      return null
    }

    // Calculate snow totals
    const snow24h = dailyForecast[0]?.snowfall || 0
    const snow48h = dailyForecast.slice(0, 2).reduce((sum, d) => sum + d.snowfall, 0)
    const snow5Day = dailyForecast.slice(0, 5).reduce((sum, d) => sum + d.snowfall, 0)
    const snow7Day = dailyForecast.slice(0, 7).reduce((sum, d) => sum + d.snowfall, 0)
    const snow10Day = dailyForecast.slice(0, 10).reduce((sum, d) => sum + d.snowfall, 0)
    const snow15Day = dailyForecast.slice(0, 15).reduce((sum, d) => sum + d.snowfall, 0)

    // Powder alert: 6"+ in next 48 hours
    const isPowderDay = snow48h >= 6

    // Find biggest snow day in next 7 days
    const biggestDay = dailyForecast.slice(0, 7).reduce((max, day) =>
      day.snowfall > max.snowfall ? day : max, dailyForecast[0])

    return {
      resortId: resort.id,
      lastUpdated: new Date().toISOString(),
      sources: validForecasts.map(f => f.source),
      current: {
        temp: dailyForecast[0]?.tempMax || null,
        snowDepth: null,  // Would need separate API
        windSpeed: null
      },
      snow24h,
      snow48h,
      snow5Day,
      snow7Day,
      snow10Day,
      snow15Day,
      isPowderDay,
      biggestDay: {
        date: biggestDay.date,
        snowfall: biggestDay.snowfall
      },
      dailyForecast,
      // Range display (like OpenSnow shows "4-8")
      dailyRanges: dailyForecast.map(d => ({
        date: d.date,
        low: Math.floor(d.snowfall * 0.7),  // Low estimate
        high: Math.ceil(d.snowfall * 1.3),  // High estimate
        mid: d.snowfall
      })),
      sparklineData: dailyForecast.slice(0, 15).map(d => ({
        day: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' }),
        date: d.date,
        snow: d.snowfall
      }))
    }
  } catch (error) {
    console.error(`Ensemble error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Fetch weather for all resorts with batching
 */
export async function fetchAllResortsEnsemble(resorts) {
  const weatherData = {}
  const BATCH_SIZE = 3  // Smaller batches due to API rate limits
  const BATCH_DELAY = 1500  // Longer delay between batches

  for (let i = 0; i < resorts.length; i += BATCH_SIZE) {
    const batch = resorts.slice(i, i + BATCH_SIZE)
    const promises = batch.map(resort => fetchEnsembleWeather(resort))
    const results = await Promise.allSettled(promises)

    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value) {
        weatherData[batch[index].id] = result.value
      }
    })

    // Delay between batches
    if (i + BATCH_SIZE < resorts.length) {
      await delay(BATCH_DELAY)
    }
  }

  return weatherData
}

export default {
  fetchEnsembleWeather,
  fetchAllResortsEnsemble
}
