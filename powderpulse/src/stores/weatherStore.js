import { create } from 'zustand'
import { resorts, getResortsByPass, sortResorts } from '../data/resorts'
import { fetchAllResortsWeather } from '../services/weatherApi'
import { fetchAllLiftStatus } from '../services/liftieApi'
import {
  findMostSnow,
  findClosestSnow,
  findBestValue,
  getPowderAlertResorts
} from '../utils/helpers'

// Auto-refresh interval (15 minutes)
const REFRESH_INTERVAL = 15 * 60 * 1000

let refreshInterval = null

const useWeatherStore = create((set, get) => ({
  // Weather data
  weatherData: {},
  liftStatus: {},
  isLoading: true,
  error: null,
  lastUpdated: null,

  // Filters and sorting
  passFilter: 'all', // 'all', 'epic', 'ikon'
  sortBy: 'snow', // 'snow', 'distance', 'name', 'value', 'region'

  // Derived data
  filteredResorts: resorts,
  powderAlerts: [],
  stats: {
    mostSnow: null,
    closestSnow: null,
    bestValue: null
  },

  // Actions
  setPassFilter: (filter) => {
    set({ passFilter: filter })
    get().updateFilteredResorts()
  },

  setSortBy: (sortBy) => {
    set({ sortBy })
    get().updateFilteredResorts()
  },

  updateFilteredResorts: () => {
    const { passFilter, sortBy, weatherData } = get()
    const filtered = getResortsByPass(passFilter)
    const sorted = sortResorts(filtered, sortBy, weatherData)
    set({ filteredResorts: sorted })
  },

  updateStats: () => {
    const { weatherData } = get()
    set({
      stats: {
        mostSnow: findMostSnow(resorts, weatherData, 'snow7Day'),
        closestSnow: findClosestSnow(resorts, weatherData, 1),
        bestValue: findBestValue(resorts, weatherData)
      },
      powderAlerts: getPowderAlertResorts(resorts, weatherData)
    })
  },

  // Fetch weather data for all resorts
  fetchWeather: async () => {
    set({ isLoading: true, error: null })

    try {
      // Fetch weather and lift status in parallel
      const [weatherData, liftStatus] = await Promise.all([
        fetchAllResortsWeather(resorts),
        fetchAllLiftStatus(resorts)
      ])

      set({
        weatherData,
        liftStatus,
        lastUpdated: new Date().toISOString(),
        isLoading: false
      })

      // Update derived data
      get().updateFilteredResorts()
      get().updateStats()
    } catch (error) {
      console.error('Error fetching weather:', error)
      set({
        error: 'Failed to fetch weather data. Please try again.',
        isLoading: false
      })
    }
  },

  // Start auto-refresh
  startAutoRefresh: () => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
    }
    refreshInterval = setInterval(() => {
      get().fetchWeather()
    }, REFRESH_INTERVAL)
  },

  // Stop auto-refresh
  stopAutoRefresh: () => {
    if (refreshInterval) {
      clearInterval(refreshInterval)
      refreshInterval = null
    }
  },

  // Get weather for a specific resort
  getResortWeather: (resortId) => {
    return get().weatherData[resortId] || null
  },

  // Get lift status for a specific resort
  getResortLiftStatus: (resortId) => {
    return get().liftStatus[resortId] || null
  }
}))

export default useWeatherStore
