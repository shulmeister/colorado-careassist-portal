// Resort data for Colorado Epic and Ikon pass mountains
// Distances calculated from Boulder, CO (40.0150, -105.2705)

export const PASS_TYPES = {
  EPIC: 'epic',
  IKON: 'ikon'
}

export const PASS_COLORS = {
  epic: {
    primary: '#0066CC',
    light: '#3B82F6',
    bg: 'rgba(0, 102, 204, 0.1)'
  },
  ikon: {
    primary: '#E31837',
    light: '#EF4444',
    bg: 'rgba(227, 24, 55, 0.1)'
  }
}

export const resorts = [
  // EPIC PASS RESORTS
  {
    id: 'vail',
    name: 'Vail',
    pass: PASS_TYPES.EPIC,
    latitude: 39.6403,
    longitude: -106.3742,
    elevation: 11570,
    distanceFromBoulder: 97,
    description: 'Legendary terrain, back bowls'
  },
  {
    id: 'beaver-creek',
    name: 'Beaver Creek',
    pass: PASS_TYPES.EPIC,
    latitude: 39.6042,
    longitude: -106.5165,
    elevation: 11440,
    distanceFromBoulder: 107,
    description: 'Luxury resort, great groomers'
  },
  {
    id: 'breckenridge',
    name: 'Breckenridge',
    pass: PASS_TYPES.EPIC,
    latitude: 39.4817,
    longitude: -106.0384,
    elevation: 12998,
    distanceFromBoulder: 80,
    description: 'Historic town, diverse terrain'
  },
  {
    id: 'keystone',
    name: 'Keystone',
    pass: PASS_TYPES.EPIC,
    latitude: 39.6069,
    longitude: -105.9438,
    elevation: 12408,
    distanceFromBoulder: 75,
    description: 'Night skiing, family friendly'
  },
  {
    id: 'crested-butte',
    name: 'Crested Butte',
    pass: PASS_TYPES.EPIC,
    latitude: 38.8986,
    longitude: -106.9653,
    elevation: 12162,
    distanceFromBoulder: 200,
    description: 'Extreme terrain, charming town'
  },
  {
    id: 'telluride',
    name: 'Telluride',
    pass: PASS_TYPES.EPIC,
    latitude: 37.9375,
    longitude: -107.8123,
    elevation: 13150,
    distanceFromBoulder: 330,
    description: 'Box canyon beauty, expert terrain'
  },

  // IKON PASS RESORTS
  {
    id: 'winter-park',
    name: 'Winter Park',
    pass: PASS_TYPES.IKON,
    latitude: 39.8841,
    longitude: -105.7627,
    elevation: 12060,
    distanceFromBoulder: 67,
    description: 'Mary Jane bumps, great value'
  },
  {
    id: 'steamboat',
    name: 'Steamboat',
    pass: PASS_TYPES.IKON,
    latitude: 40.4572,
    longitude: -106.8045,
    elevation: 10568,
    distanceFromBoulder: 157,
    description: 'Champagne powder, tree skiing'
  },
  {
    id: 'copper-mountain',
    name: 'Copper Mountain',
    pass: PASS_TYPES.IKON,
    latitude: 39.5022,
    longitude: -106.1497,
    elevation: 12313,
    distanceFromBoulder: 83,
    description: 'Naturally divided terrain'
  },
  {
    id: 'arapahoe-basin',
    name: 'Arapahoe Basin',
    pass: PASS_TYPES.IKON,
    latitude: 39.6426,
    longitude: -105.8719,
    elevation: 13050,
    distanceFromBoulder: 65,
    description: 'Longest season, expert terrain'
  },
  {
    id: 'eldora',
    name: 'Eldora',
    pass: PASS_TYPES.IKON,
    latitude: 39.9372,
    longitude: -105.5827,
    elevation: 10800,
    distanceFromBoulder: 21,
    description: 'Closest resort, quick trips'
  },
  {
    id: 'aspen-snowmass',
    name: 'Aspen Snowmass',
    pass: PASS_TYPES.IKON,
    latitude: 39.2084,
    longitude: -106.9490,
    elevation: 12510,
    distanceFromBoulder: 160,
    description: 'Four mountains, world class'
  }
]

// Get resort by ID
export const getResortById = (id) => resorts.find(r => r.id === id)

// Filter resorts by pass type
export const getResortsByPass = (passType) => {
  if (!passType || passType === 'all') return resorts
  return resorts.filter(r => r.pass === passType)
}

// Sort resorts
export const sortResorts = (resortList, sortBy, weatherData = {}) => {
  const sorted = [...resortList]

  switch (sortBy) {
    case 'snow':
      return sorted.sort((a, b) => {
        const aSnow = weatherData[a.id]?.snow7Day || 0
        const bSnow = weatherData[b.id]?.snow7Day || 0
        return bSnow - aSnow
      })
    case 'distance':
      return sorted.sort((a, b) => a.distanceFromBoulder - b.distanceFromBoulder)
    case 'name':
      return sorted.sort((a, b) => a.name.localeCompare(b.name))
    case 'value':
      return sorted.sort((a, b) => {
        const aSnow = weatherData[a.id]?.snow7Day || 0
        const bSnow = weatherData[b.id]?.snow7Day || 0
        const aValue = aSnow / (a.distanceFromBoulder || 1)
        const bValue = bSnow / (b.distanceFromBoulder || 1)
        return bValue - aValue
      })
    default:
      return sorted
  }
}
