/**
 * Meteoblue API - For Japan (and potentially other regions)
 *
 * Features:
 * - snowfraction: tells us exactly if precipitation is snow (1.0) or rain (0.0)
 * - Supports elevation (asl parameter)
 * - Good for ski resort forecasts
 */

const API_KEY = 'xi3nMt4oD8mGXRJa'
const BASE_URL = 'https://my.meteoblue.com/packages'

/**
 * Fetch weather from Meteoblue
 */
export async function fetchMeteoblueWeather(resort) {
  const lat = resort.latitude
  const lng = resort.longitude
  // Convert elevation from feet to meters
  const elevation = resort.elevation ? Math.round(resort.elevation * 0.3048) : 1000
  const timezone = resort.timezone || 'auto'

  try {
    const url = `${BASE_URL}/basic-1h_basic-day?apikey=${API_KEY}&lat=${lat}&lon=${lng}&asl=${elevation}&format=json&tz=${encodeURIComponent(timezone)}`

    const response = await fetch(url)

    if (!response.ok) {
      console.error(`Meteoblue error: ${response.status}`)
      return null
    }

    const data = await response.json()

    if (!data.data_day || !data.data_1h) {
      console.error('Meteoblue: missing data')
      return null
    }

    // Parse daily data
    const dailyData = data.data_day
    const hourlyData = data.data_1h

    // Build daily forecast
    const dailyForecast = dailyData.time.map((date, i) => {
      // Calculate snow from precipitation and snowfraction
      const precipMm = dailyData.precipitation[i] || 0
      const snowFraction = dailyData.snowfraction[i] || 0

      // Snow in inches (precip in mm, snow ratio ~10:1)
      const snowMm = precipMm * snowFraction
      const snowInches = (snowMm * 10) / 25.4  // 10:1 ratio, mm to inches

      // Convert C to F
      const tempMaxF = dailyData.temperature_max[i] !== undefined
        ? Math.round(dailyData.temperature_max[i] * 9/5 + 32)
        : null
      const tempMinF = dailyData.temperature_min[i] !== undefined
        ? Math.round(dailyData.temperature_min[i] * 9/5 + 32)
        : null

      return {
        date,
        tempMax: tempMaxF,
        tempMin: tempMinF,
        snowfall: Math.round(snowInches * 10) / 10,
        precipitation: Math.round(precipMm / 25.4 * 10) / 10, // mm to inches
        snowFraction: snowFraction,
        precipProbability: dailyData.precipitation_probability?.[i] || 0,
        windSpeed: dailyData.windspeed_mean?.[i]
          ? Math.round(dailyData.windspeed_mean[i] * 2.237) // m/s to mph
          : 0,
        pictocode: dailyData.pictocode?.[i],
        source: 'meteoblue'
      }
    })

    // Calculate snow totals
    const snow24h = dailyForecast[0]?.snowfall || 0
    const snow48h = dailyForecast.slice(0, 2).reduce((sum, d) => sum + (d.snowfall || 0), 0)
    const snow5Day = dailyForecast.slice(0, 5).reduce((sum, d) => sum + (d.snowfall || 0), 0)
    const snow7Day = dailyForecast.slice(0, 7).reduce((sum, d) => sum + (d.snowfall || 0), 0)

    // Powder alert: 6"+ in next 48 hours
    const isPowderDay = snow48h >= 6

    // Current conditions from first hourly data
    const currentIdx = 0
    const current = {
      temp: hourlyData.temperature?.[currentIdx] !== undefined
        ? Math.round(hourlyData.temperature[currentIdx] * 9/5 + 32)
        : null,
      windSpeed: hourlyData.windspeed?.[currentIdx]
        ? Math.round(hourlyData.windspeed[currentIdx] * 2.237)
        : 0,
      humidity: hourlyData.relativehumidity?.[currentIdx] || 0,
      snowFraction: hourlyData.snowfraction?.[currentIdx] || 0
    }

    return {
      resortId: resort.id,
      source: 'meteoblue',
      lastUpdated: new Date().toISOString(),
      coordinates: { lat, lng },
      elevation,
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
    console.error(`Meteoblue error for ${resort.name}:`, error)
    return null
  }
}

export default {
  fetchMeteoblueWeather
}
