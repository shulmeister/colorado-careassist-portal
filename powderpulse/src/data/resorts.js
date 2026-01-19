// Resort data for Epic and Ikon pass mountains worldwide
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
  // Mid-mountain coordinates for more accurate weather forecasts
  {
    id: 'vail',
    name: 'Vail',
    pass: PASS_TYPES.EPIC,
    region: REGIONS.COLORADO,
    latitude: 39.6403,
    longitude: -106.3742,
    // Mid-mountain: Game Creek / Two Elk area (~10,350 ft)
    midMountain: { lat: 39.6350, lng: -106.3850 },
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
    latitude: 39.6042,
    longitude: -106.5165,
    // Mid-mountain: Spruce Saddle area (~10,000 ft)
    midMountain: { lat: 39.5980, lng: -106.5220 },
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
    latitude: 39.4817,
    longitude: -106.0384,
    // Mid-mountain: Peak 8 mid-station (~11,000 ft)
    midMountain: { lat: 39.4750, lng: -106.0550 },
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
    latitude: 39.6069,
    longitude: -105.9438,
    // Mid-mountain: Summit House area (~10,800 ft)
    midMountain: { lat: 39.5950, lng: -105.9550 },
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
    latitude: 38.8986,
    longitude: -106.9653,
    // Mid-mountain: Paradise Bowl area (~10,800 ft)
    midMountain: { lat: 38.8920, lng: -106.9700 },
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
    latitude: 37.9375,
    longitude: -107.8123,
    // Mid-mountain: See Forever / Prospect Bowl (~11,500 ft)
    midMountain: { lat: 37.9320, lng: -107.8200 },
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
    latitude: 39.8841,
    longitude: -105.7627,
    // Mid-mountain: Sunspot / Mary Jane (~10,700 ft)
    midMountain: { lat: 39.8750, lng: -105.7700 },
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
    latitude: 40.4572,
    longitude: -106.8045,
    // Mid-mountain: Thunderhead Lodge (~9,080 ft)
    midMountain: { lat: 40.4650, lng: -106.7800 },
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
    latitude: 39.5022,
    longitude: -106.1497,
    // Mid-mountain: Solitude Station (~11,000 ft)
    midMountain: { lat: 39.4950, lng: -106.1550 },
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
    latitude: 39.6426,
    longitude: -105.8719,
    // Mid-mountain: Black Mountain Lodge (~11,800 ft)
    midMountain: { lat: 39.6380, lng: -105.8750 },
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
    latitude: 39.9372,
    longitude: -105.5827,
    // Mid-mountain: Indian Peaks area (~10,400 ft)
    midMountain: { lat: 39.9400, lng: -105.5880 },
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
    latitude: 39.2084,
    longitude: -106.9490,
    // Mid-mountain: Big Burn area Snowmass (~10,500 ft)
    midMountain: { lat: 39.2100, lng: -106.9580 },
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
    latitude: 37.4697,
    longitude: -106.7934,
    // Mid-mountain: Alberta Peak area (~11,000 ft)
    midMountain: { lat: 37.4720, lng: -106.7980 },
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
    latitude: 36.5967,
    longitude: -105.4544,
    // Mid-mountain: Kachina Peak area (~11,000 ft)
    midMountain: { lat: 36.5920, lng: -105.4600 },
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
    latitude: 40.5830,
    longitude: -111.6538,
    // Mid-mountain: Mid-Gad area (~9,800 ft)
    midMountain: { lat: 40.5750, lng: -111.6580 },
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
    latitude: 40.5884,
    longitude: -111.6378,
    // Mid-mountain: Collins / Wildcat area (~9,600 ft)
    midMountain: { lat: 40.5880, lng: -111.6420 },
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
    latitude: 37.6308,
    longitude: -119.0326,
    // Mid-mountain: McCoy Station area (~10,000 ft)
    midMountain: { lat: 37.6400, lng: -119.0280 },
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
    latitude: 39.1969,
    longitude: -120.2358,
    // Mid-mountain: High Camp area (~8,200 ft)
    midMountain: { lat: 39.1980, lng: -120.2400 },
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
    latitude: 38.6850,
    longitude: -120.0653,
    // Mid-mountain: Cornice area (~8,800 ft)
    midMountain: { lat: 38.6880, lng: -120.0700 },
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
    latitude: 39.3048,
    longitude: -120.3344,
    // Mid-mountain: Mt. Lincoln area (~7,900 ft)
    midMountain: { lat: 39.3080, lng: -120.3380 },
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
    latitude: 43.6808,
    longitude: -114.3514,
    // Mid-mountain: Roundhouse area (~8,500 ft)
    midMountain: { lat: 43.6750, lng: -114.3600 },
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
    latitude: 43.5875,
    longitude: -110.8279,
    // Mid-mountain: Bridger Gondola mid-station (~9,095 ft)
    midMountain: { lat: 43.5950, lng: -110.8480 },
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
    latitude: 45.2857,
    longitude: -111.4018,
    // Mid-mountain: Lone Peak Tram mid-area (~9,800 ft)
    midMountain: { lat: 45.2800, lng: -111.4100 },
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
    latitude: 60.9697,
    longitude: -149.0981,
    // Mid-mountain: Glacier Bowl area (~2,500 ft)
    midMountain: { lat: 60.9650, lng: -149.1050 },
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
    latitude: 45.0314,
    longitude: -70.3131,
    // Mid-mountain: Bullwinkle's area (~3,500 ft)
    midMountain: { lat: 45.0350, lng: -70.3080 },
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
    latitude: 44.9279,
    longitude: -72.5046,
    // Mid-mountain: Tram mid-area (~3,200 ft)
    midMountain: { lat: 44.9320, lng: -72.5020 },
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
    latitude: 50.1163,
    longitude: -122.9574,
    // Mid-mountain: Roundhouse Lodge area (~6,000 ft / 1830m)
    midMountain: { lat: 50.0770, lng: -122.9500 },
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
    latitude: 51.0045,
    longitude: -118.1590,
    // Mid-mountain: Revelation Gondola mid (~5,500 ft)
    midMountain: { lat: 51.0100, lng: -118.1650 },
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
    latitude: 51.2977,
    longitude: -117.0479,
    // Mid-mountain: Eagle's Eye area (~6,500 ft)
    midMountain: { lat: 51.2950, lng: -117.0550 },
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
    latitude: 42.88,
    longitude: 140.75,
    // Mid-mountain: Hirafu mid-area (~2,600 ft / 800m)
    midMountain: { lat: 42.8650, lng: 140.6980 },
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
    latitude: 45.9237,
    longitude: 6.8694,
    // Mid-mountain: Plan de l'Aiguille (~7,500 ft / 2300m)
    midMountain: { lat: 45.9080, lng: 6.8880 },
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
    latitude: 46.0967,
    longitude: 7.2286,
    // Mid-mountain: Ruinettes area (~7,500 ft / 2300m)
    midMountain: { lat: 46.0920, lng: 7.2350 },
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
    latitude: 45.4481,
    longitude: 6.9769,
    // Mid-mountain: Solaise area (~8,000 ft / 2450m)
    midMountain: { lat: 45.4420, lng: 6.9850 },
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
    latitude: 47.1297,
    longitude: 10.2683,
    // Mid-mountain: Galzig area (~7,200 ft / 2200m)
    midMountain: { lat: 47.1250, lng: 10.2750 },
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
    latitude: 45.9336,
    longitude: 7.6319,
    // Mid-mountain: Plan Maison area (~9,000 ft / 2750m)
    midMountain: { lat: 45.9280, lng: 7.6380 },
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
    latitude: 45.7967,
    longitude: 6.9690,
    // Mid-mountain: Maison Vieille area (~7,500 ft / 2300m)
    midMountain: { lat: 45.8020, lng: 6.9580 },
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
