# CLAUDE.md — Clawd: Gigi's Knowledge Base & Configuration

**Last Updated:** February 20, 2026
**Status:** Configuration & knowledge repository (not a running service)

---

## WHAT IS CLAWD?

Clawd is **NOT a separate running service**. It is:

1. **Gigi's Knowledge Base** — Jason's preferences, identity, memory context
2. **Elite Teams Configuration** — Team definitions and protocols
3. **Reference docs** — Concert automation plans, API configs, tool notes

**The actual Gigi AI runs in `careassist-unified`** (the Portal), not here.
Jason's preferences are injected into Gigi's system prompts in:
- `careassist-unified/gigi/telegram_bot.py` (Telegram, ask-gigi API, Siri, menubar, iMessage)
- `careassist-unified/gigi/voice_brain.py` (phone calls via Retell)
- `careassist-unified/gigi/ringcentral_bot.py` (SMS, DM, Team Chat)

**When you update preferences here, also update the system prompts in careassist-unified.**

---

## GIGI'S IDENTITY & SOUL

- **Name:** Gigi — named after Jason's youngest daughter
- **Role:** Chief of Staff, NOT a secretary or chatbot
- **Personality:** Direct, warm, competent. Gets things done. Doesn't waste words.
- **Manages:** Elite Teams (Finance, Tech, Marketing, Operations)
- **Philosophy:** Be genuinely helpful, not performatively helpful. Have opinions. Be resourceful before asking. Earn trust through competence.
- **Boundaries:** Private things stay private. Ask before acting externally. Never send half-baked replies. You're a guest in someone's life — treat it with respect.
- **Communication:** Concise when needed, thorough when it matters. No corporate drone. No sycophant. Just good.

### Operating Laws (hardcoded in all system prompts)
1. SIGNAL FILTERING — Only surface items requiring judgment or action
2. PREFERENCE LOCK — If you've seen a preference twice, it's policy
3. CONDITIONAL AUTONOMY — Act first on low-risk items
4. STATE AWARENESS — Adjust verbosity to the situation
5. OPINIONATED DECISIONS — Lead with recommendation + why
6. MEMORY — ONLY save facts explicitly stated
7. PATTERN DETECTION — Flag repeating problems
8. VOICE FIDELITY — Sound like a person
9. SELF-MONITORING — Correct yourself if drifting
10. PUSH BACK — Disagree respectfully when needed

---

## JASON'S PROFILE

- Owner of Colorado Care Assist, lives in Denver/Arvada, CO
- Phone: 603-997-1495 | Email: jason@coloradocareassist.com
- Family: Wife Jennifer, daughters Lucky, Ava, and Gigi
- Communication style: Sharp, efficient, no fluff. Wants things DONE. Give options with recommendations, not open-ended questions.
- Hates: half-finished work, having to re-explain, sycophantic language
- Philosophy: "King of the Deal" — wants the nicest possible for the least money. Loves getting $1000/night hotels for $500.

---

## MUSIC & CONCERTS (Jason goes to tons of shows)

### Listening Profile
Jason is DEEP in the jam band scene (90%+ of listening). Goes to "so many concerts." Will travel for shows. Takes family.

### Tier 1 — Core Rotation (Will Travel For)
- **Phish** — #1 favorite, travels to shows, knows the culture deeply
- **Goose** — HIGH priority (Red Rocks-sized shows)
- **Trey Anastasio** — Phish frontman solo
- **Billy Strings** — Modern bluegrass jam
- **Widespread Panic** — Southern jam legends
- **String Cheese Incident** — Colorado jam royalty

### Tier 2 — Heavy Rotation (Major Venues)
Spafford, Pigeons Playing Ping Pong, Dogs In A Pile, Disco Biscuits, Dopapod, moe., STS9, Lotus, Eggy

### Tier 3 — Regular Listening
The Motet, Galactic, Animal Liberation Orchestra, North Mississippi Allstars, Joe Russo's Almost Dead

### Jerry Garcia Appreciation
Grateful Dead (also wife likes), Jerry Garcia Band, Jerry Garcia solo

### Electronic / House (Secondary)
Dom Dolla, John Summit, Disco Lines, Oppidan, Sammy Virji, RAC, Penguin Prison, Tame Impala

### Indie / Alternative (Tertiary)
Gorillaz, Khruangbin, L'Imperatrice, The Parcels, Jesse Roper, Arc De Soleil

### Concert Alert Priority
- **RED ALERT** (text immediately): Tier 1-2 at ANY Colorado venue, Tier 2 at Red Rocks, electronic acts at Red Rocks
- **HIGH** (within 24h): The Motet, Galactic, JRAD, Dead & Co, RAC, Gorillaz, Khruangbin
- **MEDIUM** (weekly digest): L'Imperatrice, The Parcels, electronic festivals
- **ALWAYS NOTIFY:** Jam band festivals (Bonnaroo, Lockn, Peach, Summer Camp, Electric Forest, Global Dance)

### Colorado Venues
| Venue | Capacity | Notes |
|-------|----------|-------|
| Red Rocks | 9,525 | Goose, String Cheese, Widespread, STS9, house DJs |
| Mission Ballroom | 3,950 | Mid-tier jam bands, electronic |
| Ogden Theatre | 1,600 | Dogs In A Pile, smaller jam bands |
| Fillmore Auditorium | 3,900 | Similar to Mission |
| Bluebird Theater | ~500 | Small intimate shows |
| Gothic Theatre | ~1,100 | Indie/alternative |
| Levitt Pavilion | ~7,500 | Free summer concerts |

### Other Favorite Venues
Hollywood Bowl, Greek Theatre LA, Greek Theatre Berkeley, Santa Barbara Bowl, Frost Amphitheatre, The Gorge WA, St. Augustine Amphitheatre FL, Kettlehouse Amphitheater MT, The Sphere Vegas, Folsom Field Boulder

### Ticket Behavior
- Buys presale tickets, deals with queues regularly
- Uses Ticketmaster + AXS + venue-specific platforms
- Pain points: tons of presale emails, text codes, easy to miss sales
- Takes family: Lucky + Ava to shows, Jennifer to Phish

### Known Upcoming Shows (as of Feb 2026)
- Phish at The Sphere (Vegas) — April 2026 (first weekend with Lucky, third weekend with Jennifer)
- Folsom Field (Boulder) — Summer 2026
- Goose at Red Rocks — August 2026
- Goose at Kettlehouse (Montana) — August 2026
- Goose at Greek Theatre (LA) — August 2026 (with Lucky & Ava)

### NOT Primary Interest
Pop country, modern top 40, heavy metal

---

## PHISH KNOWLEDGE

### Band Members
- **Trey Anastasio** — Guitar, vocals, primary songwriter
- **Mike Gordon** — Bass, vocals
- **Jon Fishman** — Drums, vocals
- **Page McConnell** — Keyboards, vocals

### Famous Songs
**Staples:** You Enjoy Myself (YEM), Bathtub Gin, Tweezer, Divided Sky, Reba, David Bowie (original!), Mike's Song > I Am Hydrogen > Weekapaug Groove, Harry Hood, Stash, Run Like an Antelope
**Covers:** Loving Cup (Stones), Crosseyed and Painless (Talking Heads), Also Sprach Zarathustra
**Deep Cuts:** Fluffhead, Gumbo, Carini, Ghost

### Tour Lingo
- **Phan** — Phish fan
- **Couch Tour** — Watching livestream from home
- **Bust Out** — Song played for first time in many shows
- **Rage Side** — Vigorous dancing section
- **Lawn** — GA grass area at amphitheaters
- **Shakedown** — Vendor area outside shows
- **Run** — Multiple consecutive shows in same city
- **Holiday Run** — New Year's Eve multi-night event

### Annual Events
- New Year's Eve Run (usually MSG)
- Summer Tour (various US venues)
- Dick's Runs (Dick's Sporting Goods Park, CO — Labor Day weekend)

### Phish.net API
- **App ID:** `75728BE60984487598F9`
- **API Key:** `3ipzczi76ke84o`
- **Base URL:** `https://api.phish.net/v5`
- **Key endpoints:** `/shows/showdate/YYYY-MM-DD.json`, `/setlists/showdate/YYYY-MM-DD.json`, `/jamcharts/song/SONG-NAME.json`
- **Credentials location:** 1Password > "Phish.net API - Cosmic Song Explorer"

---

## TRAVEL & LOYALTY PROGRAMS

### Airlines
| Program | Status |
|---------|--------|
| United MileagePlus | **Premier Gold (LIFETIME)** — prefers United but watches cost |
| Delta SkyMiles | Member |
| JetBlue TrueBlue | Member |

### Rental Cars
| Program | Status |
|---------|--------|
| Hertz Gold Plus | Gold (skip the counter) |
| Avis Preferred | Preferred |

### Hotels
| Program | Status |
|---------|--------|
| Marriott Bonvoy | Gold Elite |

### Travel Security
| Program | Status |
|---------|--------|
| TSA PreCheck | Active |
| Passport | Valid through 11/20/2035 |

### Travel Style
- Efficient, no wasted time. Prefers direct flights.
- Wife loves fireplaces in hotel rooms
- Ski passes: Epic + Ikon
- Philosophy: nicest place possible for least money — loves deals and upgrades

---

## CONCERT TICKET AUTOMATION (Planning — Not Yet Implemented)

### The Vision
"Gigi — buy me two tickets to Dogs in a Pile at Ogden Theatre Saturday night" → Done.

### Phase 1: Email Monitoring (HIGHEST PRIORITY)
- Monitor Gmail for presale announcements, on-sale alerts, ticket confirmations
- Parse: artist, venue, date, presale time, sale time, codes
- Alert Jason BEFORE the sale starts
- Sources: Ticketmaster, AXS, Bandsintown, artist mailing lists, venue newsletters

### Phase 2: Presale Code Capture
- Capture presale codes from text messages (via iMessage/BlueBubbles)
- Associate codes with correct shows
- Have code ready at sale time

### Phase 3: Browser Automation (Semi-Automated)
- Playwright/Puppeteer for queue management
- CAPTCHA handling (2Captcha or human-in-loop)
- Gigi alerts Jason when it's his turn, or automates until CAPTCHA

### Phase 4: Full Voice Purchase (Ultimate Goal)
- Voice command → ticket purchased
- Safety: Gigi does everything except final click, sends screenshot, Jason confirms via text

### Platforms to Support
Ticketmaster, AXS (Red Rocks, Mission), Eventbrite, DICE, See Tickets, venue-specific

---

## SPOTIFY / MUSIC INTEGRATION STATUS

- **Spotify:** BLOCKED as of Jan 28, 2026. Spotify disabled new app creation.
- **Last.fm:** Recommended alternative. Simpler API (just API key, no OAuth). Already tracks Spotify listening. NOT yet implemented.
- **When Spotify unblocks:** Create app at developer.spotify.com, follow setup in git history (commit 9e311f9)

---

## ELITE TEAMS

Teams activated by "@team-name" or "team-name team":

| Team | Trigger | Config File |
|------|---------|-------------|
| Tech | `@tech-team` | `elite-teams/tech-team.md` |
| Marketing | `@marketing-team` | `elite-teams/marketing-team.md` |
| Finance | `@finance-team` | `elite-teams/finance-team.md` |
| Ops | `@ops-team` | `elite-teams/operations-team.md` |

---

## TOOL CONFIGS & API CREDENTIALS

### Retell AI (Voice Calls)
- **Business Agent (Gigi CCA):** `agent_5b425f858369d8df61c363d47f` (Custom LLM, 11labs Susan)
- **Personal Agent (Gigi for Jason):** `agent_e54167532428a1bc72c3375417`
- **Business Number:** +1-720-817-6600
- **Spare Number:** +1-719-427-4641
- **Jason's Number:** +1-603-997-1495

### Google Workspace
- Account: jason@coloradocareassist.com
- Services: Gmail, Calendar, Drive, Docs, Sheets

### Google Analytics 4
- Property ID: 445403783
- Project: cca-website-c822e

### Google Ads
- Customer ID: 6783005743
- Login Customer ID: 1446090150

### Brevo CRM
- Account: jason@coloradocareassist.com

### Google Drive Folder IDs
| Folder | Drive ID |
|--------|----------|
| Clawd Brain (root) | `1BQdXJXyIM81YBb6Sl64vNy_JH21_29NU` |
| Ideas/Business | `1Q-zCPX_mI9Mk1io0jTkVZ3HO5rBb3kpR` |
| Ideas/Travel | `1UQt9hIJqJDP7B8XzXF9rvSD1pD-1CZ5x` |
| Ideas/Projects | `1ekSZ5hjxwYuFPXu4NeTNC_g2RZMi_1H1` |
| Research | `14ASbNeTbQ0smWbrOCbT1I8FshqMZscGc` |
| Memory | `1nETOMGwsXVF-Egg1mfSYVDUJ97slfc_1` |

### QuickBooks Online
- CLI: `python3 ~/clawd/tools/quickbooks/qb.py <command>`
- Credentials: `~/clawd/credentials/quickbooks.json` (gitignored)

### All Credentials Location
`~/clawd/credentials/` — all gitignored:
- `brevo.env` — Brevo CRM API key
- `google-analytics.env` — GA4 & Google OAuth
- `google-ads.env` — Google Ads API credentials
- `quickbooks.json` — QuickBooks OAuth

---

## RELATED REPOS

| Repo | Purpose | Port |
|------|---------|------|
| **careassist-unified** | Gigi runtime, Portal, Sales, Recruiting | 8765 |
| **coloradocareassist** | Marketing website | 3000 |
| **hesedhomecare** | Hesed marketing website | 3001 |

---

## FOR CLAUDE CODE

When working in this repo:
1. **This is configuration, not runtime** — No services to restart here
2. **Preferences updated here MUST also be updated** in the system prompts in `careassist-unified/gigi/`
3. **Elite team changes** take effect when referenced by the running Gigi
4. **Memory updates** should be concise and actionable
