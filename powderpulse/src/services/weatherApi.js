// Open-Meteo API service for ski weather forecasts
// Free API, no key required - but rate limited

const BASE_URL = 'https://api.open-meteo.com/v1/forecast'

// Delay helper
const delay = (ms) => new Promise(resolve => setTimeout(resolve, ms))

// Fetch weather data for a single resort
export const fetchResortWeather = async (resort) => {
  const params = new URLSearchParams({
    latitude: resort.latitude,
    longitude: resort.longitude,
    hourly: 'temperature_2m,precipitation,snowfall,snow_depth,wind_speed_10m,weather_code',
    daily: 'temperature_2m_max,temperature_2m_min,snowfall_sum,precipitation_probability_max,weather_code',
    forecast_days: 16,
    temperature_unit: 'fahrenheit',
    timezone: resort.timezone || 'America/Denver',
    precipitation_unit: 'inch'
  })

  try {
    const response = await fetch(`${BASE_URL}?${params}`)
    if (!response.ok) {
      if (response.status === 429) {
        // Rate limited - wait and retry once
        await delay(2000)
        const retryResponse = await fetch(`${BASE_URL}?${params}`)
        if (!retryResponse.ok) {
          throw new Error(`Weather API error: ${retryResponse.status}`)
        }
        const data = await retryResponse.json()
        return processWeatherData(resort.id, data)
      }
      throw new Error(`Weather API error: ${response.status}`)
    }
    const data = await response.json()
    return processWeatherData(resort.id, data)
  } catch (error) {
    console.error(`Error fetching weather for ${resort.name}:`, error)
    return null
  }
}

// Fetch weather for all resorts with batching to avoid rate limits
export const fetchAllResortsWeather = async (resorts) => {
  const weatherData = {}
  const BATCH_SIZE = 5 // Fetch 5 at a time
  const BATCH_DELAY = 1000 // Wait 1s between batches

  // Process in batches
  for (let i = 0; i < resorts.length; i += BATCH_SIZE) {
    const batch = resorts.slice(i, i + BATCH_SIZE)
    const promises = batch.map(resort => fetchResortWeather(resort))
    const results = await Promise.allSettled(promises)

    results.forEach((result, index) => {
      if (result.status === 'fulfilled' && result.value) {
        weatherData[batch[index].id] = result.value
      }
    })

    // Delay between batches (except for last batch)
    if (i + BATCH_SIZE < resorts.length) {
      await delay(BATCH_DELAY)
    }
  }

  return weatherData
}

// Process raw API data into our format
const processWeatherData = (resortId, data) => {
  const { hourly, daily } = data

  // Calculate snow totals
  const snow24h = calculateSnowTotal(daily.snowfall_sum, 0, 1)
  const snow48h = calculateSnowTotal(daily.snowfall_sum, 0, 2)
  const snow7Day = calculateSnowTotal(daily.snowfall_sum, 0, 7)
  const snow15Day = calculateSnowTotal(daily.snowfall_sum, 0, 15)

  // Get current conditions from hourly data
  const currentHourIndex = findCurrentHourIndex(hourly.time)
  const currentTemp = hourly.temperature_2m[currentHourIndex] || null
  const currentSnowDepth = hourly.snow_depth[currentHourIndex] || 0
  const currentWindSpeed = hourly.wind_speed_10m[currentHourIndex] || 0

  // Build daily forecast array
  const dailyForecast = daily.time.map((date, index) => ({
    date,
    tempMax: daily.temperature_2m_max[index],
    tempMin: daily.temperature_2m_min[index],
    snowfall: daily.snowfall_sum[index] || 0,
    precipProb: daily.precipitation_probability_max[index] || 0,
    weatherCode: daily.weather_code[index],
    confidence: index < 7 ? 'high' : index < 12 ? 'medium' : 'low'
  }))

  // Build hourly forecast for next 48 hours
  const hourlyForecast = hourly.time.slice(0, 48).map((time, index) => ({
    time,
    temp: hourly.temperature_2m[index],
    snowfall: hourly.snowfall[index] || 0,
    precipitation: hourly.precipitation[index] || 0,
    windSpeed: hourly.wind_speed_10m[index],
    weatherCode: hourly.weather_code[index]
  }))

  // Check for powder alert (6"+ in next 48 hours)
  const isPowderDay = snow48h >= 6

  return {
    resortId,
    lastUpdated: new Date().toISOString(),
    current: {
      temp: currentTemp,
      snowDepth: currentSnowDepth,
      windSpeed: currentWindSpeed
    },
    snow24h,
    snow48h,
    snow7Day,
    snow15Day,
    isPowderDay,
    dailyForecast,
    hourlyForecast,
    // For sparkline chart
    sparklineData: dailyForecast.slice(0, 7).map(d => ({
      day: new Date(d.date).toLocaleDateString('en-US', { weekday: 'short' }),
      snow: d.snowfall
    }))
  }
}

// Helper to calculate snow totals
const calculateSnowTotal = (snowfallArray, startDay, endDay) => {
  if (!snowfallArray) return 0
  return snowfallArray
    .slice(startDay, endDay)
    .reduce((sum, val) => sum + (val || 0), 0)
}

// Find the index for the current hour
const findCurrentHourIndex = (timeArray) => {
  const now = new Date()
  const currentHour = now.toISOString().slice(0, 13)
  const index = timeArray.findIndex(t => t.startsWith(currentHour))
  return index >= 0 ? index : 0
}

// Get weather description from code
export const getWeatherDescription = (code) => {
  const descriptions = {
    0: 'Clear',
    1: 'Mainly clear',
    2: 'Partly cloudy',
    3: 'Overcast',
    45: 'Foggy',
    48: 'Rime fog',
    51: 'Light drizzle',
    53: 'Drizzle',
    55: 'Dense drizzle',
    61: 'Light rain',
    63: 'Rain',
    65: 'Heavy rain',
    66: 'Freezing rain',
    67: 'Heavy freezing rain',
    71: 'Light snow',
    73: 'Snow',
    75: 'Heavy snow',
    77: 'Snow grains',
    80: 'Light showers',
    81: 'Showers',
    82: 'Heavy showers',
    85: 'Light snow showers',
    86: 'Heavy snow showers',
    95: 'Thunderstorm',
    96: 'Thunderstorm with hail',
    99: 'Heavy thunderstorm'
  }
  return descriptions[code] || 'Unknown'
}

// Check if weather code indicates snow
export const isSnowingCode = (code) => {
  return [71, 73, 75, 77, 85, 86].includes(code)
}
