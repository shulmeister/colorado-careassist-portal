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
const RAPIDAPI_KEY = 'ce3b334075msh80fc4f61ed53886p1d70d8jsn943da04fc000'

// API endpoints
const OPEN_METEO_BASE = 'https://api.open-meteo.com/v1/forecast'
const TOMORROW_BASE = 'https://api.tomorrow.io/v4/timelines'
const OPENWEATHER_BASE = 'https://api.openweathermap.org/data/3.0/onecall'
const SNOW_FORECAST_BASE = 'https://ski-resort-forecast.p.rapidapi.com'

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
 * Regional snowfall multiplier
 * Some regions get more snow than weather models predict
 * due to maritime effects, lake effect, or unique geography
 *
 * These are CONSERVATIVE multipliers - we don't want to overshoot
 */
const getRegionalMultiplier = (region, resortId) => {
  // Japan - Sea of Japan effect (Siberian Express)
  // Calibrated: 1.5x gave 21", 2.5x gave 98", target is 42" -> use 2.0x
  if (region === 'japan') {
    return 2.0
  }

  // Alaska - Alyeska gets maritime snow
  if (region === 'alaska') {
    return 1.5
  }

  // Pacific Northwest - Cascades
  if (['crystal-mountain', 'mt-baker', 'stevens-pass', 'mt-bachelor'].includes(resortId)) {
    return 1.4
  }

  // BC Interior - Interior snow belts
  if (['revelstoke', 'kicking-horse', 'fernie', 'whitefish'].includes(resortId)) {
    return 1.35
  }

  // Utah Cottonwood Canyons - Greatest Snow on Earth
  if (['alta', 'snowbird', 'brighton', 'solitude'].includes(resortId)) {
    return 1.25
  }

  // California Sierra - Atmospheric rivers
  if (['mammoth', 'kirkwood', 'palisades-tahoe', 'sugar-bowl'].includes(resortId)) {
    return 1.2
  }

  // Colorado storm zones
  if (['wolf-creek', 'steamboat', 'crested-butte'].includes(resortId)) {
    return 1.15
  }

  return 1.0
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
 * Snow-forecast.com resort slug mapping
 * This API provides excellent ski-specific forecasts
 */
const SNOW_FORECAST_SLUGS = {
  // Colorado
  'vail': 'Vail',
  'beaver-creek': 'Beaver-Creek',
  'breckenridge': 'Breckenridge',
  'keystone': 'Keystone',
  'crested-butte': 'Crested-Butte-Mountain-Resort',
  'telluride': 'Telluride',
  'park-city': 'Park-City',
  'steamboat': 'Steamboat',
  'aspen-snowmass': 'Snowmass',
  'winter-park': 'Winter-Park-Resort',
  'copper-mountain': 'Copper-Mountain',
  'eldora': 'Eldora-Mountain-Resort',
  'arapahoe-basin': 'Arapahoe-Basin',
  'loveland': 'Loveland',
  'purgatory': 'Purgatory',
  'monarch': 'Monarch-Mountain',
  'powderhorn': 'Powderhorn',
  'sunlight': 'Sunlight-Mountain-Resort',
  'wolf-creek': 'Wolf-Creek',
  // Utah
  'snowbird': 'Snowbird',
  'alta': 'Alta',
  'brighton': 'Brighton',
  'solitude': 'Solitude',
  'deer-valley': 'Deer-Valley',
  'snowbasin': 'Snowbasin',
  'sundance': 'Sundance',
  // California
  'mammoth': 'Mammoth',
  'palisades-tahoe': 'Squaw-Valley',
  'heavenly': 'Heavenly',
  'kirkwood': 'Kirkwood',
  'northstar': 'Northstar-at-Tahoe',
  'big-bear': 'Big-Bear-Mountain',
  // Wyoming/Montana/Idaho
  'jackson-hole': 'Jackson-Hole',
  'big-sky': 'Big-Sky',
  'grand-targhee': 'Grand-Targhee',
  'sun-valley': 'Sun-Valley',
  'schweitzer': 'Schweitzer-Mountain',
  'whitefish': 'Whitefish-Mountain-Resort',
  // Pacific Northwest
  'crystal-mountain': 'Crystal-Mountain',
  'mt-bachelor': 'Mount-Bachelor',
  'stevens-pass': 'Stevens-Pass',
  'mt-baker': 'Mt-Baker',
  // Canada
  'whistler': 'Whistler-Blackcomb',
  'revelstoke': 'Revelstoke-Mountain-Resort',
  'lake-louise': 'Lake-Louise',
  'sunshine-village': 'Sunshine-Village',
  'kicking-horse': 'Kicking-Horse',
  'big-white': 'Big-White',
  'red-mountain': 'Red-Mountain',
  'fernie': 'Fernie-Alpine',
  // Japan
  'niseko': 'Niseko',
  'hakuba': 'Hakuba-Valley',
  'myoko-kogen': 'Myoko-Kogen',
  'nozawa-onsen': 'Nozawa-Onsen',
  'shiga-kogen': 'Shiga-Kogen',
  'furano': 'Furano',
  'rusutsu': 'Rusutsu',
  // Europe
  'chamonix': 'Chamonix',
  'zermatt': 'Zermatt',
  'st-anton': 'St-Anton',
  'val-disere': 'Val-d-Isere',
  'verbier': 'Verbier',
  'cervinia': 'Cervinia',
  'cortina': 'Cortina-d-Ampezzo',
  'lech-zurs': 'Lech',
  'kitzbuhel': 'Kitzbuhel',
  // East Coast
  'killington': 'Killington',
  'stowe': 'Stowe',
  'sugarbush': 'Sugarbush',
  'jay-peak': 'Jay-Peak',
  'sugarloaf': 'Sugarloaf',
  'sunday-river': 'Sunday-River',
  // New Mexico
  'taos': 'Taos-Ski-Valley',
  // Alaska
  'alyeska': 'Alyeska'
}

/**
 * Fetch from Snow-Forecast.com via RapidAPI
 * This is a ski-specific forecast source with excellent accuracy
 */
async function fetchSnowForecast(resort) {
  const slug = SNOW_FORECAST_SLUGS[resort.id]
  if (!slug) {
    // Resort not in our mapping, skip this source
    return null
  }

  try {
    const response = await fetch(`${SNOW_FORECAST_BASE}/${slug}/forecast?units=i&el=top`, {
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

    // Convert 5-day forecast (AM/PM/Night) to daily totals
    const daily = forecast5Day.map(day => {
      // Sum snow from AM + PM + Night
      const amSnow = parseFloat(day.am?.snow?.replace('in', '') || 0)
      const pmSnow = parseFloat(day.pm?.snow?.replace('in', '') || 0)
      const nightSnow = parseFloat(day.night?.snow?.replace('in', '') || 0)
      const totalSnow = amSnow + pmSnow + nightSnow

      // Parse temperatures
      const temps = [
        parseFloat(day.am?.maxTemp?.replace('°F', '') || 0),
        parseFloat(day.am?.minTemp?.replace('°F', '') || 0),
        parseFloat(day.pm?.maxTemp?.replace('°F', '') || 0),
        parseFloat(day.pm?.minTemp?.replace('°F', '') || 0),
        parseFloat(day.night?.maxTemp?.replace('°F', '') || 0),
        parseFloat(day.night?.minTemp?.replace('°F', '') || 0)
      ].filter(t => !isNaN(t) && t !== 0)

      const tempMax = temps.length > 0 ? Math.max(...temps) : 32
      const tempMin = temps.length > 0 ? Math.min(...temps) : 20

      // Calculate date from day of week
      const dayNames = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
      const today = new Date()
      const todayDay = today.getDay()
      const targetDay = dayNames.indexOf(day.dayOfWeek.toLowerCase())
      let daysAhead = targetDay - todayDay
      if (daysAhead < 0) daysAhead += 7
      const targetDate = new Date(today)
      targetDate.setDate(today.getDate() + daysAhead)
      const dateStr = targetDate.toISOString().split('T')[0]

      return {
        date: dateStr,
        tempMax,
        tempMin,
        precipInches: totalSnow * 0.1,  // Rough estimate: snow / 10 = water equiv
        snowfallRaw: totalSnow,
        precipProb: totalSnow > 0 ? 80 : 20,  // Estimate based on snow prediction
        weatherCode: totalSnow > 2 ? 73 : (totalSnow > 0 ? 71 : 0)
      }
    })

    return {
      source: 'snow-forecast',
      daily
    }
  } catch (error) {
    console.error(`Snow-Forecast error for ${resort.name}:`, error)
    return null
  }
}

/**
 * Calculate snow from precipitation using temperature-based snow:liquid ratio
 * Now includes regional multiplier for areas where models underpredict
 */
function calculateSnowFromPrecip(precipInches, avgTempF, elevationFt, region, resortId) {
  const ratio = getSnowLiquidRatio(avgTempF)
  const elevationMult = getElevationMultiplier(elevationFt)
  const regionalMult = getRegionalMultiplier(region, resortId)
  return precipInches * ratio * elevationMult * regionalMult
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

      // Get regional multiplier for this resort
      const regionalMult = getRegionalMultiplier(resort.region, resort.id)

      // Calculate snow estimates from each source
      // Apply regional multiplier to account for model underprediction
      const snowEstimates = data.precipValues.map((precip, i) => {
        // Raw snow from API (converted from cm to inches where applicable)
        // Apply regional multiplier since models underpredict in certain areas
        const rawSnow = (data.snowValues[i] || 0) * regionalMult

        // Calculated snow from precip with proper snow:liquid ratio
        const calcSnow = avgTemp <= 35
          ? calculateSnowFromPrecip(precip, avgTemp, resort.elevation, resort.region, resort.id)
          : 0

        // Use the higher of raw or calculated
        if (rawSnow > 0) {
          if (calcSnow > rawSnow * 1.3) {
            return rawSnow * 0.5 + calcSnow * 0.5  // Blend when calc is much higher
          }
          return rawSnow
        }

        // No raw snow but we have precip - calculate from precip
        if (precip > 0 && avgTemp <= 32) {
          return calcSnow * 0.85
        }

        return 0
      })

      // Ensemble strategy:
      // - During storms: bias toward higher predictions (75/25)
      // - Normal conditions: moderate bias toward higher (60/40)
      // Calibrated: 80/20 was too high, 70/30 too low -> 75/25
      let ensembleSnow
      if (isStormEvent && snowEstimates.length > 1) {
        // During storm events, trust the higher predictions
        const maxSnow = Math.max(...snowEstimates)
        const avgSnow = average(snowEstimates)
        ensembleSnow = avgSnow * 0.25 + maxSnow * 0.75
      } else {
        // Normal conditions
        const maxSnow = Math.max(...snowEstimates)
        const avgSnow = average(snowEstimates)
        ensembleSnow = avgSnow * 0.4 + maxSnow * 0.6
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
    // Snow-Forecast.com is ski-specific and often most accurate
    const [openMeteo, tomorrowIo, openWeather, snowForecast] = await Promise.all([
      fetchOpenMeteo(resort),
      fetchTomorrowIo(resort),
      fetchOpenWeather(resort),
      fetchSnowForecast(resort)
    ])

    // Filter out failed fetches
    const validForecasts = [openMeteo, tomorrowIo, openWeather, snowForecast].filter(f => f !== null)

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
