# Marketing Dashboard - Additional Metrics Analysis

## Overview
This document analyzes all marketing API integrations and identifies valuable additional metrics that could enhance the marketing dashboard.

---

## 1. Facebook/Instagram Metrics

### Currently Tracking:
- ✅ Page likes/followers
- ✅ Impressions & reach
- ✅ Post engagements (likes, comments, shares)
- ✅ Video views
- ✅ Click actions (directions, phone, website)
- ✅ Post-level metrics

### Recommended Additions:

#### **Audience Demographics** (High Value)
- **Age & Gender Breakdown**: Understand audience composition
- **Top Locations**: Geographic distribution of audience
- **Device Types**: Mobile vs Desktop engagement
- **Best Posting Times**: When audience is most active
- **API Endpoint**: `/{page_id}/insights` with `metric=page_fans_by_age_gender`, `page_fans_by_country`, etc.

#### **Engagement Quality Metrics** (Medium Value)
- **Engagement Rate**: (Engagements / Reach) × 100
- **Reaction Types Breakdown**: Like, Love, Haha, Wow, Sad, Angry
- **Comment Sentiment**: Positive/negative comment ratio (requires NLP)
- **Share Quality**: Shares vs comments ratio
- **API**: Already available in post insights

#### **Content Performance** (High Value)
- **Post Type Performance**: Photo vs Video vs Link posts
- **Top Performing Hashtags**: Which hashtags drive engagement
- **Content Themes**: Categorize posts and track theme performance
- **Story Metrics**: Views, exits, replies (24-hour window)
- **API**: `/{page_id}/posts` with expanded fields

#### **Video-Specific Metrics** (Medium Value)
- **Video Completion Rate**: % watched to end
- **Average Watch Time**: How long people watch
- **Video Engagement**: Reactions during video playback
- **API**: `/{post_id}/video_insights`

#### **Instagram-Specific** (High Value)
- **Stories Metrics**: Views, exits, replies, link clicks
- **Reels Performance**: Views, likes, comments, shares
- **IGTV Metrics**: Watch time, completion rate
- **Hashtag Performance**: Top hashtags by engagement
- **API**: Instagram Graph API insights

---

## 2. LinkedIn Metrics

### Currently Tracking:
- ✅ Impressions
- ✅ Clicks
- ✅ Likes, Comments, Shares
- ✅ **Reactions** (NEW - just added)
- ✅ **Audience Demographics** (NEW - just added)
- ✅ Follower count

### Recommended Additions:

#### **Content Performance** (High Value)
- **Post Type Performance**: Article vs Video vs Image posts
- **Best Posting Times**: Day of week and time analysis
- **Content Topics**: Track performance by topic/category
- **API**: Available in share statistics

#### **Engagement Quality** (Medium Value)
- **Engagement Rate by Post Type**: Compare article vs video engagement
- **Comment Quality**: Average comments per post
- **Share Reach**: How far shares extend reach
- **API**: Post-level insights

#### **Audience Growth** (High Value)
- **Follower Growth Rate**: Daily/weekly follower changes
- **Follower Demographics Over Time**: Track audience evolution
- **Unfollow Rate**: Track follower churn
- **API**: `organizationalEntityFollowerStatistics` with time series

#### **Video Metrics** (Medium Value)
- **Video Views**: Total and unique
- **Video Completion Rate**: % watched to end
- **Video Engagement**: Reactions during playback
- **API**: Video-specific insights

#### **Lead Generation** (High Value)
- **Lead Gen Form Completions**: If using LinkedIn Lead Gen Forms
- **Message Requests**: Direct messages from posts
- **Profile Views from Content**: Track-to-profile conversions
- **API**: Lead gen and messaging APIs

---

## 3. Pinterest Metrics

### Currently Tracking:
- ✅ Impressions
- ✅ Saves
- ✅ Pin clicks
- ✅ Outbound clicks
- ✅ Engagement rate
- ✅ Top pins
- ✅ Board metrics

### Recommended Additions:

#### **Audience Insights** (High Value)
- **Audience Demographics**: Age, gender, location
- **Interests**: What your audience is interested in
- **Device Types**: Mobile vs desktop usage
- **API**: `GET /user_account/analytics` with audience breakdown

#### **Content Performance** (High Value)
- **Pin Type Performance**: Standard vs video vs carousel
- **Board Performance**: Which boards drive most engagement
- **Seasonal Trends**: Performance by season/holiday
- **API**: Pin-level analytics with board grouping

#### **Traffic Quality** (Medium Value)
- **Click-Through Rate by Pin Type**: Compare standard vs video
- **Outbound Click Quality**: Which pins drive website traffic
- **Save-to-Click Ratio**: How saves convert to clicks
- **API**: Available in pin analytics

#### **Search Performance** (High Value)
- **Search Keywords**: What people search to find your pins
- **Trending Keywords**: Keywords gaining traction
- **Search Impressions**: How often pins appear in search
- **API**: Pinterest Search API (if available)

#### **Video Metrics** (Medium Value)
- **Video Views**: Total and unique
- **Video Completion Rate**: % watched to end
- **Video Saves**: How many people save videos
- **API**: Video pin analytics

---

## 4. TikTok Metrics

### Currently Tracking:
- ✅ Ad spend
- ✅ Impressions
- ✅ Clicks
- ✅ CTR, CPC
- ✅ Conversions
- ✅ Campaign-level metrics

### Recommended Additions:

#### **Organic Metrics** (High Value - Requires Creator API)
- **Follower Count**: Track growth
- **Profile Views**: How many view your profile
- **Video Views**: Total and unique
- **Likes, Comments, Shares**: Engagement metrics
- **Video Completion Rate**: Watch time metrics
- **API**: TikTok Creator API (separate from Ads API)

#### **Content Performance** (High Value)
- **Top Performing Videos**: By views, likes, shares
- **Best Posting Times**: When audience is most active
- **Hashtag Performance**: Which hashtags drive views
- **Sound/Music Performance**: Which sounds perform best
- **API**: Creator API analytics

#### **Audience Insights** (Medium Value)
- **Follower Demographics**: Age, gender, location
- **Follower Interests**: What your audience likes
- **Device Types**: Mobile vs desktop
- **API**: Creator API audience insights

#### **Ad Performance Enhancements** (Medium Value)
- **Video View Rate**: For video ads
- **Engagement Rate**: Likes/comments on ads
- **Audience Overlap**: Organic vs paid audience
- **API**: Enhanced Ads API metrics

---

## 5. Google Ads Metrics

### Currently Tracking:
- ✅ Spend (total & daily)
- ✅ Clicks, Impressions
- ✅ Conversions & conversion value
- ✅ CTR, CPC, CPM
- ✅ ROAS
- ✅ Campaign-level breakdown
- ✅ Cost per conversion

### Recommended Additions:

#### **Quality Score Metrics** (High Value)
- **Average Quality Score**: Overall account quality
- **Quality Score by Keyword**: Identify optimization opportunities
- **Expected CTR**: How ads are expected to perform
- **Ad Relevance**: How relevant ads are to keywords
- **Landing Page Experience**: Landing page quality
- **API**: `SELECT campaign.advertising_channel_type, ad_group_criterion.quality_info FROM ad_group_criterion`

#### **Search Terms Performance** (High Value)
- **Search Terms Report**: What people actually search
- **Wasteful Search Terms**: High spend, low conversion terms
- **Opportunity Search Terms**: Low spend, high potential terms
- **API**: `SELECT search_term_view.search_term, metrics FROM search_term_view`

#### **Device Performance** (Medium Value)
- **Performance by Device**: Desktop, Mobile, Tablet
- **Device-Specific CPC/CTR**: Optimize bids by device
- **Cross-Device Conversions**: Track multi-device journeys
- **API**: `SELECT segments.device FROM campaign` with device breakdown

#### **Time-Based Performance** (Medium Value)
- **Performance by Day of Week**: Best days to advertise
- **Performance by Hour**: Best times to show ads
- **Seasonal Trends**: Performance by month/season
- **API**: `SELECT segments.date, segments.day_of_week, segments.hour FROM campaign`

#### **Audience Performance** (High Value)
- **Audience Demographics**: Age, gender, household income
- **Affinity Audiences**: Interests and behaviors
- **In-Market Audiences**: Purchase intent signals
- **Custom Audiences**: Performance of uploaded lists
- **API**: `SELECT audience FROM campaign_audience_view`

#### **Ad Extensions Performance** (Medium Value)
- **Sitelink Performance**: Which sitelinks get clicks
- **Call Extension Performance**: Phone call metrics
- **Location Extension Performance**: Store visit metrics
- **Structured Snippet Performance**: Which snippets perform
- **API**: Extension-specific metrics

#### **Competitive Metrics** (Low-Medium Value)
- **Auction Insights**: Share of impressions vs competitors
- **Top Competitors**: Who you're competing against
- **Overlap Rate**: How often you compete
- **API**: `SELECT auction_insights FROM domain_category_view`

---

## 6. Google Analytics 4 (GA4) Metrics

### Currently Tracking:
- ✅ Total users
- ✅ Sessions
- ✅ Conversions & conversion rate
- ✅ Average session duration
- ✅ Engagement rate
- ✅ Bounce rate
- ✅ Users over time
- ✅ Sessions by source
- ✅ Conversions by source
- ✅ Top pages

### Recommended Additions:

#### **User Behavior Metrics** (High Value)
- **User Retention**: New vs returning users
- **User Lifetime Value**: LTV by acquisition source
- **Session Quality**: Engaged sessions vs bounces
- **Pages per Session**: How many pages users view
- **API**: `SELECT user_engagement, session_engaged, engaged_sessions FROM events`

#### **Conversion Funnel** (High Value)
- **Funnel Visualization**: Step-by-step conversion path
- **Drop-off Points**: Where users leave the funnel
- **Conversion Path Length**: How many sessions to convert
- **API**: `SELECT conversion_path FROM events WHERE event_name = 'conversion'`

#### **E-commerce Metrics** (If Applicable)
- **Revenue**: Total revenue from conversions
- **Average Order Value**: Revenue per conversion
- **Product Performance**: Top products by revenue
- **Cart Abandonment**: Add to cart vs purchase
- **API**: E-commerce events and parameters

#### **Traffic Source Quality** (High Value)
- **Source/Medium Performance**: Which sources drive quality traffic
- **Referral Sites**: Top referring websites
- **Social Media Traffic**: Performance by platform
- **Direct vs Organic**: Compare direct and search traffic
- **API**: Enhanced `sessions_by_source` with quality metrics

#### **Geographic Performance** (Medium Value)
- **Users by Country/City**: Geographic distribution
- **Conversion Rate by Location**: Best performing locations
- **Language Preferences**: User language breakdown
- **API**: `SELECT geo.country, geo.city FROM events`

#### **Technology Metrics** (Low-Medium Value)
- **Browser Performance**: Which browsers users use
- **OS Performance**: Desktop vs mobile OS
- **Screen Resolution**: Device display sizes
- **Connection Speed**: User connection quality
- **API**: `SELECT device.category, device.operating_system FROM events`

#### **Content Performance** (High Value)
- **Content Grouping**: Performance by content category
- **Scroll Depth**: How far users scroll
- **Time on Page**: Engagement per page
- **Exit Rate**: Which pages users exit from
- **API**: Enhanced page-level metrics

#### **Event Tracking** (High Value)
- **Custom Events**: Track specific user actions
- **Event Value**: Revenue/value from events
- **Event Funnels**: Track user journey through events
- **API**: Custom event parameters

---

## 7. Google Business Profile (GBP) Metrics

### Currently Tracking:
- ✅ Website clicks
- ✅ Phone calls
- ✅ Direction requests
- ✅ Business impressions (maps & search)
- ✅ Actions over time

### Recommended Additions:

#### **Search Performance** (High Value)
- **Search Keywords**: What people search to find you
- **Search Category Performance**: Which categories drive searches
- **Search vs Discovery**: How people find your business
- **API**: `getSearchKeywordImpressions` endpoint (if available)

#### **Photo Performance** (Medium Value)
- **Photo Views**: How many view your photos
- **Photo Engagement**: User interactions with photos
- **User-uploaded Photos**: Track customer photos
- **API**: Photo insights API

#### **Review Metrics** (High Value)
- **Review Count**: Total reviews
- **Average Rating**: Overall rating
- **Review Sentiment**: Positive vs negative reviews
- **Review Response Rate**: How often you respond
- **Review Response Time**: Average time to respond
- **API**: Reviews API

#### **Competitive Insights** (Medium Value)
- **Market Position**: Your ranking vs competitors
- **Share of Impressions**: Your % of category impressions
- **Competitor Comparison**: Compare metrics to competitors
- **API**: Competitive insights (if available)

#### **Location-Specific Metrics** (High Value)
- **Multi-Location Performance**: Compare locations
- **Location-Specific Actions**: Which locations drive most actions
- **Location Search Performance**: Location-specific keywords
- **API**: Multi-location aggregation

#### **Time-Based Insights** (Medium Value)
- **Peak Action Times**: When people call/click most
- **Day of Week Performance**: Best days for engagement
- **Seasonal Trends**: Performance by season
- **API**: Time-based breakdowns

---

## 8. Facebook Ads Metrics

### Currently Tracking:
- ✅ Spend
- ✅ Impressions, Clicks, Reach
- ✅ CPC, CPM, CTR
- ✅ Conversions
- ✅ Campaign-level breakdown
- ✅ Daily breakdown

### Recommended Additions:

#### **Audience Performance** (High Value)
- **Audience Demographics**: Age, gender, location
- **Custom Audience Performance**: How custom audiences perform
- **Lookalike Audience Performance**: Lookalike effectiveness
- **Interest Targeting Performance**: Which interests convert
- **API**: Audience insights and breakdowns

#### **Ad Creative Performance** (High Value)
- **Creative Type Performance**: Image vs Video vs Carousel
- **Ad Copy Performance**: Which headlines/descriptions work
- **Creative Fatigue**: When ads stop performing
- **A/B Test Results**: Creative test performance
- **API**: Ad creative insights

#### **Placement Performance** (Medium Value)
- **Performance by Placement**: Facebook vs Instagram vs Audience Network
- **Feed vs Stories Performance**: Compare feed and stories
- **Device Performance**: Mobile vs Desktop
- **API**: Placement breakdowns

#### **Attribution & Funnel** (High Value)
- **Attribution Windows**: First-click vs last-click
- **Multi-Touch Attribution**: Full customer journey
- **Funnel Performance**: Awareness → Consideration → Conversion
- **API**: Attribution insights

#### **Video Ad Metrics** (Medium Value)
- **Video View Rate**: % who watch video
- **Video Completion Rate**: % who watch to end
- **ThruPlay**: 15-second video views
- **Video Engagement**: Reactions during video
- **API**: Video-specific metrics

---

## Priority Recommendations

### 🔥 High Priority (High Business Value, Medium Implementation)
1. **Facebook/Instagram Audience Demographics** - Understand your audience
2. **LinkedIn Follower Growth Rate** - Track audience growth
3. **Google Ads Quality Score** - Optimize ad performance
4. **Google Ads Search Terms Report** - Find optimization opportunities
5. **GA4 User Retention** - Understand user loyalty
6. **GBP Review Metrics** - Track reputation
7. **GBP Search Keywords** - Understand local search

### ⚡ Medium Priority (Good Value, Easy Implementation)
1. **Facebook Post Type Performance** - Optimize content mix
2. **LinkedIn Best Posting Times** - Timing optimization
3. **Pinterest Audience Demographics** - Audience insights
4. **Google Ads Device Performance** - Device optimization
5. **GA4 Geographic Performance** - Location insights
6. **Facebook Ads Audience Performance** - Audience optimization

### 💡 Low Priority (Nice to Have, Complex Implementation)
1. **TikTok Organic Metrics** - Requires separate API
2. **Sentiment Analysis** - Requires NLP processing
3. **Competitive Insights** - Limited API availability
4. **Multi-Touch Attribution** - Complex data modeling

---

## Implementation Notes

### Easy Wins (Can add immediately):
- Facebook audience demographics (already available in API)
- LinkedIn follower growth (time series of existing metric)
- Google Ads device breakdown (add dimension to existing query)
- GA4 geographic data (add dimension to existing query)
- GBP review metrics (separate reviews API)

### Requires Additional API Access:
- TikTok organic metrics (Creator API)
- Instagram Stories insights (24-hour window)
- Pinterest search keywords (may require business account upgrade)

### Requires Data Processing:
- Sentiment analysis (NLP library)
- Content categorization (ML or manual tagging)
- Multi-touch attribution (data modeling)

---

*Last Updated: December 29, 2025*

