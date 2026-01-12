// Utility functions for PowderPulse

// Get snow amount color class based on inches
export const getSnowColorClass = (inches) => {
  if (inches === 0) return 'snow-none'
  if (inches < 1) return 'snow-none'
  if (inches < 3) return 'snow-light'
  if (inches < 6) return 'snow-moderate'
  if (inches < 12) return 'snow-heavy'
  if (inches < 18) return 'snow-epic'
  return 'snow-legendary'
}

// Get snow amount background color class
export const getSnowBgColorClass = (inches) => {
  if (inches === 0) return 'bg-snow-none'
  if (inches < 1) return 'bg-snow-none'
  if (inches < 3) return 'bg-snow-light'
  if (inches < 6) return 'bg-snow-moderate'
  if (inches < 12) return 'bg-snow-heavy'
  if (inches < 18) return 'bg-snow-epic'
  return 'bg-snow-legendary'
}

// Get hex color for snow amount (for charts)
export const getSnowHexColor = (inches) => {
  if (inches === 0) return '#94A3B8'
  if (inches < 1) return '#94A3B8'
  if (inches < 3) return '#60A5FA'
  if (inches < 6) return '#3B82F6'
  if (inches < 12) return '#2563EB'
  if (inches < 18) return '#1D4ED8'
  return '#7C3AED'
}

// Format snow amount with proper decimal places
export const formatSnowAmount = (inches) => {
  if (inches === 0) return '0"'
  if (inches < 1) return `${inches.toFixed(1)}"`
  return `${Math.round(inches)}"`
}

// Format temperature
export const formatTemp = (temp) => {
  if (temp === null || temp === undefined) return '--'
  return `${Math.round(temp)}°F`
}

// Format date for display
export const formatDate = (dateString) => {
  const date = new Date(dateString)
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric'
  })
}

// Format time for display
export const formatTime = (timeString) => {
  const date = new Date(timeString)
  return date.toLocaleTimeString('en-US', {
    hour: 'numeric',
    hour12: true
  })
}

// Get day name from date string
export const getDayName = (dateString) => {
  const date = new Date(dateString)
  const today = new Date()
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)

  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === tomorrow.toDateString()) return 'Tomorrow'

  return date.toLocaleDateString('en-US', { weekday: 'short' })
}

// Calculate snow per mile (value metric)
export const calculateSnowPerMile = (snowAmount, distance) => {
  if (!distance || distance === 0) return 0
  return snowAmount / distance
}

// Find resort with most snow
export const findMostSnow = (resorts, weatherData, period = 'snow7Day') => {
  let maxSnow = 0
  let maxResort = null

  resorts.forEach(resort => {
    const snow = weatherData[resort.id]?.[period] || 0
    if (snow > maxSnow) {
      maxSnow = snow
      maxResort = { ...resort, snow }
    }
  })

  return maxResort
}

// Find closest resort with snow
export const findClosestSnow = (resorts, weatherData, minSnow = 1) => {
  const resortsWithSnow = resorts
    .filter(r => (weatherData[r.id]?.snow48h || 0) >= minSnow)
    .sort((a, b) => a.distanceFromBoulder - b.distanceFromBoulder)

  if (resortsWithSnow.length === 0) return null

  const resort = resortsWithSnow[0]
  return {
    ...resort,
    snow: weatherData[resort.id]?.snow48h || 0
  }
}

// Find best value (most snow per mile driven)
export const findBestValue = (resorts, weatherData) => {
  let bestValue = 0
  let bestResort = null

  resorts.forEach(resort => {
    const snow = weatherData[resort.id]?.snow7Day || 0
    const value = calculateSnowPerMile(snow, resort.distanceFromBoulder)

    if (value > bestValue && snow >= 3) { // Minimum 3" to be considered
      bestValue = value
      bestResort = {
        ...resort,
        snow,
        value: value.toFixed(2)
      }
    }
  })

  return bestResort
}

// Get powder alert resorts (6"+ in 48 hours)
export const getPowderAlertResorts = (resorts, weatherData) => {
  return resorts
    .filter(r => weatherData[r.id]?.isPowderDay)
    .map(r => ({
      ...r,
      snow48h: weatherData[r.id]?.snow48h || 0
    }))
    .sort((a, b) => b.snow48h - a.snow48h)
}

// Calculate time since last update
export const getTimeSinceUpdate = (isoString) => {
  if (!isoString) return 'Never'

  const updated = new Date(isoString)
  const now = new Date()
  const diffMinutes = Math.floor((now - updated) / 60000)

  if (diffMinutes < 1) return 'Just now'
  if (diffMinutes < 60) return `${diffMinutes}m ago`

  const diffHours = Math.floor(diffMinutes / 60)
  if (diffHours < 24) return `${diffHours}h ago`

  return `${Math.floor(diffHours / 24)}d ago`
}

// Debounce function for search/filter
export const debounce = (func, wait) => {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}
