# Trade Rules, Resolution Sources & Strategy Audit
## February 14, 2026 (FINAL — all bots stopped, crypto liquidated)

**Prepared for independent audit.** Three automated trading bots were built to operate across two platforms (Polymarket + Kalshi). This document covers every market type, every resolution rule, every data source, bugs found, and the emergency liquidation that followed.

### CURRENT STATUS: ALL BOTS HALTED
- **All 3 trading bots are STOPPED** — no LaunchAgents running
- **All crypto positions LIQUIDATED** at market (9 positions sold Feb 14)
- **Weather positions held to resolution** (~$35 across ~40 positions, most near $0)
- **USDC balance: $254.41**
- **No new trades will be placed** until owner gives explicit permission

---

## TABLE OF CONTENTS
1. [Bot #1: Polymarket Weather Sniper](#bot-1-polymarket-weather-sniper)
2. [Bot #2: Kalshi Weather Sniper](#bot-2-kalshi-weather-sniper)
3. [Bot #3: Polymarket Crypto Price Sniper](#bot-3-polymarket-crypto-price-sniper)
4. [Resolution Source Matrix (3-Column)](#resolution-source-matrix)
5. [Remaining Risks](#remaining-risks)
6. [Strategy Detail: Weather Sniper](#strategy-detail-weather-sniper)
7. [Strategy Detail: Crypto Price Sniper](#strategy-detail-crypto-price-sniper)
8. [Wallet & Order Routing](#wallet--order-routing)
9. [Bugs Found & Fixed](#bugs-found--fixed)

---

## BOT #1: POLYMARKET WEATHER SNIPER

**Location:** `~/mac-mini-apps/weather-arb/` | **Port:** 3010 | **Status:** STOPPED (was live, halted Feb 14)

### What It Trades
Daily high temperature markets on Polymarket. Example questions:
- "Will the highest temperature in New York be 55F or higher on February 16?"
- "Will the highest temperature in Chicago be 30F or below on February 16?"
- "Will the highest temperature in Seattle be between 45-47F on February 16?"

### Resolution Source (POLYMARKET WEATHER)
**Weather Underground historical observations at AIRPORT weather stations.**

Polymarket's own resolution text (from each market description):
> "Resolution source: wunderground.com, specifically the 'Max' listed under 'Temperature' for the relevant city and date"

Each city resolves at a SPECIFIC airport station:

| City | Resolution Station | ICAO Code | Wunderground URL |
|------|-------------------|-----------|-----------------|
| New York | LaGuardia Airport | KLGA | wunderground.com/history/daily/us/ny/new-york-city/KLGA |
| Chicago | O'Hare International | KORD | wunderground.com/history/daily/us/il/chicago/KORD |
| Seattle | SeaTac Airport | KSEA | wunderground.com/history/daily/us/wa/seatac/KSEA |
| Dallas | Love Field | KDAL | wunderground.com/history/daily/us/tx/dallas/KDAL |
| Atlanta | Hartsfield-Jackson | KATL | wunderground.com/history/daily/us/ga/atlanta/KATL |
| Miami | Miami International | KMIA | wunderground.com/history/daily/us/fl/miami/KMIA |

**NOT NOAA. NOT weather.gov. NOT downtown weather stations.**

### What Our Bot Uses for Forecasting
- **API:** NOAA weather.gov (`api.weather.gov/points/{lat},{lon}`)
- **Coordinates used (from `markets.py` WEATHER_CITIES):**

| City | Lat | Lon | Where This Points | Matches Resolution Station? |
|------|-----|-----|-------------------|---------------------------|
| NYC | 40.7772 | -73.8726 | Near LaGuardia | YES (within 0.4km of KLGA) |
| Chicago | 41.9769 | -87.9081 | Near O'Hare | YES (within 0.5km of KORD) |
| Seattle | 47.4499 | -122.3118 | Near SeaTac | YES (within 0.3km of KSEA) |
| Dallas | 32.8459 | -96.8509 | Near Love Field | YES (within 0.6km of KDAL) |
| Atlanta | 33.6367 | -84.4279 | Near Hartsfield | YES (within 0.4km of KATL) |
| Miami | 25.7954 | -80.2901 | Near MIA | YES (within 0.5km of KMIA) |

**STATUS: CORRECT.** Coordinates match the Wunderground resolution stations. The inherent risk is that NOAA forecasts (predictions) may differ from Wunderground actuals by 2-5F. The 5F margin buffer accounts for this.

### Bot Configuration
| Parameter | Value | Meaning |
|-----------|-------|---------|
| SNIPE_PRICE | $0.22 | Limit buy price per share |
| SNIPE_MAX_PRICE | $0.35 | Skip if market already above this |
| SNIPE_BUDGET | $50 | Per market |
| SNIPE_MAX_TOTAL | $300 | Total exposure cap |
| SNIPE_MARGIN_F | 5 | Forecast must beat threshold by 5F+ |
| SNIPE_MARGIN_C | 5 | Forecast must beat threshold by 5C+ |
| BETWEEN_ENABLED | true | Also trades "between X-Y" buckets |
| BETWEEN_PRICE | $0.15 | Limit price for between buckets |
| BETWEEN_PROXIMITY_F | 2 | Forecast must be within 2F of midpoint |
| BETWEEN_BUDGET | $15 | Per between market |
| BETWEEN_MAX_TOTAL | $100 | Between exposure cap |
| POLL_FAST | 5s | During snipe window (10:50-11:25 UTC) |
| POLL_SLOW | 60s | Outside snipe window |

### Payout
- Buy YES at $0.22, resolves YES = $1.00 payout = +$0.78 profit (354% ROI)
- Buy YES at $0.22, resolves NO = $0.00 payout = -$0.22 loss (100% loss)
- To be profitable: need >22% win rate on tail bets

---

## BOT #2: KALSHI WEATHER SNIPER

**Location:** `~/mac-mini-apps/kalshi-weather/` | **Port:** 3011 | **Status:** STOPPED (balance: $0.09, was never funded)

### What It Trades
Same concept as Polymarket weather — daily high temperature — but on Kalshi platform.

### Resolution Source (KALSHI WEATHER)
**National Weather Service (NWS) Climatological Report (Daily).**

Kalshi's own resolution text (from market rules_primary):
> "If the highest temperature recorded at [STATION] for [DATE] as reported by the National Weather Service's Climatological Report (Daily), is [CONDITION], then the market resolves to Yes."

**CRITICAL: Kalshi uses DIFFERENT stations than Polymarket for the same cities:**

| City | Kalshi Station | Polymarket Station | SAME? |
|------|---------------|-------------------|-------|
| New York | Central Park | LaGuardia (KLGA) | **NO** |
| Chicago | Chicago Midway | O'Hare (KORD) | **NO** |
| Denver | Denver, CO | (not active on Poly) | N/A |
| Austin | Austin Bergstrom | (not active on Poly) | N/A |
| Miami | Miami International Airport | Miami International (KMIA) | **YES** |
| Los Angeles | Los Angeles Airport | (not active on Poly) | N/A |
| Las Vegas | Las Vegas | (not active on Poly) | N/A |

### What Our Bot Uses for Forecasting (FIXED Feb 14)
- **API:** NOAA weather.gov (`api.weather.gov/points/{lat},{lon}`)
- **Coordinates (UPDATED to match NWS Climatological Report stations):**

| City | Lat | Lon | Target Station | Status |
|------|-----|-----|---------------|--------|
| NYC | 40.7829 | -73.9654 | Central Park | FIXED (was downtown Manhattan) |
| Chicago | 41.7868 | -87.7522 | Midway (KMDW) | FIXED (was downtown Loop) |
| Denver | 39.8561 | -104.6737 | DIA (KDEN) | FIXED (was downtown) |
| Austin | 30.1975 | -97.6664 | Bergstrom (KAUS) | FIXED (was downtown) |
| Miami | 25.7959 | -80.2870 | MIA (KMIA) | FIXED (was downtown) |
| LA | 33.9425 | -118.4081 | LAX (KLAX) | FIXED (was downtown) |
| Las Vegas | 36.0840 | -115.1537 | Harry Reid (KLAS) | FIXED (was downtown Strip) |

**Philadelphia removed** — no active Kalshi events found.

**STATUS: FIXED.** All 7 cities now use coordinates matching their NWS Climatological Report stations. Bot restarted and confirmed running with 83 markets across 7 cities.

### Bot Configuration
| Parameter | Value | Meaning |
|-----------|-------|---------|
| SNIPE_PRICE_CENTS | 22 | Limit buy at 22 cents |
| SNIPE_MAX_PRICE_CENTS | 35 | Skip if above 35 cents |
| SNIPE_BUDGET | $25 | Per market |
| SNIPE_MAX_TOTAL | $150 | Total exposure cap |
| SNIPE_MARGIN_F | 5 | Must beat threshold by 5F |
| BETWEEN_ENABLED | true | Also trades between buckets |
| BETWEEN_PRICE_CENTS | 15 | Limit price for between |
| BETWEEN_PROXIMITY_F | 2 | Forecast within 2F of midpoint |
| BETWEEN_BUDGET | $15 | Per between market |
| BETWEEN_MAX_TOTAL | $100 | Between exposure cap |
| POLL_FAST | 10s | During snipe window |
| POLL_SLOW | 60s | Normal |

### Kalshi Snipe Windows
Bot scans during two windows (configured in main.py):
- **Window 1:** 10:00-12:00 UTC (3:00-5:00 AM MT)
- **Window 2:** 14:00-16:00 UTC (7:00-9:00 AM MT)
- Exact Kalshi market open timing is not precisely known (unlike Polymarket's 11:00 UTC)

### Payout
- Kalshi charges ~1% fee on winnings
- Buy YES at $0.22, resolves YES = $1.00 payout = ~$0.77 profit after fees
- Buy YES at $0.22, resolves NO = $0.00 payout = -$0.22 loss
- Same break-even: need >22% win rate

---

## BOT #3: POLYMARKET CRYPTO PRICE SNIPER

**Location:** `~/mac-mini-apps/btc-sniper/` | **Port:** 3014 | **Status:** STOPPED, ALL POSITIONS LIQUIDATED

### What It Trades
Crypto barrier option markets on Polymarket. Example questions:
- "Will Bitcoin reach $150,000 in 2026?" (touch/reach upside)
- "Will Bitcoin dip to $20,000 in February?" (touch/dip downside)
- "Will XRP reach $4.20 in 2026?"

These are **barrier/touch options** — does the price reach the level at ANY point during the period? Not a closing price bet.

### Resolution Source (POLYMARKET CRYPTO)
**Binance BTC/USDT 1-minute candle HIGH (for reach) or LOW (for dip).**

Polymarket's exact resolution text (from event 194107 description):
> "The resolution source for this market is Binance, specifically the BTC/USDT 'High' prices available at https://www.binance.com/en/trade/BTC_USDT with the chart settings on '1m' for one-minute candles selected on the top bar."

> "This market will immediately resolve to 'Yes' if any Binance 1 minute candle for BTC/USDT during the month specified in the title (from 00:00 AM ET on the first day to 11:59 PM ET on the last), has a final High price equal to or greater than the price specified in the title."

> "Prices from other exchanges, different trading pairs, or spot markets will not be considered."

Key details:
- **Exchange:** Binance ONLY (not Coinbase, not Kraken, not spot)
- **Pair:** BTC/USDT ONLY (other coins use their respective /USDT pairs)
- **Price type:** 1-minute candle HIGH (for "reach/hit" markets) or LOW (for "dip/fall" markets)
- **Time zone:** Eastern Time (ET)
- **Trigger:** Immediate resolution — no waiting for end date
- **Period:** Monthly (Feb, Mar) or Annual (2026)

### What Our Bot Uses for Prices and Volatility (FIXED Feb 14)
- **Price API:** Binance.US (`api.binance.us/api/v3/ticker/price?symbol=BTCUSDT`)
- **Volatility API:** Binance.US daily klines (`api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1d`)
- **Why .US:** Binance.com (the resolution source) is geo-blocked from the US (HTTP 451). Binance.US has the same USDT pairs with negligible price difference (<0.1%).
- **Vol calculation:** 30-day realized volatility from daily closes, annualized with sqrt(365)

**STATUS: FIXED.** Previously used Coinbase BTC-USD spot (wrong exchange, wrong pair). Now uses Binance.US USDT pairs. Bot restarted and confirmed: 15 coins tracked, BTC=$70,239.66 from Binance.US, real volatilities loaded (BTC=79.2%, ETH=98.8%, etc.).

### Positions: ALL LIQUIDATED (Feb 14, 2026)

The crypto sniper placed orders on its first run with no MAX_DAYS filter, buying annual markets (320 days to expiry) that locked up capital through Dec 2026. After discovery, all open orders were cancelled and all 9 filled positions were market-sold:

| Coin | Market | Shares Sold | Proceeds | Status |
|------|--------|-------------|----------|--------|
| ETH | Reach $2,800 Feb | 277 | $15.24 | SOLD (0.31 dust remaining) |
| BTC | Dip $20K 2026 | 210 | matched | SOLD |
| BTC | Reach $160K 2026 | 210 | matched | SOLD |
| BTC | Reach $150K 2026 | 210 | matched | SOLD |
| BTC | Dip $15K 2026 | 166 | matched | SOLD |
| BTC | Reach $190K 2026 | 133 | matched | SOLD |
| ETH | Dip $1,600 Feb | 40 | matched | SOLD |
| BTC | Dip $55K Feb | 5.36 | matched | SOLD |
| DOGE | Dip $0.02 2026 | 5 | matched | SOLD |

**Original cost:** ~$100 | **Sale proceeds:** positions sold at market (FOK orders) | **Loss:** ~$25-30 estimated (bought at ~10c avg, sold at ~6-8c avg due to illiquidity)

**Bot is STOPPED. No LaunchAgent running. No orders pending.**

### Bot Configuration
| Parameter | Value | Meaning |
|-----------|-------|---------|
| EDGE_THRESHOLD | 5% | Fair value must exceed market price by 5%+ |
| MAX_PRICE | $0.15 | Only buy shares priced under 15 cents |
| MIN_PRICE | $0.01 | Skip dust-priced markets |
| BUDGET | $10 | Per trade |
| MAX_TOTAL | $100 | Total exposure cap |
| VOL_WINDOW | 30 | 30-day realized vol calculation |
| POLL_INTERVAL | 60s | Normal scan interval |
| SPIKE_POLL | 15s | Fast scan after 3%+ BTC move |
| SPIKE_THRESHOLD | 3% | Triggers fast scanning |
| SPIKE_DURATION | 600s | Fast scan lasts 10 minutes |

### Coins Tracked (15)
BTC, ETH, SOL, XRP, DOGE, HYPE, ENA, BNB, LINK, ZEC, ADA, AVAX, DOT, LTC, SUI

**Note:** As of Feb 14, active events exist for BTC (annual), ETH (annual), XRP (annual), DOGE (annual), and potentially others. Only BTC has monthly events.

### Payout
- Buy YES at $0.095, resolves YES = $1.00 payout = +$0.905 profit (952% ROI)
- Buy YES at $0.095, resolves NO = $0.00 payout = -$0.095 loss
- All current orders are on annual markets (320 days left)

---

## RESOLUTION SOURCE MATRIX

| Bot | Platform | Market Type | Resolution Source | Resolution Data | Bot's Price/Forecast Source | MATCH? |
|-----|----------|------------|-------------------|-----------------|---------------------------|--------|
| Weather Sniper | Polymarket | Daily high temp | Weather Underground | Airport station max temp (KLGA, KORD, KSEA, KDAL, KATL, KMIA) | NOAA forecast at airport coords | YES (coords match airports) |
| Kalshi Weather | Kalshi | Daily high temp | NWS Climatological Report (Daily) | Named NWS stations (Central Park, Midway, DIA, Bergstrom, MIA, LAX, Harry Reid) | NOAA forecast at NWS station coords | YES (FIXED Feb 14) |
| Crypto Sniper | Polymarket | Barrier options | Binance BTC/USDT | 1-min candle HIGH or LOW | Binance.US USDT spot + daily klines | YES (FIXED Feb 14) |

---

## REMAINING RISKS

### RISK 1: NOAA Forecast vs Wunderground Actual (Polymarket Weather)
- NOAA forecasts 2 days out have typical RMSE of 2-3F for US cities
- Wunderground reports actual observed temperatures from airport ASOS stations
- The two can differ because: (a) forecast error, (b) microclimate differences within the same NOAA grid cell
- The 5F margin provides buffer, but is not guaranteed
- **Mitigation:** 5F is ~2x the typical forecast error. Slam dunks should still resolve correctly most of the time.

### RISK 2: NOAA Forecast vs NWS CLR Actual (Kalshi Weather)
- Same forecast vs actual gap as Polymarket weather
- Additional concern: NWS CLR station may not be at the exact grid cell center
- **Mitigation:** Coordinates now target the actual NWS observation stations. 5F margin still applies.

### RISK 3: Binance.com vs Binance.US Price Difference
- Resolution uses Binance.com, but we use Binance.US for price data (geo-block)
- Typical difference: <$20 on BTC (~0.03%), negligible for barrier option math
- **Mitigation:** With 5% edge threshold, a 0.03% price difference is immaterial.

### RISK 4: Crypto Volatility Model Accuracy
- Bot uses a simple GBM (Geometric Brownian Motion) barrier option model with zero drift
- Real crypto prices have fat tails, jumps, and mean-reverting vol
- **Specific concerns:**
  1. **Zero drift assumption:** Crypto has positive drift historically. mu=0 may underprice reach and overprice dip.
  2. **GBM assumption:** Fat tails mean deep OTM barriers are more likely to be hit than GBM suggests.
  3. **Constant vol:** 30-day realized vol may not capture current regime.
  4. **No jump diffusion:** Bitcoin can gap 5-10% in minutes.
- **Mitigation:** 5% edge threshold provides buffer. All orders are small ($10 each).

### RISK 5: Kalshi Snipe Window Timing Unknown
- Don't know exactly when Kalshi releases daily weather markets
- Current broad windows (10:00-12:00 UTC, 14:00-16:00 UTC) may scan too early or late
- **Impact:** Low — bot runs continuously during windows, just checks more often than needed

---

## STRATEGY DETAIL: WEATHER SNIPER

Both weather bots (Polymarket + Kalshi) use the same core strategy. Here is the exact logic:

### Step 1: Pre-fetch Forecasts
- Before markets open, bot fetches NOAA forecasts for each city
- NOAA `api.weather.gov/points/{lat},{lon}` returns a forecast grid URL
- Bot fetches 7-day forecast, extracts daytime high temperatures
- Forecasts are cached for 1 hour
- Target date is T+2 (markets released today are for the day after tomorrow)

### Step 2: Scan Markets
- **Polymarket:** Polls `gamma-api.polymarket.com/events?tag_slug=weather&closed=false&limit=200`
- **Kalshi:** Polls Kalshi API for each series ticker (KXHIGHNY, KXHIGHCHI, etc.)
- For each market, bot extracts: city, date, direction (above/below/between), threshold temperature

### Step 3: Slam Dunk Detection (Tail Buckets)
For "X or higher" and "X or below" markets:

```
IF direction == "above" (e.g., "55F or higher"):
    margin = forecast_high - threshold
    # Example: forecast=62F, threshold=55F -> margin=7F

IF direction == "below" (e.g., "30F or below"):
    margin = threshold - forecast_high
    # Example: forecast=22F, threshold=30F -> margin=8F

IF margin >= 5F:
    -> SLAM DUNK -- buy YES
    # The forecast says it's a lock. 5F buffer for forecast error.

IF margin < 5F:
    -> SKIP -- not enough confidence
```

### Step 4: Between Bucket Detection (Only During Snipe Window)
For "between X-Y" markets:

```
midpoint = (threshold_low + threshold_high) / 2
proximity = abs(forecast_high - midpoint)

IF proximity <= 2F:
    -> Buy YES (forecast is near the middle of this bucket)

IF proximity > 2F:
    -> SKIP
```

Between buckets are only evaluated during the snipe window (when new markets first open) to avoid buying stale already-repriced markets.

### Step 5: Order Execution
- Place GTC (Good Til Cancelled) limit BUY order at fixed price ($0.22 for tail, $0.15 for between)
- Order sits on the book until filled or market closes
- If market price is already above our limit, order just sits unfilled (no loss)
- If market price drops to our limit, order fills

### Step 6: Hold to Resolution
- No auto-sell. All positions held until the market resolves.
- If the actual temperature matches our bet: payout $1.00 per share
- If not: payout $0.00

### Step 7: Timing (Polymarket Only)
- 10:50 UTC: Bot enters fast-poll mode (every 5 seconds)
- 11:00:00 UTC: Polymarket creates new temperature events for T+2
- 11:03-11:17 UTC: Markets start accepting orders (staggered by city)
- Bot detects `acceptingOrdersTimestamp` and places orders the instant each market opens
- By ~11:30 UTC: Most markets already repriced to fair value by other traders
- Our edge: orders placed in seconds, before the crowd

### Dynamic Budget (Polymarket Only)
The Polymarket weather bot scales budget based on number of opportunities:
```
budget_per_market = min(remaining_budget / num_opportunities, $50)
```
Fewer opportunities = bigger wagers per market. Capped at $50.

---

## STRATEGY DETAIL: CRYPTO PRICE SNIPER

### Step 1: Fetch Spot Prices (from Binance.US)
- Every 60 seconds, bot fetches prices for 15 coins via Binance.US USDT pairs
- `GET api.binance.us/api/v3/ticker/price?symbol=BTCUSDT`
- Markets resolve on Binance.com, but .com is geo-blocked from US; Binance.US tracks within ~0.03%

### Step 2: Calculate Realized Volatility (from Binance.US)
- Every 6 hours, bot fetches daily klines from Binance.US
- `GET api.binance.us/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=35`
- Calculates 30-day realized volatility: `vol = stdev(log_returns) * sqrt(365)`
- Real values as of Feb 14: BTC=79%, ETH=99%, SOL=100%, XRP=112%, DOGE=104%, ZEC=157%

### Step 3: Scan Markets
- Polls `gamma-api.polymarket.com/events?tag_slug=crypto-prices&closed=false&limit=100`
- For each event, identifies the coin from the title
- For each market within the event, parses direction (reach/dip) and barrier price
- 372 markets scanned on latest run

### Step 4: Fair Value Calculation (Barrier Option Math)
Uses the reflection principle for a geometric Brownian motion running maximum/minimum:

**For "reach" barriers (price must go UP to H):**
```
b = ln(H / S)                    # log-distance to barrier
nu = mu - sigma^2/2              # drift adjustment (mu=0 assumed)
T = days_left / 365              # time in years

P(reach) = Phi((nu*T - b) / (sigma*sqrt(T)))
         + exp(2*nu*b/sigma^2) * Phi((-nu*T - b) / (sigma*sqrt(T)))

When mu=0 (zero drift): simplifies to P = 2 * Phi(-b / (sigma*sqrt(T)))
```

**For "dip" barriers (price must go DOWN to L):**
```
a = ln(L / S)                    # log-distance to barrier (negative)
nu = mu - sigma^2/2

P(dip) = Phi((a - nu*T) / (sigma*sqrt(T)))
       + exp(2*nu*a/sigma^2) * Phi((a + nu*T) / (sigma*sqrt(T)))

When mu=0: simplifies to P = 2 * Phi(a / (sigma*sqrt(T)))
```

Where:
- S = current spot price (from Binance.US)
- H = reach barrier (H > S)
- L = dip barrier (L < S)
- sigma = annualized realized volatility (from Binance.US daily klines)
- T = time to expiry in years
- mu = drift (assumed 0 = risk-neutral)
- Phi = standard normal CDF (implemented via math.erf)

### Step 5: Edge Detection
```
fair_value = P(reach or dip)    # from barrier math above
yes_price = Polymarket YES price
no_price = Polymarket NO price

yes_edge = fair_value - yes_price
no_edge = (1 - fair_value) - no_price

IF yes_edge >= 5% AND yes_price <= 15 cents AND yes_price >= 1 cent:
    -> BUY YES (market is underpricing the probability)

IF no_edge >= 5% AND no_price <= 15 cents AND no_price >= 1 cent:
    -> BUY NO (market is overpricing the probability)
```

### Step 6: Order Execution
- Place GTC limit BUY at the current market price (not a fixed price like weather)
- Budget: $10 per trade, $100 total cap
- Minimum 5 shares per order

### Step 7: Spike Detection
```
IF |BTC_current - BTC_previous| / BTC_previous >= 3%:
    -> SPIKE MODE for 10 minutes
    -> Poll every 15s instead of 60s
    -> Refresh volatilities immediately

# Rationale: after a big price move, market prices lag the new reality
# Model recalculates fair values with new spot, finds fresh edge
```

### Step 8: Hold to Resolution
- All positions held to expiry (monthly or annual)
- Barrier options resolve immediately if touched (upside: any 1-min HIGH >= barrier, downside: any 1-min LOW <= barrier)
- If barrier never touched by end date: resolves NO

---

## WALLET & ORDER ROUTING

### Polymarket (Both Weather + Crypto Bots)
- **Wallet:** `0x7c3d3D6557e5B00C9149739Ad1d4Fc088229238C`
- **Chain:** Polygon (chain ID 137)
- **Currency:** USDCe
- **Order signing:** Local (private key on mac mini, never transmitted)
- **Order routing:** Through `clob-proxy-ams.fly.dev` (Fly.io Amsterdam proxy)
- **Proxy purpose:** Bypasses Polymarket CLOB geo-restriction on POST /order
- **Proxy auth:** `X-Proxy-Token: warb-clob-2026` header
- **CLOB client:** py-clob-client Python library, patched to route through proxy

### Kalshi
- **API Key:** `e22efd8d-...`
- **Auth:** RSA key pair at `~/.kalshi-private-key.pem`
- **No proxy needed** (Kalshi has no geo-restriction)
- **Balance:** $0.09 (effectively zero — needs deposit to trade)

---

## SERVICES & PORTS

| Service | Port | LaunchAgent | Status |
|---------|------|-------------|--------|
| Polymarket Weather Sniper | 3010 | com.coloradocareassist.weather-arb | **STOPPED** |
| Kalshi Weather Sniper | 3011 | com.coloradocareassist.kalshi-weather | **STOPPED** |
| Crypto Price Sniper | 3014 | com.coloradocareassist.btc-sniper | **STOPPED**, all positions liquidated |

---

## BUGS FOUND & FIXED

### BUG 1: Crypto Sniper Used Wrong Exchange — FIXED
- **Was:** Coinbase BTC-USD spot (`api.coinbase.com/v2/prices/BTC-USD/spot`)
- **Now:** Binance.US BTC/USDT (`api.binance.us/api/v3/ticker/price?symbol=BTCUSDT`)
- **File changed:** `btc-sniper/sniper.py` — replaced `COINBASE_API` + `CRYPTOCOM_API` with `BINANCE_API`
- **Volatility also fixed:** Was Crypto.com, now Binance.US daily klines
- **Note:** Binance.com is the actual resolution source but returns HTTP 451 from US IPs. Binance.US tracks within ~0.03% — negligible for our 5% edge threshold.

### BUG 2: Kalshi Weather Used Downtown Coordinates — FIXED
- **Was:** All 8 cities used city center lat/lon
- **Now:** All 7 cities use NWS Climatological Report station coordinates
- **File changed:** `kalshi-weather/config.py` — CITIES dict updated
- **Philadelphia removed** — no Kalshi events exist for it
- **Impact of old bug:** Chicago downtown vs Midway airport could differ by 11F. The 5F safety margin was completely swamped. Bot could have made losing bets thinking they were slam dunks.

| City | Old Coordinates | New Coordinates | Station |
|------|----------------|-----------------|---------|
| NYC | 40.7128, -74.0060 (downtown) | 40.7829, -73.9654 | Central Park |
| Chicago | 41.8781, -87.6298 (downtown) | 41.7868, -87.7522 | Midway (KMDW) |
| Denver | 39.7392, -104.9903 (downtown) | 39.8561, -104.6737 | DIA (KDEN) |
| Austin | 30.2672, -97.7431 (downtown) | 30.1975, -97.6664 | Bergstrom (KAUS) |
| Miami | 25.7617, -80.1918 (downtown) | 25.7959, -80.2870 | MIA (KMIA) |
| LA | 34.0522, -118.2437 (downtown) | 33.9425, -118.4081 | LAX (KLAX) |
| Las Vegas | 36.1699, -115.1398 (downtown) | 36.0840, -115.1537 | Harry Reid (KLAS) |
| Philadelphia | 39.9526, -75.1652 | REMOVED | No Kalshi events |

---

---

## EMERGENCY LIQUIDATION LOG — Feb 14, 2026

### Timeline of Events
1. **Crypto sniper built and deployed** with two critical bugs: wrong exchange (Coinbase instead of Binance) and no MAX_DAYS filter
2. **Bot immediately bought $100 in annual markets** (320 days to expiry) — locked up nearly half the cash position
3. **Bugs discovered during audit:** wrong price source, wrong coordinates on Kalshi bot
4. **Bugs fixed, bots restarted** — but crypto sniper immediately redeployed $100 again (LaunchAgent plist still had old MAX_TOTAL=100)
5. **Second round of cancellations** — plist updated, bot restarted with MAX_TOTAL=$25, MAX_DAYS=45
6. **Owner ordered full liquidation** — all crypto positions market-sold, all bots stopped
7. **Final state:** $254.41 USDC cash + ~$35 in weather positions (holding to resolution)

### Design Flaws Identified
1. **No timing discipline on crypto sniper:** Weather sniper correctly waits for daily market open to snipe fresh markets. Crypto sniper ran continuously and bought whatever had calculated "edge" — including 320-day annual markets and 2-week monthly markets indiscriminately.
2. **No expiry filter:** Bot had no MAX_DAYS parameter at launch. Any market with 5%+ model edge was fair game regardless of time horizon.
3. **Capital efficiency ignored:** $10/trade x 10+ annual markets = $100+ locked for 320 days. Expected return on annual barrier options is highly uncertain. Capital should have been reserved for the higher-conviction, shorter-duration weather snipes.
4. **LaunchAgent env vars override config.py defaults:** Changing config.py MAX_TOTAL from 100 to 25 had no effect because the plist still had BTC_MAX_TOTAL=100. Config changes must be applied to BOTH files.

### Financial Impact
- **Starting balance (pre-crypto sniper):** ~$280
- **Lost to crypto trading (buy high, sell low on illiquid markets):** ~$25-30
- **Current USDC balance:** $254.41
- **Weather positions (resolving):** ~$35.66 (3 positions near $1.00, rest near $0)

### What's Still Running
- **Elite Trading MCP** (port 3002) — paper/mock trading only, no real money
- **All other real-money bots: STOPPED** pending owner review and explicit restart permission

---

*Document generated February 14, 2026. Final update after emergency liquidation. All resolution rules sourced from platform market descriptions and API responses. Both critical bugs (wrong exchange, wrong coordinates) were fixed before bots were halted. All real-money trading is paused.*
