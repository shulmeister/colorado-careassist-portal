import { create } from 'zustand'
import { resorts, getResortsByPass, sortResorts } from '../data/resorts'
import { fetchAllResortsWeather } from '../services/weatherApi'
import {
  findMostSnow,
  findClosestSnow,
  findBestValue,
  getPowderAlertResorts
} from '../utils/helpers'

// Auto-refresh interval (30 minutes)
const REFRESH_INTERVAL = 30 * 60 * 1000

const useWeatherStore = create((set, get) => ({
  // Weather data
  weatherData: {},
  isLoading: true,
  error: null,
  lastUpdated: null,

  // Filters and sorting
  passFilter: 'all', // 'all', 'epic', 'ikon'
  sortBy: 'snow', // 'snow', 'distance', 'name', 'value'

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
      const weatherData = await fetchAllResortsWeather(resorts)

      set({
        weatherData,
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

  // Initialize and start auto-refresh
  initialize: () => {
    // Initial fetch
    get().fetchWeather()

    // Set up auto-refresh
    const refreshInterval = setInterval(() => {
      get().fetchWeather()
    }, REFRESH_INTERVAL)

    // Return cleanup function
    return () => clearInterval(refreshInterval)
  },

  // Manual refresh
  refresh: () => {
    get().fetchWeather()
  },

  // Get weather for a specific resort
  getResortWeather: (resortId) => {
    return get().weatherData[resortId] || null
  }
}))

export default useWeatherStore
