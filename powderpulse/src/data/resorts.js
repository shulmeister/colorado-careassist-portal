// Resort data for Epic and Ikon pass mountains worldwide
// Summit GPS coordinates for accurate weather forecasts
// Distances calculated from Boulder, CO (40.0150, -105.2705)

export const PASS_TYPES = {
  EPIC: 'epic',
  IKON: 'ikon',
  BOTH: 'both'
}

export const REGIONS = {
  COLORADO: 'colorado',
  NEW_MEXICO: 'new-mexico',
  UTAH: 'utah',
  CALIFORNIA: 'california',
  IDAHO: 'idaho',
  WYOMING: 'wyoming',
  MONTANA: 'montana',
  ALASKA: 'alaska',
  MAINE: 'maine',
  VERMONT: 'vermont',
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
    // Summit: China Bowl summit (11,570 ft)
    latitude: 39.6220,
    longitude: -106.3890,
    elevation: 11570,
    baseElevation: 8120,
    distanceFromBoulder: 97,
    timezone: 'America/Denver',
    liftieId: 'vail',
    webcamUrl: 'https://www.vail.com/the-mountain/mountain-conditions/mountain-cams.aspx',
    description: 'Legendary terrain, back bowls'
  },
  {
    id: 'beaver-creek',
    name: 'Beaver Creek',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    // Summit: Birds of Prey (11,440 ft)
    latitude: 39.5870,
    longitude: -106.5320,
    elevation: 11440,
    baseElevation: 8100,
    distanceFromBoulder: 107,
    timezone: 'America/Denver',
    liftieId: 'beaver-creek',
    webcamUrl: 'https://www.beavercreek.com/the-mountain/mountain-conditions/mountain-cams.aspx',
    description: 'Luxury resort, great groomers'
  },
  {
    id: 'breckenridge',
    name: 'Breckenridge',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    // Summit: Imperial Express top (12,998 ft)
    latitude: 39.4630,
    longitude: -106.0750,
    elevation: 12998,
    baseElevation: 9600,
    distanceFromBoulder: 80,
    timezone: 'America/Denver',
    liftieId: 'breckenridge',
    webcamUrl: 'https://www.breckenridge.com/the-mountain/mountain-conditions/mountain-cams.aspx',
    description: 'Historic town, diverse terrain'
  },
  {
    id: 'keystone',
    name: 'Keystone',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    // Summit: The Outback top (12,408 ft)
    latitude: 39.5770,
    longitude: -105.9780,
    elevation: 12408,
    baseElevation: 9280,
    distanceFromBoulder: 75,
    timezone: 'America/Denver',
    liftieId: 'keystone',
    webcamUrl: 'https://www.keystoneresort.com/the-mountain/mountain-conditions/mountain-cams.aspx',
    description: 'Night skiing, family friendly'
  },
  {
    id: 'crested-butte',
    name: 'Crested Butte',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    // Summit: High Lift top (12,162 ft)
    latitude: 38.8840,
    longitude: -106.9780,
    elevation: 12162,
    baseElevation: 9375,
    distanceFromBoulder: 200,
    timezone: 'America/Denver',
    liftieId: 'crested-butte',
    webcamUrl: 'https://www.skicb.com/the-mountain/mountain-conditions/mountain-cams.aspx',
    description: 'Extreme terrain, charming town'
  },
  {
    id: 'telluride',
    name: 'Telluride',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    // Summit: Revelation Bowl (13,150 ft)
    latitude: 37.9280,
    longitude: -107.8350,
    elevation: 13150,
    baseElevation: 8725,
    distanceFromBoulder: 330,
    timezone: 'America/Denver',
    liftieId: 'telluride',
    webcamUrl: 'https://www.tellurideskiresort.com/the-mountain/conditions-weather/webcams/',
    description: 'Box canyon beauty, expert terrain'
  },
  // IKON PASS - COLORADO
  {
    id: 'winter-park',
    name: 'Winter Park',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    // Summit: Parsenn Bowl (12,060 ft)
    latitude: 39.8670,
    longitude: -105.7850,
    elevation: 12060,
    baseElevation: 9000,
    distanceFromBoulder: 67,
    timezone: 'America/Denver',
    liftieId: 'winter-park',
    webcamUrl: 'https://www.winterparkresort.com/the-mountain/mountain-report/web-cams',
    description: 'Mary Jane bumps, great value'
  },
  {
    id: 'steamboat',
    name: 'Steamboat',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    // Summit: Mt. Werner summit (10,568 ft)
    latitude: 40.4850,
    longitude: -106.7720,
    elevation: 10568,
    baseElevation: 6900,
    distanceFromBoulder: 157,
    timezone: 'America/Denver',
    liftieId: 'steamboat',
    webcamUrl: 'https://www.steamboat.com/the-mountain/live-cams',
    description: 'Champagne powder, tree skiing'
  },
  {
    id: 'copper-mountain',
    name: 'Copper Mountain',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    // Summit: Tucker Mountain (12,313 ft)
    latitude: 39.4820,
    longitude: -106.1680,
    elevation: 12313,
    baseElevation: 9712,
    distanceFromBoulder: 83,
    timezone: 'America/Denver',
    liftieId: 'copper-mountain',
    webcamUrl: 'https://www.coppercolorado.com/the-mountain/conditions-weather/web-cams',
    description: 'Naturally divided terrain'
  },
  {
    id: 'arapahoe-basin',
    name: 'Arapahoe Basin',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    // Summit: Lenawee Mountain (13,050 ft)
    latitude: 39.6380,
    longitude: -105.8720,
    elevation: 13050,
    baseElevation: 10780,
    distanceFromBoulder: 65,
    timezone: 'America/Denver',
    liftieId: 'arapahoe-basin',
    webcamUrl: 'https://www.arapahoebasin.com/the-mountain/webcams/',
    description: 'Longest season, expert terrain'
  },
  {
    id: 'eldora',
    name: 'Eldora',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    // Summit: Corona lift top (10,800 ft)
    latitude: 39.9450,
    longitude: -105.5920,
    elevation: 10800,
    baseElevation: 9200,
    distanceFromBoulder: 21,
    timezone: 'America/Denver',
    liftieId: 'eldora',
    webcamUrl: 'https://www.eldora.com/the-mountain/conditions-hours/webcams',
    description: 'Closest resort, quick trips'
  },
  {
    id: 'aspen-snowmass',
    name: 'Aspen Snowmass',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    // Summit: Snowmass High Alpine (12,510 ft)
    latitude: 39.1880,
    longitude: -106.9680,
    elevation: 12510,
    baseElevation: 8104,
    distanceFromBoulder: 160,
    timezone: 'America/Denver',
    liftieId: 'snowmass',
    webcamUrl: 'https://www.aspensnowmass.com/four-mountains/mountain-conditions/webcams',
    description: 'Four mountains, world class'
  },
  {
    id: 'wolf-creek',
    name: 'Wolf Creek',
    pass: PASS_TYPES.IKON,
    region: REGIONS.COLORADO,
    // Summit: Alberta Peak (11,904 ft)
    latitude: 37.4750,
    longitude: -106.8030,
    elevation: 11904,
    baseElevation: 10300,
    distanceFromBoulder: 280,
    timezone: 'America/Denver',
    liftieId: null,
    webcamUrl: 'https://wolfcreekski.com/snow-conditions/',
    description: 'Most snow in Colorado, no crowds'
  },

  // ==================== NEW MEXICO ====================
  {
    id: 'taos',
    name: 'Taos Ski Valley',
    pass: PASS_TYPES.IKON,
    region: REGIONS.NEW_MEXICO,
    // Summit: Kachina Peak (12,481 ft)
    latitude: 36.5850,
    longitude: -105.4650,
    elevation: 12481,
    baseElevation: 9207,
    distanceFromBoulder: 280,
    timezone: 'America/Denver',
    liftieId: 'taos-ski-valley',
    webcamUrl: 'https://www.skitaos.com/conditions-cams/webcams',
    description: 'Steep terrain, authentic culture'
  },

  // ==================== UTAH ====================
  {
    id: 'snowbird',
    name: 'Snowbird',
    pass: PASS_TYPES.IKON,
    region: REGIONS.UTAH,
    // Summit: Hidden Peak (11,000 ft)
    latitude: 40.5600,
    longitude: -111.6580,
    elevation: 11000,
    baseElevation: 7760,
    distanceFromBoulder: 525,
    timezone: 'America/Denver',
    liftieId: 'snowbird',
    webcamUrl: 'https://www.snowbird.com/mountain-report/',
    description: 'Deep powder, steep terrain'
  },
  {
    id: 'alta',
    name: 'Alta',
    pass: PASS_TYPES.IKON,
    region: REGIONS.UTAH,
    // Summit: Mt. Baldy (10,550 ft)
    latitude: 40.5920,
    longitude: -111.6350,
    elevation: 10550,
    baseElevation: 8530,
    distanceFromBoulder: 525,
    timezone: 'America/Denver',
    liftieId: 'alta',
    webcamUrl: 'https://www.alta.com/conditions/webcams',
    description: 'Skiers only, legendary powder'
  },

  // ==================== CALIFORNIA ====================
  {
    id: 'mammoth',
    name: 'Mammoth Mountain',
    pass: PASS_TYPES.IKON,
    region: REGIONS.CALIFORNIA,
    // Summit: Mammoth Mountain top (11,053 ft)
    latitude: 37.6310,
    longitude: -119.0370,
    elevation: 11053,
    baseElevation: 7953,
    distanceFromBoulder: 850,
    timezone: 'America/Los_Angeles',
    liftieId: 'mammoth-mountain',
    webcamUrl: 'https://www.mammothmountain.com/mountain-information/webcams',
    description: 'Longest season in CA, massive terrain'
  },
  {
    id: 'palisades-tahoe',
    name: 'Palisades Tahoe',
    pass: PASS_TYPES.IKON,
    region: REGIONS.CALIFORNIA,
    // Summit: Granite Chief (9,050 ft)
    latitude: 39.2020,
    longitude: -120.2550,
    elevation: 9050,
    baseElevation: 6200,
    distanceFromBoulder: 900,
    timezone: 'America/Los_Angeles',
    liftieId: 'palisades-tahoe',
    webcamUrl: 'https://www.palisadestahoe.com/mountain-information/webcams',
    description: 'Olympic history, Lake Tahoe views'
  },
  {
    id: 'kirkwood',
    name: 'Kirkwood',
    pass: PASS_TYPES.IKON,
    region: REGIONS.CALIFORNIA,
    // Summit: Thimble Peak (9,800 ft)
    latitude: 38.6920,
    longitude: -120.0750,
    elevation: 9800,
    baseElevation: 7800,
    distanceFromBoulder: 900,
    timezone: 'America/Los_Angeles',
    liftieId: 'kirkwood',
    webcamUrl: 'https://www.kirkwood.com/the-mountain/mountain-conditions/mountain-cams.aspx',
    description: 'Steep chutes, deep snow, no crowds'
  },
  {
    id: 'sugar-bowl',
    name: 'Sugar Bowl',
    pass: PASS_TYPES.IKON,
    region: REGIONS.CALIFORNIA,
    // Summit: Mt. Lincoln (8,383 ft)
    latitude: 39.3120,
    longitude: -120.3420,
    elevation: 8383,
    baseElevation: 6883,
    distanceFromBoulder: 920,
    timezone: 'America/Los_Angeles',
    liftieId: 'sugar-bowl',
    webcamUrl: 'https://www.sugarbowl.com/conditions',
    description: 'Historic Tahoe resort, classic skiing'
  },

  // ==================== IDAHO ====================
  {
    id: 'sun-valley',
    name: 'Sun Valley',
    pass: PASS_TYPES.IKON,
    region: REGIONS.IDAHO,
    // Summit: Bald Mountain summit (9,150 ft)
    latitude: 43.6670,
    longitude: -114.3680,
    elevation: 9150,
    baseElevation: 5750,
    distanceFromBoulder: 580,
    timezone: 'America/Boise',
    liftieId: 'sun-valley',
    webcamUrl: 'https://www.sunvalley.com/mountain/webcams',
    description: 'Historic resort, world-class grooming'
  },

  // ==================== WYOMING ====================
  {
    id: 'jackson-hole',
    name: 'Jackson Hole',
    pass: PASS_TYPES.IKON,
    region: REGIONS.WYOMING,
    // Summit: Rendezvous Mountain top (10,450 ft)
    latitude: 43.5980,
    longitude: -110.8480,
    elevation: 10450,
    baseElevation: 6311,
    distanceFromBoulder: 450,
    timezone: 'America/Denver',
    liftieId: 'jackson-hole',
    webcamUrl: 'https://www.jacksonhole.com/webcams',
    description: 'Expert terrain, Corbet\'s Couloir'
  },

  // ==================== MONTANA ====================
  {
    id: 'big-sky',
    name: 'Big Sky',
    pass: PASS_TYPES.IKON,
    region: REGIONS.MONTANA,
    // Summit: Lone Peak (11,166 ft)
    latitude: 45.2680,
    longitude: -111.4180,
    elevation: 11166,
    baseElevation: 6800,
    distanceFromBoulder: 650,
    timezone: 'America/Denver',
    liftieId: 'big-sky',
    webcamUrl: 'https://bigskyresort.com/conditions-webcams',
    description: 'Biggest skiing in America, uncrowded'
  },

  // ==================== ALASKA ====================
  {
    id: 'alyeska',
    name: 'Alyeska',
    pass: PASS_TYPES.IKON,
    region: REGIONS.ALASKA,
    // Summit: Mt. Alyeska top (3,939 ft)
    latitude: 60.9630,
    longitude: -149.1080,
    elevation: 3939,
    baseElevation: 250,
    distanceFromBoulder: 2800,
    timezone: 'America/Anchorage',
    liftieId: 'alyeska',
    webcamUrl: 'https://alyeskaresort.com/mountain/webcams/',
    description: 'Ocean views, extreme terrain, deep snow'
  },

  // ==================== MAINE ====================
  {
    id: 'sugarloaf',
    name: 'Sugarloaf',
    pass: PASS_TYPES.IKON,
    region: REGIONS.MAINE,
    // Summit: Sugarloaf Mountain (4,237 ft)
    latitude: 45.0450,
    longitude: -70.3080,
    elevation: 4237,
    baseElevation: 1417,
    distanceFromBoulder: 2100,
    timezone: 'America/New_York',
    liftieId: 'sugarloaf',
    webcamUrl: 'https://www.sugarloaf.com/mountain-info/webcams',
    description: 'Biggest skiing in the East, above treeline'
  },

  // ==================== VERMONT ====================
  {
    id: 'jay-peak',
    name: 'Jay Peak',
    pass: PASS_TYPES.IKON,
    region: REGIONS.VERMONT,
    // Summit: Jay Peak summit (3,968 ft)
    latitude: 44.9350,
    longitude: -72.4980,
    elevation: 3968,
    baseElevation: 1815,
    distanceFromBoulder: 2000,
    timezone: 'America/New_York',
    liftieId: 'jay-peak',
    webcamUrl: 'https://jaypeakresort.com/ski-ride/conditions/webcams',
    description: 'Most snow in the East, glades galore'
  },

  // ==================== CANADA ====================
  {
    id: 'whistler',
    name: 'Whistler Blackcomb',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.CANADA,
    // Summit: Whistler Peak (7,494 ft / 2284m)
    latitude: 50.0630,
    longitude: -122.9350,
    elevation: 7494,
    baseElevation: 2140,
    distanceFromBoulder: 1100,
    timezone: 'America/Vancouver',
    liftieId: 'whistler-blackcomb',
    webcamUrl: 'https://www.whistlerblackcomb.com/the-mountain/mountain-conditions/mountain-cams.aspx',
    description: 'Largest in North America'
  },
  {
    id: 'revelstoke',
    name: 'Revelstoke',
    pass: PASS_TYPES.IKON,
    region: REGIONS.CANADA,
    // Summit: Mount Mackenzie top (7,300 ft / 2225m)
    latitude: 51.0150,
    longitude: -118.1550,
    elevation: 7300,
    baseElevation: 1680,
    distanceFromBoulder: 950,
    timezone: 'America/Vancouver',
    liftieId: null,
    webcamUrl: 'https://www.revelstokemountainresort.com/mountain/webcams/',
    description: 'Longest vertical in NA, deep pow'
  },
  {
    id: 'kicking-horse',
    name: 'Kicking Horse',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.CANADA,
    // Summit: Blue Heaven (8,033 ft / 2450m)
    latitude: 51.2880,
    longitude: -117.0550,
    elevation: 8033,
    baseElevation: 3900,
    distanceFromBoulder: 920,
    timezone: 'America/Edmonton',
    liftieId: null,
    webcamUrl: 'https://kickinghorseresort.com/conditions/cams/',
    description: 'Champagne powder, big mountain'
  },

  // ==================== JAPAN ====================
  {
    id: 'niseko',
    name: 'Niseko United',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.JAPAN,
    // Summit: Mt. Annupuri top (4,291 ft / 1308m)
    latitude: 42.87,
    longitude: 140.679,
    elevation: 4291,
    baseElevation: 1640,
    distanceFromBoulder: 5800,
    timezone: 'Asia/Tokyo',
    liftieId: 'niseko',
    webcamUrl: 'https://www.niseko.ne.jp/en/livecam/',
    description: 'Legendary powder, Japanese culture'
  },

  // ==================== EUROPE ====================
  {
    id: 'chamonix',
    name: 'Chamonix',
    pass: PASS_TYPES.IKON,
    region: REGIONS.EUROPE,
    // Summit: Aiguille du Midi area (12,605 ft / 3842m)
    latitude: 45.8780,
    longitude: 6.8870,
    elevation: 12605,
    baseElevation: 3396,
    distanceFromBoulder: 5300,
    timezone: 'Europe/Paris',
    liftieId: 'chamonix',
    webcamUrl: 'https://www.chamonix.com/webcams,106,en.html',
    description: 'Mont Blanc, extreme terrain'
  },
  {
    id: 'verbier',
    name: 'Verbier',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.EUROPE,
    // Summit: Mont Fort (10,925 ft / 3330m)
    latitude: 46.0820,
    longitude: 7.2880,
    elevation: 10925,
    baseElevation: 4921,
    distanceFromBoulder: 5350,
    timezone: 'Europe/Zurich',
    liftieId: 'verbier',
    webcamUrl: 'https://www.verbier.ch/en/webcams/',
    description: 'Swiss Alps, freeride paradise'
  },
  {
    id: 'val-disere',
    name: 'Val d\'Isère',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.EUROPE,
    // Summit: Rocher de Bellevarde (9,186 ft / 2800m)
    latitude: 45.4230,
    longitude: 6.9820,
    elevation: 9186,
    baseElevation: 6004,
    distanceFromBoulder: 5320,
    timezone: 'Europe/Paris',
    liftieId: 'val-disere',
    webcamUrl: 'https://www.valdisere.com/en/webcams/',
    description: 'French Alps, Olympic history'
  },
  {
    id: 'st-anton',
    name: 'St. Anton',
    pass: PASS_TYPES.IKON,
    region: REGIONS.EUROPE,
    // Summit: Valluga (9,222 ft / 2811m)
    latitude: 47.1580,
    longitude: 10.2180,
    elevation: 9222,
    baseElevation: 4275,
    distanceFromBoulder: 5400,
    timezone: 'Europe/Vienna',
    liftieId: 'st-anton-am-arlberg',
    webcamUrl: 'https://www.stantonamarlberg.com/en/winter/webcams',
    description: 'Birthplace of alpine skiing'
  },
  {
    id: 'cervinia',
    name: 'Cervinia',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.EUROPE,
    // Summit: Plateau Rosa (11,417 ft / 3480m)
    latitude: 45.9330,
    longitude: 7.7080,
    elevation: 11417,
    baseElevation: 6726,
    distanceFromBoulder: 5380,
    timezone: 'Europe/Rome',
    liftieId: 'cervino-ski-paradise',
    webcamUrl: 'https://www.cervinia.it/en/webcam',
    description: 'Matterhorn views, high altitude'
  },
  {
    id: 'courmayeur',
    name: 'Courmayeur',
    pass: PASS_TYPES.IKON,
    region: REGIONS.EUROPE,
    // Summit: Cresta d'Arp (9,186 ft / 2800m)
    latitude: 45.8120,
    longitude: 6.9480,
    elevation: 9186,
    baseElevation: 4016,
    distanceFromBoulder: 5310,
    timezone: 'Europe/Rome',
    liftieId: null,
    webcamUrl: 'https://www.courmayeur-montblanc.com/en/webcam',
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

// Helper to calculate snow for a day range
const getSnowForRange = (weatherData, resortId, startDay, endDay) => {
  const forecast = weatherData[resortId]?.dailyForecast || []
  return forecast.slice(startDay, endDay).reduce((sum, d) => sum + (d.snowfall || 0), 0)
}

// Sort resorts
export const sortResorts = (resortList, sortBy, weatherData = {}) => {
  const sorted = [...resortList]

  switch (sortBy) {
    case 'snow24h':
      return sorted.sort((a, b) => {
        const aSnow = weatherData[a.id]?.snow24h || 0
        const bSnow = weatherData[b.id]?.snow24h || 0
        return bSnow - aSnow
      })
    case 'snow5':
      return sorted.sort((a, b) => {
        const aSnow = getSnowForRange(weatherData, a.id, 0, 5)
        const bSnow = getSnowForRange(weatherData, b.id, 0, 5)
        return bSnow - aSnow
      })
    case 'snow10':
      return sorted.sort((a, b) => {
        const aSnow = getSnowForRange(weatherData, a.id, 0, 10)
        const bSnow = getSnowForRange(weatherData, b.id, 0, 10)
        return bSnow - aSnow
      })
    case 'snow15':
      return sorted.sort((a, b) => {
        const aSnow = getSnowForRange(weatherData, a.id, 0, 15)
        const bSnow = getSnowForRange(weatherData, b.id, 0, 15)
        return bSnow - aSnow
      })
    case 'snow6to10':
      return sorted.sort((a, b) => {
        const aSnow = getSnowForRange(weatherData, a.id, 5, 10)
        const bSnow = getSnowForRange(weatherData, b.id, 5, 10)
        return bSnow - aSnow
      })
    case 'snow11to15':
      return sorted.sort((a, b) => {
        const aSnow = getSnowForRange(weatherData, a.id, 10, 15)
        const bSnow = getSnowForRange(weatherData, b.id, 10, 15)
        return bSnow - aSnow
      })
    case 'snow':
    case 'snow7':
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
        const regionOrder = ['colorado', 'new-mexico', 'utah', 'california', 'idaho', 'wyoming', 'montana', 'alaska', 'maine', 'vermont', 'canada', 'japan', 'europe']
        return regionOrder.indexOf(a.region) - regionOrder.indexOf(b.region)
      })
    default:
      return sorted
  }
}
