/**
 * Google Ads Script to fetch metrics and send to Marketing Dashboard
 * 
 * Setup Instructions:
 * 1. Go to Google Ads → Tools & Settings → Bulk Actions → Scripts
 * 2. Click the + button to create a new script
 * 3. Copy and paste this entire script
 * 4. Update the WEBHOOK_URL below with your backend URL
 * 5. Schedule to run daily (or as needed)
 * 
 * Note: This script uses UrlFetchApp which is available in Google Ads Scripts
 */

// ⚠️ UPDATE THIS URL TO YOUR BACKEND ENDPOINT
const WEBHOOK_URL = 'https://portal-coloradocareassist-3e1a4bb34793.mac-miniapp.com/api/marketing/google-ads/webhook';

// Secret key for authentication (optional but recommended)
// Set this in both the script and your backend WEBHOOK_SECRET env var
// ⚠️ UPDATE THIS with the secret from Mac Mini (Local): mac-mini config:get GOOGLE_ADS_WEBHOOK_SECRET --app portal-coloradocareassist
const WEBHOOK_SECRET = '36d65febabc5df0d2a67d6e604ff652de681b8923590425c298f1cd7ed6c80ff';

/**
 * Main function - runs when script executes
 */
function main() {
  Logger.log('Starting Google Ads metrics collection...');
  
  try {
    const metrics = collectMetrics();
    sendToWebhook(metrics);
    Logger.log('Successfully sent metrics to dashboard');
  } catch (error) {
    Logger.log('Error: ' + error.message);
    // Optionally send error notification
    sendErrorNotification(error);
  }
}

/**
 * Collect all Google Ads metrics
 */
function collectMetrics() {
  const today = new Date();
  const thirtyDaysAgo = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);
  
  const startDate = formatDate(thirtyDaysAgo);
  const endDate = formatDate(today);
  
  Logger.log(`Collecting metrics from ${startDate} to ${endDate}`);
  
  // Get account-level metrics (last 30 days)
  const accountMetrics = getAccountMetrics(startDate, endDate);
  
  // Get campaign-level data
  const campaigns = getCampaigns(startDate, endDate);
  
  // Get quality scores
  const qualityScores = getQualityScores();
  
  // Get search terms
  const searchTerms = getSearchTerms(startDate, endDate);
  
  // Get device performance
  const devicePerformance = getDevicePerformance(startDate, endDate);
  
  // Get daily breakdown
  const dailyBreakdown = getDailyBreakdown(startDate, endDate);
  
  return {
    customer_id: AdsApp.currentAccount().getCustomerId().replace(/-/g, ''),
    date_range: {
      start: startDate,
      end: endDate
    },
    account: accountMetrics,
    campaigns: campaigns,
    quality_scores: qualityScores,
    search_terms: searchTerms,
    device_performance: devicePerformance,
    daily_breakdown: dailyBreakdown,
    fetched_at: new Date().toISOString(),
    currency_code: AdsApp.currentAccount().getCurrencyCode() || 'USD'
  };
}

/**
 * Get account-level summary metrics
 */
function getAccountMetrics(startDate, endDate) {
  const query = `
    SELECT
      metrics.cost_micros,
      metrics.clicks,
      metrics.impressions,
      metrics.conversions,
      metrics.conversions_value,
      metrics.ctr,
      metrics.average_cpc
    FROM customer
    WHERE segments.date BETWEEN '${startDate}' AND '${endDate}'
  `;
  
  const report = AdsApp.report(query);
  const rows = report.rows();
  
  let totalCost = 0;
  let totalClicks = 0;
  let totalImpressions = 0;
  let totalConversions = 0;
  let totalConversionValue = 0;
  
  while (rows.hasNext()) {
    const row = rows.next();
    totalCost += parseFloat(row['metrics.cost_micros']) / 1000000;
    totalClicks += parseInt(row['metrics.clicks']);
    totalImpressions += parseInt(row['metrics.impressions']);
    totalConversions += parseFloat(row['metrics.conversions']);
    totalConversionValue += parseFloat(row['metrics.conversions_value']);
  }
  
  const ctr = totalImpressions > 0 ? (totalClicks / totalImpressions) * 100 : 0;
  const cpc = totalClicks > 0 ? totalCost / totalClicks : 0;
  const roas = totalCost > 0 ? totalConversionValue / totalCost : 0;
  const costPerConversion = totalConversions > 0 ? totalCost / totalConversions : 0;
  const conversionRate = totalClicks > 0 ? (totalConversions / totalClicks) * 100 : 0;
  
  return {
    spend: totalCost,
    clicks: totalClicks,
    impressions: totalImpressions,
    conversions: totalConversions,
    conversion_value: totalConversionValue,
    ctr: ctr,
    cpc: cpc,
    roas: roas,
    cost_per_conversion: costPerConversion,
    conversion_rate: conversionRate
  };
}

/**
 * Get campaign-level data
 */
function getCampaigns(startDate, endDate) {
  const query = `
    SELECT
      campaign.id,
      campaign.name,
      campaign.status,
      metrics.cost_micros,
      metrics.clicks,
      metrics.impressions,
      metrics.conversions,
      metrics.conversions_value,
      metrics.ctr,
      metrics.average_cpc
    FROM campaign
    WHERE segments.date BETWEEN '${startDate}' AND '${endDate}'
      AND campaign.status != 'REMOVED'
  `;
  
  const report = AdsApp.report(query);
  const rows = report.rows();
  
  const campaigns = [];
  const campaignMap = {};
  
  while (rows.hasNext()) {
    const row = rows.next();
    const campaignId = row['campaign.id'];
    
    if (!campaignMap[campaignId]) {
      campaignMap[campaignId] = {
        id: campaignId,
        name: row['campaign.name'],
        status: row['campaign.status'],
        spend: 0,
        clicks: 0,
        impressions: 0,
        conversions: 0,
        conversion_value: 0
      };
    }
    
    const campaign = campaignMap[campaignId];
    campaign.spend += parseFloat(row['metrics.cost_micros']) / 1000000;
    campaign.clicks += parseInt(row['metrics.clicks']);
    campaign.impressions += parseInt(row['metrics.impressions']);
    campaign.conversions += parseFloat(row['metrics.conversions']);
    campaign.conversion_value += parseFloat(row['metrics.conversions_value']);
  }
  
  // Convert to array and calculate derived metrics
  for (const campaignId in campaignMap) {
    const campaign = campaignMap[campaignId];
    campaign.roas = campaign.spend > 0 ? campaign.conversion_value / campaign.spend : 0;
    campaign.ctr = campaign.impressions > 0 ? (campaign.clicks / campaign.impressions) * 100 : 0;
    campaign.cpc = campaign.clicks > 0 ? campaign.spend / campaign.clicks : 0;
    campaign.cost_per_conversion = campaign.conversions > 0 ? campaign.spend / campaign.conversions : 0;
    campaigns.push(campaign);
  }
  
  // Sort by spend descending
  campaigns.sort((a, b) => b.spend - a.spend);
  
  return campaigns.slice(0, 50); // Top 50 campaigns
}

/**
 * Get quality scores
 */
function getQualityScores() {
  const query = `
    SELECT
      ad_group_criterion.keyword.text,
      ad_group_criterion.quality_info.quality_score,
      ad_group_criterion.quality_info.creative_quality_score,
      ad_group_criterion.quality_info.post_click_quality_score,
      ad_group_criterion.quality_info.search_predicted_ctr
    FROM keyword_view
    WHERE ad_group_criterion.type = 'KEYWORD'
      AND ad_group_criterion.status = 'ENABLED'
      AND ad_group_criterion.quality_info.quality_score IS NOT NULL
    LIMIT 1000
  `;
  
  const report = AdsApp.report(query);
  const rows = report.rows();
  
  let totalQualityScore = 0;
  let totalCreativeScore = 0;
  let totalLandingPageScore = 0;
  let totalPredictedCtr = 0;
  let count = 0;
  
  while (rows.hasNext()) {
    const row = rows.next();
    const qualityScore = parseInt(row['ad_group_criterion.quality_info.quality_score']);
    const creativeScore = row['ad_group_criterion.quality_info.creative_quality_score'];
    const landingPageScore = row['ad_group_criterion.quality_info.post_click_quality_score'];
    const predictedCtr = row['ad_group_criterion.quality_info.search_predicted_ctr'];
    
    if (qualityScore) {
      totalQualityScore += qualityScore;
      count++;
    }
    
    if (creativeScore) totalCreativeScore += parseQualityScore(creativeScore);
    if (landingPageScore) totalLandingPageScore += parseQualityScore(landingPageScore);
    if (predictedCtr) totalPredictedCtr += parseQualityScore(predictedCtr);
  }
  
  return {
    average_quality_score: count > 0 ? totalQualityScore / count : 0,
    average_creative_score: count > 0 ? totalCreativeScore / count : 0,
    average_landing_page_score: count > 0 ? totalLandingPageScore / count : 0,
    average_predicted_ctr: count > 0 ? totalPredictedCtr / count : 0,
    keywords_analyzed: count
  };
}

/**
 * Parse quality score enum to number
 */
function parseQualityScore(score) {
  const scores = {
    'UNKNOWN': 0,
    'BELOW_AVERAGE': 1,
    'AVERAGE': 2,
    'ABOVE_AVERAGE': 3
  };
  return scores[score] || 0;
}

/**
 * Get search terms
 */
function getSearchTerms(startDate, endDate) {
  const query = `
    SELECT
      search_term_view.search_term,
      metrics.cost_micros,
      metrics.clicks,
      metrics.impressions,
      metrics.conversions
    FROM search_term_view
    WHERE segments.date BETWEEN '${startDate}' AND '${endDate}'
      AND metrics.impressions > 0
    ORDER BY metrics.cost_micros DESC
    LIMIT 100
  `;
  
  const report = AdsApp.report(query);
  const rows = report.rows();
  
  const searchTerms = [];
  
  while (rows.hasNext()) {
    const row = rows.next();
    const cost = parseFloat(row['metrics.cost_micros']) / 1000000;
    const clicks = parseInt(row['metrics.clicks']);
    
    searchTerms.push({
      search_term: row['search_term_view.search_term'],
      cost: cost,
      clicks: clicks,
      impressions: parseInt(row['metrics.impressions']),
      conversions: parseFloat(row['metrics.conversions']),
      cpc: clicks > 0 ? cost / clicks : 0
    });
  }
  
  return searchTerms;
}

/**
 * Get device performance breakdown
 */
function getDevicePerformance(startDate, endDate) {
  const query = `
    SELECT
      segments.device,
      metrics.cost_micros,
      metrics.clicks,
      metrics.impressions,
      metrics.conversions,
      metrics.conversions_value
    FROM campaign
    WHERE segments.date BETWEEN '${startDate}' AND '${endDate}'
  `;
  
  const report = AdsApp.report(query);
  const rows = report.rows();
  
  const devices = {
    'DESKTOP': { spend: 0, clicks: 0, impressions: 0, conversions: 0, conversion_value: 0 },
    'MOBILE': { spend: 0, clicks: 0, impressions: 0, conversions: 0, conversion_value: 0 },
    'TABLET': { spend: 0, clicks: 0, impressions: 0, conversions: 0, conversion_value: 0 }
  };
  
  while (rows.hasNext()) {
    const row = rows.next();
    const device = row['segments.device'];
    
    if (devices[device]) {
      devices[device].spend += parseFloat(row['metrics.cost_micros']) / 1000000;
      devices[device].clicks += parseInt(row['metrics.clicks']);
      devices[device].impressions += parseInt(row['metrics.impressions']);
      devices[device].conversions += parseFloat(row['metrics.conversions']);
      devices[device].conversion_value += parseFloat(row['metrics.conversions_value']);
    }
  }
  
  // Calculate derived metrics
  for (const device in devices) {
    const data = devices[device];
    data.ctr = data.impressions > 0 ? (data.clicks / data.impressions) * 100 : 0;
    data.cpc = data.clicks > 0 ? data.spend / data.clicks : 0;
    data.conversion_rate = data.clicks > 0 ? (data.conversions / data.clicks) * 100 : 0;
  }
  
  return devices;
}

/**
 * Get daily breakdown
 */
function getDailyBreakdown(startDate, endDate) {
  const query = `
    SELECT
      segments.date,
      metrics.cost_micros,
      metrics.clicks,
      metrics.impressions,
      metrics.conversions,
      metrics.conversions_value
    FROM customer
    WHERE segments.date BETWEEN '${startDate}' AND '${endDate}'
    ORDER BY segments.date
  `;
  
  const report = AdsApp.report(query);
  const rows = report.rows();
  
  const daily = [];
  
  while (rows.hasNext()) {
    const row = rows.next();
    const spend = parseFloat(row['metrics.cost_micros']) / 1000000;
    const clicks = parseInt(row['metrics.clicks']);
    const conversions = parseFloat(row['metrics.conversions']);
    const conversionValue = parseFloat(row['metrics.conversions_value']);
    
    daily.push({
      date: row['segments.date'],
      spend: spend,
      clicks: clicks,
      impressions: parseInt(row['metrics.impressions']),
      conversions: conversions,
      conversion_value: conversionValue,
      roas: spend > 0 ? conversionValue / spend : 0,
      cost_per_conversion: conversions > 0 ? spend / conversions : 0
    });
  }
  
  return daily;
}

/**
 * Send metrics to backend webhook
 */
function sendToWebhook(data) {
  const payload = JSON.stringify(data);
  
  const options = {
    'method': 'post',
    'contentType': 'application/json',
    'payload': payload,
    'headers': {
      'X-Webhook-Secret': WEBHOOK_SECRET
    },
    'muteHttpExceptions': true
  };
  
  try {
    const response = UrlFetchApp.fetch(WEBHOOK_URL, options);
    const responseCode = response.getResponseCode();
    const responseText = response.getContentText();
    
    if (responseCode === 200) {
      Logger.log('Successfully sent data to webhook');
    } else {
      Logger.log('Webhook returned error: ' + responseCode + ' - ' + responseText);
      throw new Error('Webhook error: ' + responseCode);
    }
  } catch (error) {
    Logger.log('Error sending to webhook: ' + error.message);
    throw error;
  }
}

/**
 * Send error notification (optional)
 */
function sendErrorNotification(error) {
  // You can add email notification or other error handling here
  Logger.log('Error in Google Ads script: ' + error.message);
}

/**
 * Format date for GAQL query (YYYY-MM-DD)
 */
function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return year + '-' + month + '-' + day;
}

