// Liftie API service for lift status
// Uses our backend proxy to bypass CORS restrictions

// Use backend proxy instead of direct Liftie API
const LIFTIE_PROXY_URL = '/api/liftie'

// Fetch lift status for a single resort
export const fetchLiftStatus = async (liftieId) => {
  if (!liftieId) return null

  try {
    const response = await fetch(`${LIFTIE_PROXY_URL}/${liftieId}`)
    if (!response.ok) {
      console.warn(`Liftie proxy error for ${liftieId}: ${response.status}`)
      return null
    }

    const data = await response.json()

    // Check for proxy error response
    if (data.error) {
      console.warn(`Liftie API error for ${liftieId}: ${data.error}`)
      return null
    }

    return {
      isOpen: data.open,
      lifts: {
        open: data.lifts?.stats?.open || 0,
        closed: data.lifts?.stats?.closed || 0,
        hold: data.lifts?.stats?.hold || 0,
        scheduled: data.lifts?.stats?.scheduled || 0,
        percentage: data.lifts?.stats?.percentage?.open || 0
      },
      weather: data.weather ? {
        temp: data.weather.temperature?.max,
        conditions: data.weather.conditions,
        text: data.weather.text
      } : null
    }
  } catch (error) {
    console.warn(`Failed to fetch lift status for ${liftieId}:`, error.message)
    return null
  }
}

// Fetch lift status for multiple resorts
// Uses batched requests with delays to avoid rate limiting
export const fetchAllLiftStatus = async (resorts) => {
  const liftStatus = {}
  const BATCH_SIZE = 5
  const BATCH_DELAY = 500 // 500ms between batches

  // Filter resorts that have liftieId
  const resortsWithLiftie = resorts.filter(r => r.liftieId)

  for (let i = 0; i < resortsWithLiftie.length; i += BATCH_SIZE) {
    const batch = resortsWithLiftie.slice(i, i + BATCH_SIZE)

    // Process batch in parallel
    const batchResults = await Promise.all(
      batch.map(async (resort) => {
        const status = await fetchLiftStatus(resort.liftieId)
        return { resortId: resort.id, status }
      })
    )

    // Store results
    batchResults.forEach(({ resortId, status }) => {
      if (status) {
        liftStatus[resortId] = status
      }
    })

    // Delay between batches (except for last batch)
    if (i + BATCH_SIZE < resortsWithLiftie.length) {
      await new Promise(resolve => setTimeout(resolve, BATCH_DELAY))
    }
  }

  return liftStatus
}

// Get status color based on percentage open
export const getLiftStatusColor = (percentage) => {
  if (percentage >= 80) return { bg: 'bg-green-500', text: 'text-green-400', label: 'Open' }
  if (percentage >= 20) return { bg: 'bg-yellow-500', text: 'text-yellow-400', label: 'Partial' }
  if (percentage > 0) return { bg: 'bg-red-500', text: 'text-red-400', label: 'Limited' }
  return { bg: 'bg-slate-600', text: 'text-slate-400', label: 'Closed' }
}
