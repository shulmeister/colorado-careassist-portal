/**
 * Weather Unlocked API - For Japan (Niseko) and potentially other regions
 *
 * API provides ski resort specific forecasts
 * https://developer.weatherunlocked.com/
 */

const APP_ID = '5e8cea21'
const APP_KEY = '92538c1a0601feeb3d9fb661763d30ed'
const BASE_URL = 'https://api.weatherunlocked.com/api'

/**
 * Fetch current weather for a location
 */
export async function fetchWeatherUnlockedCurrent(lat, lng) {
  try {
    const response = await fetch(
      `${BASE_URL}/current/${lat},${lng}?app_id=${APP_ID}&app_key=${APP_KEY}`
    )

    if (!response.ok) {
      console.error(`Weather Unlocked current error: ${response.status}`)
      return null
    }

    return await response.json()
  } catch (error) {
    console.error('Weather Unlocked current error:', error)
    return null
  }
}

/**
 * Fetch forecast for a location (up to 7 days)
 */
export async function fetchWeatherUnlockedForecast(lat, lng) {
  try {
    const response = await fetch(
      `${BASE_URL}/forecast/${lat},${lng}?app_id=${APP_ID}&app_key=${APP_KEY}`
    )

    if (!response.ok) {
      console.error(`Weather Unlocked forecast error: ${response.status}`)
      return null
    }

    return await response.json()
  } catch (error) {
    console.error('Weather Unlocked forecast error:', error)
    return null
  }
}

/**
 * Fetch ski resort forecast - specialized endpoint for snow sports
 */
export async function fetchSkiResortForecast(lat, lng) {
  try {
    // Weather Unlocked has a specific ski resort forecast endpoint
    const response = await fetch(
      `${BASE_URL}/resortforecast/${lat},${lng}?app_id=${APP_ID}&app_key=${APP_KEY}&num_of_days=7`
    )

    if (!response.ok) {
      // Fall back to regular forecast if ski endpoint fails
      console.log('Ski resort endpoint failed, using regular forecast')
      return await fetchWeatherUnlockedForecast(lat, lng)
    }

    return await response.json()
  } catch (error) {
    console.error('Weather Unlocked ski forecast error:', error)
    return null
  }
}

/**
 * Fetch weather for a Japan resort (Niseko)
 * Converts Weather Unlocked data to our standard format
 */
export async function fetchWeatherUnlockedForResort(resort) {
  const lat = resort.latitude
  const lng = resort.longitude

  try {
    // Try ski resort forecast first, fall back to regular
    const [forecastData, currentData] = await Promise.all([
      fetchSkiResortForecast(lat, lng),
      fetchWeatherUnlockedCurrent(lat, lng)
    ])

    if (!forecastData) {
      console.warn(`Weather Unlocked failed for ${resort.name}`)
      return null
    }

    // Parse the forecast data into our format
    const days = forecastData.Days || forecastData.forecast || []

    const dailyForecast = days.map(day => {
      // Weather Unlocked provides multiple time slots per day
      const timeSlots = day.Timeframes || []

      // Aggregate snow across all time slots
      const totalSnow = timeSlots.reduce((sum, slot) => {
        // Snow is in cm, convert to inches
        const snowCm = slot.snow_total_cm || slot.freshsnow_cm || 0
        return sum + (snowCm / 2.54)
      }, 0)

      // Get max/min temps
      const temps = timeSlots.map(slot => slot.temp_c || slot.temp_f)
      const tempMax = temps.length > 0 ? Math.max(...temps) : null
      const tempMin = temps.length > 0 ? Math.min(...temps) : null

      // Convert C to F if needed
      const toFahrenheit = (c) => c !== null ? Math.round((c * 9/5) + 32) : null

      return {
        date: day.date,
        tempMax: day.temp_max_f || toFahrenheit(day.temp_max_c) || toFahrenheit(tempMax),
        tempMin: day.temp_min_f || toFahrenheit(day.temp_min_c) || toFahrenheit(tempMin),
        snowfall: Math.round(totalSnow * 10) / 10,
        windSpeed: day.windspd_max_mph || Math.max(...timeSlots.map(s => s.windspd_mph || 0)),
        precipProbability: day.prob_precip_pct || 0,
        source: 'weather-unlocked'
      }
    })

    // Calculate snow totals
    const snow24h = dailyForecast[0]?.snowfall || 0
    const snow48h = dailyForecast.slice(0, 2).reduce((sum, d) => sum + (d.snowfall || 0), 0)
    const snow5Day = dailyForecast.slice(0, 5).reduce((sum, d) => sum + (d.snowfall || 0), 0)
    const snow7Day = dailyForecast.slice(0, 7).reduce((sum, d) => sum + (d.snowfall || 0), 0)

    // Powder alert: 6"+ in next 48 hours
    const isPowderDay = snow48h >= 6

    // Current conditions
    const current = currentData ? {
      temp: currentData.temp_f || Math.round((currentData.temp_c * 9/5) + 32),
      windSpeed: currentData.windspd_mph || 0,
      humidity: currentData.humid_pct || 0,
      cloudCover: currentData.cloudtotal_pct || 0
    } : null

    return {
      resortId: resort.id,
      source: 'weather-unlocked',
      lastUpdated: new Date().toISOString(),
      coordinates: { lat, lng },
      current,
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
    console.error(`Weather Unlocked error for ${resort.name}:`, error)
    return null
  }
}

export default {
  fetchWeatherUnlockedCurrent,
  fetchWeatherUnlockedForecast,
  fetchSkiResortForecast,
  fetchWeatherUnlockedForResort
}
