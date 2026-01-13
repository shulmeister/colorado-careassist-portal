// Resort data for Epic and Ikon pass mountains worldwide
// Distances calculated from Boulder, CO (40.0150, -105.2705)

export const PASS_TYPES = {
  EPIC: 'epic',
  IKON: 'ikon',
  BOTH: 'both'
}

export const REGIONS = {
  COLORADO: 'colorado',
  UTAH: 'utah',
  IDAHO: 'idaho',
  WYOMING: 'wyoming',
  CANADA: 'canada',
  JAPAN: 'japan',
  EUROPE: 'europe'
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
  },
  both: {
    primary: '#9333EA',
    light: '#A855F7',
    bg: 'rgba(147, 51, 234, 0.1)'
  }
}

export const resorts = [
  // ==================== COLORADO ====================
  // EPIC PASS
  {
    id: 'vail',
    name: 'Vail',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    latitude: 39.6403,
    longitude: -106.3742,
    elevation: 11570,
    distanceFromBoulder: 97,
    timezone: 'America/Denver',
    liftieId: 'vail',
    description: 'Legendary terrain, back bowls'
  },
  {
    id: 'beaver-creek',
    name: 'Beaver Creek',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    latitude: 39.6042,
    longitude: -106.5165,
    elevation: 11440,
    distanceFromBoulder: 107,
    timezone: 'America/Denver',
    liftieId: 'beaver-creek',
    description: 'Luxury resort, great groomers'
  },
  {
    id: 'breckenridge',
    name: 'Breckenridge',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    latitude: 39.4817,
    longitude: -106.0384,
    elevation: 12998,
    distanceFromBoulder: 80,
    timezone: 'America/Denver',
    liftieId: 'breckenridge',
    description: 'Historic town, diverse terrain'
  },
  {
    id: 'keystone',
    name: 'Keystone',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    latitude: 39.6069,
    longitude: -105.9438,
    elevation: 12408,
    distanceFromBoulder: 75,
    timezone: 'America/Denver',
    liftieId: 'keystone',
    description: 'Night skiing, family friendly'
  },
  {
    id: 'crested-butte',
    name: 'Crested Butte',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    latitude: 38.8986,
    longitude: -106.9653,
    elevation: 12162,
    distanceFromBoulder: 200,
    timezone: 'America/Denver',
    liftieId: 'crested-butte',
    description: 'Extreme terrain, charming town'
  },
  {
    id: 'telluride',
    name: 'Telluride',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    latitude: 37.9375,
    longitude: -107.8123,
    elevation: 13150,
    distanceFromBoulder: 330,
    timezone: 'America/Denver',
    liftieId: 'telluride',
    description: 'Box canyon beauty, expert terrain'
  },
  // IKON PASS - COLORADO
  {
    id: 'winter-park',
    name: 'Winter Park',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    latitude: 39.8841,
    longitude: -105.7627,
    elevation: 12060,
    distanceFromBoulder: 67,
    timezone: 'America/Denver',
    liftieId: 'winter-park',
    description: 'Mary Jane bumps, great value'
  },
  {
    id: 'steamboat',
    name: 'Steamboat',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    latitude: 40.4572,
    longitude: -106.8045,
    elevation: 10568,
    distanceFromBoulder: 157,
    timezone: 'America/Denver',
    liftieId: 'steamboat',
    description: 'Champagne powder, tree skiing'
  },
  {
    id: 'copper-mountain',
    name: 'Copper Mountain',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    latitude: 39.5022,
    longitude: -106.1497,
    elevation: 12313,
    distanceFromBoulder: 83,
    timezone: 'America/Denver',
    liftieId: 'copper-mountain',
    description: 'Naturally divided terrain'
  },
  {
    id: 'arapahoe-basin',
    name: 'Arapahoe Basin',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    latitude: 39.6426,
    longitude: -105.8719,
    elevation: 13050,
    distanceFromBoulder: 65,
    timezone: 'America/Denver',
    liftieId: 'arapahoe-basin',
    description: 'Longest season, expert terrain'
  },
  {
    id: 'eldora',
    name: 'Eldora',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    latitude: 39.9372,
    longitude: -105.5827,
    elevation: 10800,
    distanceFromBoulder: 21,
    timezone: 'America/Denver',
    liftieId: 'eldora',
    description: 'Closest resort, quick trips'
  },
  {
    id: 'aspen-snowmass',
    name: 'Aspen Snowmass',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    latitude: 39.2084,
    longitude: -106.9490,
    elevation: 12510,
    distanceFromBoulder: 160,
    timezone: 'America/Denver',
    liftieId: 'snowmass',
    description: 'Four mountains, world class'
  },
  {
    id: 'wolf-creek',
    name: 'Wolf Creek',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    latitude: 37.4697,
    longitude: -106.7934,
    elevation: 11904,
    distanceFromBoulder: 280,
    timezone: 'America/Denver',
    liftieId: null, // Not on Liftie
    description: 'Most snow in Colorado, no crowds'
  },

  // ==================== UTAH ====================
  {
    id: 'snowbird',
    name: 'Snowbird',
    pass: PASS_TYPES.IKON,
    region: REGIONS.UTAH,
    latitude: 40.5830,
    longitude: -111.6538,
    elevation: 11000,
    distanceFromBoulder: 525,
    timezone: 'America/Denver',
    liftieId: 'snowbird',
    description: 'Deep powder, steep terrain'
  },
  {
    id: 'alta',
    name: 'Alta',
    pass: PASS_TYPES.IKON,
    region: REGIONS.UTAH,
    latitude: 40.5884,
    longitude: -111.6378,
    elevation: 10550,
    distanceFromBoulder: 525,
    timezone: 'America/Denver',
    liftieId: 'alta',
    description: 'Skiers only, legendary powder'
  },

  // ==================== IDAHO ====================
  {
    id: 'sun-valley',
    name: 'Sun Valley',
    pass: PASS_TYPES.IKON,
    region: REGIONS.IDAHO,
    latitude: 43.6808,
    longitude: -114.3514,
    elevation: 9150,
    distanceFromBoulder: 580,
    timezone: 'America/Boise',
    liftieId: 'sun-valley',
    description: 'Historic resort, world-class grooming'
  },

  // ==================== WYOMING ====================
  {
    id: 'jackson-hole',
    name: 'Jackson Hole',
    pass: PASS_TYPES.IKON,
    region: REGIONS.WYOMING,
    latitude: 43.5875,
    longitude: -110.8279,
    elevation: 10450,
    distanceFromBoulder: 450,
    timezone: 'America/Denver',
    liftieId: 'jackson-hole',
    description: 'Expert terrain, Corbet\'s Couloir'
  },

  // ==================== CANADA ====================
  {
    id: 'whistler',
    name: 'Whistler Blackcomb',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.CANADA,
    latitude: 50.1163,
    longitude: -122.9574,
    elevation: 7494,
    distanceFromBoulder: 1100,
    timezone: 'America/Vancouver',
    liftieId: 'whistler-blackcomb',
    description: 'Largest in North America'
  },
  {
    id: 'revelstoke',
    name: 'Revelstoke',
    pass: PASS_TYPES.IKON,
    region: REGIONS.CANADA,
    latitude: 51.0045,
    longitude: -118.1590,
    elevation: 7300,
    distanceFromBoulder: 950,
    timezone: 'America/Vancouver',
    liftieId: null, // Not on Liftie
    description: 'Longest vertical in NA, deep pow'
  },
  {
    id: 'kicking-horse',
    name: 'Kicking Horse',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.CANADA,
    latitude: 51.2977,
    longitude: -117.0479,
    elevation: 8033,
    distanceFromBoulder: 920,
    timezone: 'America/Edmonton',
    liftieId: null, // Not on Liftie
    description: 'Champagne powder, big mountain'
  },

  // ==================== JAPAN ====================
  {
    id: 'niseko',
    name: 'Niseko United',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.JAPAN,
    latitude: 42.88,
    longitude: 140.75,
    elevation: 4291,
    distanceFromBoulder: 5800,
    timezone: 'Asia/Tokyo',
    liftieId: 'niseko',
    description: 'Legendary powder, Japanese culture'
  },

  // ==================== EUROPE ====================
  {
    id: 'chamonix',
    name: 'Chamonix',
    pass: PASS_TYPES.IKON,
    region: REGIONS.EUROPE,
    latitude: 45.9237,
    longitude: 6.8694,
    elevation: 12605,
    distanceFromBoulder: 5300,
    timezone: 'Europe/Paris',
    liftieId: 'chamonix',
    description: 'Mont Blanc, extreme terrain'
  },
  {
    id: 'verbier',
    name: 'Verbier',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.EUROPE,
    latitude: 46.0967,
    longitude: 7.2286,
    elevation: 10925,
    distanceFromBoulder: 5350,
    timezone: 'Europe/Zurich',
    liftieId: 'verbier',
    description: 'Swiss Alps, freeride paradise'
  },
  {
    id: 'val-disere',
    name: 'Val d\'Isère',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.EUROPE,
    latitude: 45.4481,
    longitude: 6.9769,
    elevation: 9186,
    distanceFromBoulder: 5320,
    timezone: 'Europe/Paris',
    liftieId: 'val-disere',
    description: 'French Alps, Olympic history'
  },
  {
    id: 'st-anton',
    name: 'St. Anton',
    pass: PASS_TYPES.IKON,
    region: REGIONS.EUROPE,
    latitude: 47.1297,
    longitude: 10.2683,
    elevation: 9222,
    distanceFromBoulder: 5400,
    timezone: 'Europe/Vienna',
    liftieId: 'st-anton-am-arlberg',
    description: 'Birthplace of alpine skiing'
  },
  {
    id: 'cervinia',
    name: 'Cervinia',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.EUROPE,
    latitude: 45.9336,
    longitude: 7.6319,
    elevation: 11417,
    distanceFromBoulder: 5380,
    timezone: 'Europe/Rome',
    liftieId: 'cervino-ski-paradise',
    description: 'Matterhorn views, high altitude'
  },
  {
    id: 'courmayeur',
    name: 'Courmayeur',
    pass: PASS_TYPES.IKON,
    region: REGIONS.EUROPE,
    latitude: 45.7967,
    longitude: 6.9690,
    elevation: 9186,
    distanceFromBoulder: 5310,
    timezone: 'Europe/Rome',
    liftieId: null, // Not on Liftie
    description: 'Mont Blanc, Italian charm'
  }
]

// Get resort by ID
export const getResortById = (id) => resorts.find(r => r.id === id)

// Filter resorts by pass type
export const getResortsByPass = (passType) => {
  if (!passType || passType === 'all') return resorts
  return resorts.filter(r => r.pass === passType)
}

// Filter resorts by region
export const getResortsByRegion = (region) => {
  if (!region || region === 'all') return resorts
  return resorts.filter(r => r.region === region)
}

// Get unique regions
export const getRegions = () => [...new Set(resorts.map(r => r.region))]

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
    case 'region':
      return sorted.sort((a, b) => {
        const regionOrder = ['colorado', 'utah', 'idaho', 'wyoming', 'canada', 'japan', 'europe']
        return regionOrder.indexOf(a.region) - regionOrder.indexOf(b.region)
      })
    default:
      return sorted
  }
}
