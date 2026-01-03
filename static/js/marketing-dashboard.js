/* global Chart */
(function () {
    'use strict';

    const API_BASE = '/api/marketing';
    const PRESET_LABELS = {
        today: 'Today',
        yesterday: 'Yesterday',
        last_7_days: 'Last 7 days',
        last_30_days: 'Last 30 days',
        month_to_date: 'Month to date',
        quarter_to_date: 'Quarter to date',
        year_to_date: 'Year to date',
        last_12_months: 'Last 12 months',
    };

    const SEGMENT_FILTERS = [
        { id: 'all', label: 'All Campaigns' },
        { id: 'recruiting', label: 'Recruiting' },
        { id: 'client', label: 'Client Acquisition' },
    ];

    const SEGMENT_KEYWORDS = {
        recruiting: ['recruit', 'caregiver', 'talent', 'hiring', 'applicant'],
        client: ['client', 'family', 'service', 'private pay', 'care'],
    };

    const presetSelectIds = [
        'datePreset',
        'socialDatePreset',
        'paidDatePreset',
        'emailDatePreset',
        'websiteDatePreset',
        'engagementDatePreset',
    ];

    const refreshButtonIds = [
        'refreshBtn',
        'socialRefreshBtn',
        'paidRefreshBtn',
        'emailRefreshBtn',
        'websiteRefreshBtn',
        'engagementRefreshBtn',
    ];

    const BENCHMARKS = {
        targetRoas: 3.5,
        targetDailySpend: 450,
        targetConversions: 50,
        targetEmailOpen: 35,
        targetEmailClick: 5,
        targetSessions: 2000,
    };

    const charts = {
        roas: null,
        costPerf: null,
        costConv: null,
        impressions: null,
        sessions: null,
        interactionsClicks: null,
        interactionsConv: null,
        paidSpend: null,
        socialReach: null,
        socialEngagement: null,
        paidDaily: null,
        campaignEfficiency: null,
        websiteSessions: null,
        gbpSearches: null,
        emailEngagement: null,
        emailGrowth: null,
        engagementType: null,
        engagementTrend: null,
    };

    const state = {
        preset: 'last_30_days',
        selectedCampaign: null,
        latestGoogleData: null,
        latestGa4Data: null,
        googleCampaigns: [],
        facebookCampaigns: [],
        recentCampaigns: [],
        conversionPaths: [],
        segment: 'all',
        alertLog: [],
        lastAlertCount: 0,
    };

    document.addEventListener('DOMContentLoaded', () => {
        initTabNavigation();
        initCharts();
        initDrilldownPanel();
        initSegmentFilters();
        renderRecentCampaigns();
        renderAlertTimeline();
        attachEventHandlers();
        const initialPreset = document.getElementById('datePreset')?.value || state.preset;
        state.preset = initialPreset;
        syncPresetSelectors(initialPreset);
        fetchDashboardData(initialPreset);
    });

    function initTabNavigation() {
        const sidebarLinks = Array.from(document.querySelectorAll('.sidebar-link'));
        const tabSections = Array.from(document.querySelectorAll('.tab-content'));
        const normalizeId = (value) => {
            if (!value) return null;
            return value.startsWith('tab-') ? value : `tab-${value}`;
        };

        let currentTabId = tabSections.find((section) => section.classList.contains('active'))?.id || 'tab-overview';

        const setActiveLink = (link) => {
            sidebarLinks.forEach((item) => item.classList.toggle('active', item === link));
        };

        const setActiveTab = (tabId) => {
            const target = document.getElementById(tabId);
            if (!target) {
                console.warn('Tab not found:', tabId);
                return false;
            }
            tabSections.forEach((section) => section.classList.toggle('active', section === target));
            currentTabId = tabId;
            return true;
        };

        const handleTabChange = (targetId) => {
            if (!targetId) return;
            const linkForTab = sidebarLinks.find(
                (link) => normalizeId(link.getAttribute('data-tab-target') || link.getAttribute('data-tab')) === targetId,
            );
            if (setActiveTab(targetId) && linkForTab) {
                setActiveLink(linkForTab);
            }
        };

        sidebarLinks.forEach((link) => {
            link.addEventListener('click', (event) => {
                if (link.classList.contains('disabled')) {
                    event.preventDefault();
                    return;
                }

                const rawTarget = link.getAttribute('data-tab-target') || link.getAttribute('data-tab');
                const targetId = normalizeId(rawTarget);
                if (targetId) {
                    link.setAttribute('href', `#${targetId}`);
                    handleTabChange(targetId);
                }
            });
        });

        window.addEventListener('hashchange', () => {
            const newHash = window.location.hash.replace('#', '');
            const normalized = normalizeId(newHash);
            if (normalized) {
                handleTabChange(normalized);
            }
        });

        const initialHash = window.location.hash.replace('#', '');
        const initialTabId = normalizeId(initialHash) || currentTabId;
        handleTabChange(initialTabId);
    }

    function attachEventHandlers() {
        presetSelectIds.forEach((id) => {
            const select = document.getElementById(id);
            if (!select) return;
            select.addEventListener('change', () => {
                const preset = select.value;
                state.preset = preset;
                syncPresetSelectors(preset);
                fetchDashboardData(preset);
            });
        });

        refreshButtonIds.forEach((id) => {
            const button = document.getElementById(id);
            if (!button) return;
            button.addEventListener('click', (event) => {
                event.preventDefault();
                fetchDashboardData(state.preset);
            });
        });
    }

    function initSegmentFilters() {
        const container = document.getElementById('segmentFilters');
        if (!container) return;
        container.innerHTML = SEGMENT_FILTERS.map(
            (filter) => `
                <button class="segment-chip ${filter.id === state.segment ? 'active' : ''}" data-segment="${filter.id}">
                    ${filter.label}
                </button>
            `,
        ).join('');
        container.querySelectorAll('.segment-chip').forEach((chip) => {
            chip.addEventListener('click', () => {
                const targetSegment = chip.getAttribute('data-segment');
                handleSegmentChange(targetSegment);
            });
        });
    }

    function setActiveSegmentChip(segmentId) {
        const container = document.getElementById('segmentFilters');
        if (!container) return;
        container.querySelectorAll('.segment-chip').forEach((chip) => {
            const isActive = chip.getAttribute('data-segment') === segmentId;
            chip.classList.toggle('active', isActive);
        });
    }

    function handleSegmentChange(segmentId) {
        if (!segmentId || segmentId === state.segment) return;
        state.segment = segmentId;
        setActiveSegmentChip(segmentId);
        state.recentCampaigns = [];
        renderRecentCampaigns();
        fetchDashboardData(state.preset);
    }

    function attachCampaignRowHandlers() {
        const rows = document.querySelectorAll('.campaign-row');
        rows.forEach((row) => {
            row.addEventListener('click', () => {
                const source = row.getAttribute('data-source');
                const index = Number(row.getAttribute('data-index'));
                if (source === 'google') {
                    const campaign = state.googleCampaigns[index];
                    if (campaign) {
                        openCampaignDrilldown('Google Ads', campaign);
                    }
                } else if (source === 'facebook') {
                    const campaign = state.facebookCampaigns[index];
                    if (campaign) {
                        openCampaignDrilldown('Facebook Ads', campaign);
                    }
                }
            });
        });
    }

    function syncPresetSelectors(value) {
        presetSelectIds.forEach((id) => {
            const select = document.getElementById(id);
            if (!select) return;
            if (Array.from(select.options).some((option) => option.value === value)) {
                select.value = value;
            }
        });
    }

    async function fetchDashboardData(preset) {
        const { start, end } = calculateDateRange(preset);
        try {
            const [adsResult, socialResult, websiteResult, emailResult, engagementResult] = await Promise.allSettled([
                fetchJson(`${API_BASE}/ads?from=${start}&to=${end}`),
                fetchJson(`${API_BASE}/social?from=${start}&to=${end}`),
                fetchJson(`${API_BASE}/website?from=${start}&to=${end}`),
                fetchJson(`${API_BASE}/email?from=${start}&to=${end}`),
                fetchJson(`${API_BASE}/engagement?from=${start}&to=${end}`),
            ]);

            const ads = adsResult.status === 'fulfilled' ? adsResult.value : null;
            const social = socialResult.status === 'fulfilled' ? socialResult.value : null;
            const website = websiteResult.status === 'fulfilled' ? websiteResult.value : null;
            const email = emailResult.status === 'fulfilled' ? emailResult.value : null;
            const engagement = engagementResult.status === 'fulfilled' ? engagementResult.value : null;

            if (adsResult.status === 'rejected') {
                console.error('Ads metrics request failed', adsResult.reason);
            }
            if (socialResult.status === 'rejected') {
                console.error('Social metrics request failed', socialResult.reason);
            }
            if (websiteResult.status === 'rejected') {
                console.error('Website metrics request failed', websiteResult.reason);
            }
            if (emailResult.status === 'rejected') {
                console.error('Email metrics request failed', emailResult.reason);
            }
            if (engagementResult.status === 'rejected') {
                console.error('Engagement metrics request failed', engagementResult.reason);
            }

            renderDashboard({
                ads,
                social,
                website,
                email,
                engagement,
                preset,
                fallbackRange: { start, end },
            });
        } catch (error) {
            console.error('Unexpected dashboard fetch error', error);
        }
    }

    async function fetchJson(url) {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`Request failed: ${response.status}`);
        }
        return response.json();
    }

    function renderDashboard({ ads, social, website, email, engagement, preset, fallbackRange }) {
        const adsRange = ads?.range || fallbackRange;
        if (adsRange) {
            updateDateRangeDisplay(adsRange.start, adsRange.end, preset);
        }

        if (ads?.success) {
            renderAdsSection(ads, preset);
        }
        if (social?.success) {
            renderSocialSection(social, preset);
        }
        if (website?.success) {
            renderWebsiteSection(website, preset);
        }
        if (email?.success) {
            renderEmailSection(email, preset);
        }
        if (engagement?.success) {
            renderEngagementSection(engagement, preset);
        }
    }

    function renderAdsSection(payload, preset) {
        if (!payload?.data) return;

        const google = payload.data.google_ads;
        const facebookAccount = payload.data.facebook_ads?.account;
        const facebookCampaigns = payload.data.facebook_ads?.campaigns || [];
        const googleCampaigns = google?.campaigns || [];
        const days = payload.range?.days || 30;

        const filteredGoogleCampaigns = filterCampaignsBySegment(googleCampaigns);
        const filteredFacebookCampaigns = filterCampaignsBySegment(facebookCampaigns);

        const googleSummary =
            state.segment === 'all'
                ? google
                : buildGoogleMetricsFromCampaigns(filteredGoogleCampaigns, days, google);
        const facebookSummary =
            state.segment === 'all'
                ? facebookAccount
                : buildFacebookMetricsFromCampaigns(filteredFacebookCampaigns);

        renderGoogleOverview(googleSummary);
        renderFacebookOverview(facebookSummary);
        renderCampaignTables(filteredGoogleCampaigns, filteredFacebookCampaigns);
        renderPaidSummary(googleSummary, facebookSummary, payload.range, preset);
        updateAdsCharts(google);
        updatePaidDailyChart(google, facebookAccount);
        updateCampaignEfficiencyChart(filteredGoogleCampaigns, filteredFacebookCampaigns);
        state.latestGoogleData = google;
    }

    function renderGoogleOverview(google) {
        if (!google) {
            setText('googleAdsSpend');
            setText('googleAccountSpend');
            return;
        }

        const currency = google.currency_code || 'USD';
        setText('googleAdsSpend', formatCurrency(google.spend?.total, 2, currency));
        setText('googleAccountSpend', formatCurrency(google.spend?.total, 2, currency));
        setText('googleClicks', formatNumber(google.performance?.clicks));
        setText('googleImpressions', formatNumber(google.performance?.impressions));
        setText('googleCTR', formatPercent(google.efficiency?.ctr));
        setText('googleCPC', formatCurrency(google.efficiency?.cpc, 2, currency));
        setText('googleConversions', formatNumber(google.performance?.conversions));
        setText('googleConvValue', formatCurrency(google.performance?.conversion_value, 2, currency));

        const roasValue = safeNumber(google.efficiency?.roas);
        setText('googleRoasMetric', roasValue !== null ? `${roasValue.toFixed(2)}x` : '—');
        updatePill('googleRoasSummary', roasValue !== null ? `ROAS ${roasValue.toFixed(2)}x` : 'ROAS —');
        
        // New search KPIs
        const convRate = safeNumber(google.efficiency?.conversion_rate);
        setText('googleConversionRate', convRate !== null ? `${convRate.toFixed(2)}%` : '—');
        
        const searchIS = safeNumber(google.efficiency?.search_impression_share);
        setText('googleSearchIS', searchIS !== null ? `${searchIS.toFixed(1)}%` : '—');
        
        const rankLostIS = safeNumber(google.efficiency?.search_rank_lost_impression_share);
        setText('googleRankLostIS', rankLostIS !== null ? `${rankLostIS.toFixed(1)}%` : '—');
        
        const budgetLostIS = safeNumber(google.efficiency?.search_budget_lost_impression_share);
        setText('googleBudgetLostIS', budgetLostIS !== null ? `${budgetLostIS.toFixed(1)}%` : '—');

        const costPerConv = safeNumber(google.efficiency?.cost_per_conversion);
        updatePill(
            'googleCostPerConvPill',
            costPerConv !== null ? `Cost/Conv ${formatCurrency(costPerConv, 2, currency)}` : 'Cost/Conv —',
        );

        setText('totalImpressions', formatNumber(google.performance?.impressions));
        
        // Render new metrics: Quality Scores, Search Terms, Device Performance
        renderGoogleQualityScores(google.quality_scores);
        renderGoogleSearchTerms(google.search_terms);
        renderGoogleDevicePerformance(google.device_performance);
    }
    
    function renderGoogleQualityScores(qualityScores) {
        if (!qualityScores || !qualityScores.average_quality_score) return;
        
        const container = document.getElementById('googleQualityScores');
        if (!container) return;
        
        container.innerHTML = `
            <div class="stats-row">
                <div class="stats-label">Avg Quality Score</div>
                <div class="stats-value">${qualityScores.average_quality_score}/10</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Creative Score</div>
                <div class="stats-value">${qualityScores.average_creative_score || '—'}/10</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Landing Page Score</div>
                <div class="stats-value">${qualityScores.average_landing_page_score || '—'}/10</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Predicted CTR</div>
                <div class="stats-value">${qualityScores.average_predicted_ctr || '—'}/10</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Keywords Analyzed</div>
                <div class="stats-value">${formatNumber(qualityScores.keywords_analyzed || 0)}</div>
            </div>
        `;
    }
    
    function renderGoogleSearchTerms(searchTerms) {
        if (!searchTerms || !searchTerms.length) return;
        
        const container = document.getElementById('googleSearchTerms');
        if (!container) return;
        
        container.innerHTML = searchTerms.slice(0, 10).map((term) => {
            const cpc = term.cpc ? formatCurrency(term.cpc, 2) : '—';
            const conversions = term.conversions || 0;
            return `
                <div class="stats-row">
                    <div class="stats-label" title="${term.search_term}">${term.search_term.length > 40 ? term.search_term.substring(0, 40) + '...' : term.search_term}</div>
                    <div class="stats-value">
                        ${formatNumber(term.clicks)}
                        <span class="stats-change">${cpc} | ${conversions} conv</span>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    function renderGoogleDevicePerformance(devicePerf) {
        if (!devicePerf || !Object.keys(devicePerf).length) return;
        
        const container = document.getElementById('googleDevicePerformance');
        if (!container) return;
        
        const devices = Object.entries(devicePerf).map(([device, stats]) => ({
            device: device.charAt(0).toUpperCase() + device.slice(1),
            ...stats
        }));
        
        container.innerHTML = devices.map((device) => {
            const ctr = device.ctr ? formatPercent(device.ctr) : '—';
            const convRate = device.conversion_rate ? formatPercent(device.conversion_rate) : '—';
            return `
                <div class="stats-row">
                    <div class="stats-label">${device.device}</div>
                    <div class="stats-value">
                        ${formatCurrency(device.spend, 2)}
                        <span class="stats-change">${formatNumber(device.clicks)} clicks | ${ctr} CTR | ${convRate} Conv</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    function renderFacebookOverview(account) {
        if (!account) {
            setText('facebookAdsSpend');
            setText('facebookAccountSpend');
            setText('facebookClicks');
            setText('facebookCTR');
            setText('facebookCPC');
            setText('facebookConversions');
            updatePill('facebookCtrPill');
            updatePill('facebookCpcPill');
            setChangeValue('facebookAdsChange');
            return;
        }

        setText('facebookAdsSpend', formatCurrency(account.spend, 2));
        updatePill('facebookCtrPill', account.ctr !== undefined ? `CTR ${formatPercent(account.ctr)}` : 'CTR —');
        updatePill('facebookCpcPill', account.cpc !== undefined ? `CPC ${formatCurrency(account.cpc, 2)}` : 'CPC —');

        setText('facebookAccountSpend', formatCurrency(account.spend, 2));
        setText('facebookClicks', formatNumber(account.clicks));
        setText('facebookCTR', formatPercent(account.ctr));
        setText('facebookCPC', formatCurrency(account.cpc, 2));
        setText('facebookConversions', formatNumber(account.conversions));

        const change = calculateDailyTrend(account.daily || account.daily_breakdown);
        setChangeValue('facebookAdsChange', change);
    }

    function renderCampaignTables(googleCampaigns, facebookCampaigns) {
        state.googleCampaigns = googleCampaigns;
        state.facebookCampaigns = facebookCampaigns;
        const googleBody = document.getElementById('googleCampaignsTable');
        if (googleBody) {
            if (!googleCampaigns.length) {
                googleBody.innerHTML = `<tr><td colspan="8" class="empty-state-text">No active Google Ads campaigns found</td></tr>`;
            } else {
                googleBody.innerHTML = googleCampaigns.slice(0, 10).map((campaign, index) => {
                    const roasText = campaign.roas ? `${campaign.roas.toFixed(2)}x` : '—';
                    const convRateText = campaign.conversion_rate !== undefined ? `${campaign.conversion_rate.toFixed(2)}%` : '—';
                    const searchISText = campaign.search_impression_share !== undefined ? `${campaign.search_impression_share.toFixed(1)}%` : '—';
                    return `
                        <tr class="campaign-row" data-source="google" data-index="${index}">
                            <td>${index + 1}</td>
                            <td>
                                <span class="campaign-name">${campaign.name}</span>
                                <span class="campaign-id">${campaign.channel || ''}</span>
                            </td>
                            <td>${formatCurrency(campaign.spend, 2)}</td>
                            <td>${formatNumber(campaign.clicks)}</td>
                            <td>${formatNumber(campaign.conversions)}</td>
                            <td>${convRateText}</td>
                            <td>${roasText}</td>
                            <td>${searchISText}</td>
                        </tr>
                    `;
                }).join('');
            }
        }

        const facebookBody = document.getElementById('facebookCampaignsTable');
        if (facebookBody) {
            if (!facebookCampaigns.length) {
                facebookBody.innerHTML = `<tr><td colspan="5" class="empty-state-text">No Facebook campaigns found</td></tr>`;
            } else {
                facebookBody.innerHTML = facebookCampaigns.slice(0, 6).map((campaign, index) => `
                    <tr class="campaign-row" data-source="facebook" data-index="${index}">
                        <td>${index + 1}</td>
                        <td class="campaign-name">${campaign.name}</td>
                        <td>${formatCurrency(campaign.spend, 2)}</td>
                        <td>${formatNumber(campaign.impressions)}</td>
                        <td>${formatNumber(campaign.clicks)}</td>
                    </tr>
                `).join('');
            }
        }

        attachCampaignRowHandlers();
    }

    function renderPaidSummary(google, facebookAccount, range, preset) {
        const googleSpend = safeNumber(google?.spend?.total) ?? 0;
        const facebookSpend = safeNumber(facebookAccount?.spend) ?? 0;
        const totalSpend = googleSpend + facebookSpend;

        const googleClicks = safeNumber(google?.performance?.clicks) ?? 0;
        const facebookClicks = safeNumber(facebookAccount?.clicks) ?? 0;
        const totalClicks = googleClicks + facebookClicks;

        const googleConversions = safeNumber(google?.performance?.conversions) ?? 0;
        const facebookConversions = safeNumber(facebookAccount?.conversions) ?? 0;
        const totalConversions = googleConversions + facebookConversions;

        setText('paidTotalSpend', formatCurrency(totalSpend, 2));
        setTargetBadge('paidTotalSpend', totalSpend, BENCHMARKS.targetDailySpend * ((range?.days || 30) / 30));
        setText('paidGoogleSpend', formatCurrency(googleSpend, 2));
        setText('paidFacebookSpend', formatCurrency(facebookSpend, 2));
        setText('paidClicks', formatNumber(totalClicks));

        const blendedCpc = totalClicks ? totalSpend / totalClicks : null;
        setText('paidCPC', blendedCpc !== null ? formatCurrency(blendedCpc, 2) : '—');
        setText('paidConversions', formatNumber(totalConversions));
        setTargetBadge('paidConversions', totalConversions, BENCHMARKS.targetConversions);

        const googleImpressions = safeNumber(google?.performance?.impressions) ?? 0;
        const facebookImpressions = safeNumber(facebookAccount?.impressions) ?? 0;
        const totalImpressions = googleImpressions + facebookImpressions;

        const roasValue = safeNumber(google?.efficiency?.roas);
        setText('paidRoas', roasValue !== null ? `${roasValue.toFixed(2)}x` : '—');
        setTargetBadge('paidRoas', roasValue, BENCHMARKS.targetRoas, true);

        const blendedCostPerConv = totalConversions ? totalSpend / totalConversions : null;
        setText('paidCostPerConv', blendedCostPerConv !== null ? formatCurrency(blendedCostPerConv, 2) : '—');

        const conversionRate = totalClicks ? (totalConversions / totalClicks) * 100 : null;
        setText('paidConversionRate', conversionRate !== null ? `${conversionRate.toFixed(1)}%` : '—');

        const blendedCpm = totalImpressions ? (totalSpend / totalImpressions) * 1000 : null;
        setText('paidCpm', blendedCpm !== null ? formatCurrency(blendedCpm, 2) : '—');

        updateRangeLabel({
            start: range?.start,
            end: range?.end,
            preset,
            targetId: 'paidDateRange',
        });

        updatePaidCampaignStats(google?.campaigns || []);
        updatePaidSpendChart(googleSpend, facebookSpend);
        const alerts = evaluatePaidAlerts({
            roasValue,
            conversionRate,
            blendedCpc,
            blendedCostPerConv,
            blendedCpm,
            facebookDelivery: facebookAccount?.delivery_rate,
            facebookCtr: facebookAccount?.ctr,
        });
        logAlerts(alerts);
        renderPaidAlerts(alerts);
    }

    function evaluatePaidAlerts(metrics) {
        const alerts = [];
        if (metrics.roasValue !== null && metrics.roasValue < 2) {
            alerts.push({ level: 'warning', message: `ROAS trending low at ${metrics.roasValue.toFixed(2)}x` });
        }
        if (metrics.blendedCostPerConv !== null && metrics.blendedCostPerConv > 300) {
            alerts.push({ level: 'critical', message: `Cost per conversion spiked to ${formatCurrency(metrics.blendedCostPerConv, 2)}` });
        }
        if (metrics.conversionRate !== null && metrics.conversionRate < 2) {
            alerts.push({ level: 'warning', message: `Conversion rate fell to ${metrics.conversionRate.toFixed(1)}%` });
        }
        if (metrics.blendedCpm !== null && metrics.blendedCpm > 45) {
            alerts.push({ level: 'info', message: `CPM is elevated at ${formatCurrency(metrics.blendedCpm, 2)}` });
        }
        if (metrics.facebookDelivery && metrics.facebookDelivery < 80) {
            alerts.push({ level: 'warning', message: `Facebook delivery rate down to ${metrics.facebookDelivery.toFixed(1)}%` });
        }
        if (metrics.facebookCtr && metrics.facebookCtr < 0.5) {
            alerts.push({ level: 'info', message: `Facebook CTR is just ${metrics.facebookCtr.toFixed(2)}%` });
        }
        return alerts;
    }

    function renderPaidAlerts(alerts) {
        const container = document.getElementById('paidAlerts');
        if (!container) return;
        if (!alerts.length) {
            container.innerHTML = `
                <div class="stats-row">
                    <div class="stats-label">All systems nominal</div>
                    <div class="stats-value">No alerts</div>
                </div>
            `;
            return;
        }
        const badge = (level) => {
            switch (level) {
                case 'critical':
                    return '🔴';
                case 'warning':
                    return '🟠';
                default:
                    return '🟡';
            }
        };
        container.innerHTML = alerts
            .map(
                (alert) => `
                <div class="stats-row">
                    <div class="stats-label">${badge(alert.level)} ${alert.message}</div>
                    <div class="stats-value">${new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                </div>
            `,
            )
            .join('');
    }

    function logAlerts(alerts) {
        const timestamp = new Date().toISOString();
        if (alerts.length) {
            alerts.forEach((alert) => {
                state.alertLog.unshift({
                    level: alert.level,
                    message: alert.message,
                    timestamp,
                });
            });
        } else if (state.lastAlertCount > 0) {
            state.alertLog.unshift({
                level: 'clear',
                message: 'Alerts cleared',
                timestamp,
            });
        }
        state.alertLog = state.alertLog.slice(0, 10);
        state.lastAlertCount = alerts.length;
        renderAlertTimeline();
    }

    function renderAlertTimeline() {
        const container = document.getElementById('alertTimeline');
        if (!container) return;
        if (!state.alertLog.length) {
            container.innerHTML = `<div class="timeline-entry">No alert events</div>`;
            return;
        }
        container.innerHTML = state.alertLog
            .map(
                (entry) => `
                    <div class="timeline-entry ${entry.level}">
                        <span>${formatTimelineTime(entry.timestamp)}</span>
                        <span>${entry.message}</span>
                    </div>
                `,
            )
            .join('');
    }

    function updatePaidCampaignStats(campaigns) {
        const container = document.getElementById('paidCampaignStats');
        if (!container) return;

        if (!campaigns.length) {
            container.innerHTML = `
                <div class="stats-row">
                    <div class="stats-label">No campaign data</div>
                    <div class="stats-value">—</div>
                </div>
            `;
            return;
        }

        const topCampaigns = [...campaigns]
            .sort((a, b) => (b.roas || 0) - (a.roas || 0))
            .slice(0, 4);

        container.innerHTML = topCampaigns
            .map((campaign) => {
                const roasText = campaign.roas ? `${campaign.roas.toFixed(2)}x` : '—';
                const cpa = campaign.cost_per_conversion ? formatCurrency(campaign.cost_per_conversion, 2) : '—';
                return `
                    <div class="stats-row">
                        <div class="stats-label">${campaign.name}</div>
                        <div class="stats-value">
                            ${roasText}
                            <span class="stats-change">${cpa}</span>
                        </div>
                    </div>
                `;
            })
            .join('');
    }

    function updatePaidSpendChart(googleSpend, facebookSpend) {
        if (!charts.paidSpend) return;
        charts.paidSpend.data.datasets[0].data = [googleSpend, facebookSpend];
        charts.paidSpend.update();
    }

    function updateAdsCharts(google) {
        if (!google?.spend?.daily || !google.spend.daily.length) return;

        const daily = google.spend.daily;
        const labels = daily.map((entry) => formatChartLabel(entry.date));

        updateLineChart(charts.roas, labels, daily.map((entry) => roundNumber(entry.roas, 2)));
        if (charts.roas?.data?.datasets?.[1]) {
            charts.roas.data.datasets[1].data = labels.map(() => BENCHMARKS.targetRoas);
            charts.roas.update();
        }
        updateLineChart(charts.costPerf, labels, daily.map((entry) => roundNumber(entry.spend, 2)));
        if (charts.costPerf?.data?.datasets?.[1]) {
            charts.costPerf.data.datasets[1].data = labels.map(() => BENCHMARKS.targetDailySpend);
            charts.costPerf.update();
        }
        updateLineChart(charts.costConv, labels, daily.map((entry) => roundNumber(entry.cost_per_conversion, 2)));
        updateLineChart(charts.impressions, labels, daily.map((entry) => entry.impressions || 0));
        updateLineChart(charts.interactionsClicks, labels, daily.map((entry) => entry.clicks || 0));
        updateLineChart(charts.interactionsConv, labels, daily.map((entry) => entry.conversions || 0));
    }

    function updatePaidDailyChart(google, facebook) {
        if (!charts.paidDaily) return;

        const googleDaily = Array.isArray(google?.spend?.daily) ? google.spend.daily : [];
        const facebookDaily = Array.isArray(facebook?.daily) ? facebook.daily : [];
        const combined = {};

        googleDaily.forEach((entry) => {
            combined[entry.date] = {
                googleSpend: entry.spend || 0,
                googleConversions: entry.conversions || 0,
                facebookSpend: 0,
            };
        });

        facebookDaily.forEach((entry) => {
            if (!combined[entry.date]) {
                combined[entry.date] = { googleSpend: 0, googleConversions: 0, facebookSpend: 0 };
            }
            combined[entry.date].facebookSpend = entry.spend || 0;
        });

        const dates = Object.keys(combined).sort();
        if (!dates.length) {
            charts.paidDaily.data.labels = [];
            charts.paidDaily.update();
            return;
        }

        charts.paidDaily.data.labels = dates.map((date) => formatChartLabel(date));
        charts.paidDaily.data.datasets[0].data = dates.map((date) => combined[date].googleSpend);
        charts.paidDaily.data.datasets[1].data = dates.map((date) => combined[date].facebookSpend);
        charts.paidDaily.data.datasets[2].data = dates.map((date) => combined[date].googleConversions);
        charts.paidDaily.update();
    }

    function updateCampaignEfficiencyChart(googleCampaigns, facebookCampaigns) {
        if (!charts.campaignEfficiency) return;

        const normalize = (campaign, index, source) => ({
            x: campaign.spend || 0,
            y: campaign.conversions || 0,
            r: Math.max(4, Math.sqrt(Math.max(campaign.clicks || 0, 0))),
            campaign: campaign.name || 'Campaign',
            source,
            campaignIndex: index,
        });

        charts.campaignEfficiency.data.datasets[0].data = (googleCampaigns || []).map((campaign, index) =>
            normalize(campaign, index, 'google'),
        );
        charts.campaignEfficiency.data.datasets[1].data = (facebookCampaigns || []).map((campaign, index) =>
            normalize(campaign, index, 'facebook'),
        );
        charts.campaignEfficiency.update();
    }

    function renderSocialSection(payload, preset) {
        if (!payload?.data) return;

        const { range, data } = payload;
        updateRangeLabel({
            start: range?.start,
            end: range?.end,
            preset,
            targetId: 'socialDateRange',
        });

        const summary = data.summary || {};
        const postOverview = data.post_overview || {};

        setText('socialPageLikes', formatNumber(summary.total_page_likes?.value));
        setChangeValue('socialLikesChange', summary.total_page_likes?.change);
        setText('socialReach', formatNumber(summary.reach?.total));
        setChangeValue('socialReachChange', summary.reach?.change);

        const engagementValue = summary.unique_clicks ?? postOverview.post_clicks;
        setText('socialEngagement', formatNumber(engagementValue));
        setText('socialPosts', formatNumber(postOverview.posts_published));
        setText('socialImpressions', formatNumber(summary.impressions));
        setText('socialVideoViews', formatNumber(summary.video_views_3s));

        renderSocialTopPosts(data.top_posts || []);
        updateSocialCharts(postOverview.chart || []);
        
        // Render new metrics: Facebook Audience Demographics
        renderFacebookDemographics(data.audience_demographics || summary.audience_demographics);
        
        // Render new metrics: LinkedIn follower growth (if available in data)
        if (data.linkedin) {
            renderLinkedInFollowerGrowth(data.linkedin);
        }
    }
    
    function renderLinkedInFollowerGrowth(linkedin) {
        if (!linkedin || !linkedin.follower_growth) return;
        
        const container = document.getElementById('linkedinFollowerGrowth');
        if (!container) return;
        
        const growth = linkedin.follower_growth;
        container.innerHTML = `
            <div class="stats-row">
                <div class="stats-label">Current Followers</div>
                <div class="stats-value">${formatNumber(growth.current_followers)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Growth Rate</div>
                <div class="stats-value">${formatPercent(growth.growth_rate)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Followers Added</div>
                <div class="stats-value">${formatNumber(growth.followers_added)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Growth Trend</div>
                <div class="stats-value">${growth.trend === 'up' ? '↑ Increasing' : growth.trend === 'down' ? '↓ Decreasing' : '→ Stable'}</div>
            </div>
        `;
    }
    
    function renderFacebookDemographics(demographics) {
        if (!demographics || !Object.keys(demographics).length) return;
        
        const container = document.getElementById('facebookDemographics');
        if (!container) return;
        
        let html = '';
        
        // Top Countries
        if (demographics.countries && demographics.countries.length) {
            html += '<div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;"><div class="stats-label" style="font-weight: 600;">Top Countries</div></div>';
            demographics.countries.slice(0, 5).forEach(country => {
                html += `
                    <div class="stats-row">
                        <div class="stats-label">${country.country}</div>
                        <div class="stats-value">${formatNumber(country.count)}</div>
                    </div>
                `;
            });
        }
        
        // Top Cities
        if (demographics.cities && demographics.cities.length) {
            html += '<div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;"><div class="stats-label" style="font-weight: 600;">Top Cities</div></div>';
            demographics.cities.slice(0, 5).forEach(city => {
                html += `
                    <div class="stats-row">
                        <div class="stats-label">${city.city}</div>
                        <div class="stats-value">${formatNumber(city.count)}</div>
                    </div>
                `;
            });
        }
        
        // Devices
        if (demographics.devices && Object.keys(demographics.devices).length) {
            html += '<div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;"><div class="stats-label" style="font-weight: 600;">Devices</div></div>';
            Object.entries(demographics.devices).slice(0, 3).forEach(([device, count]) => {
                html += `
                    <div class="stats-row">
                        <div class="stats-label">${device}</div>
                        <div class="stats-value">${formatNumber(count)}</div>
                    </div>
                `;
            });
        }
        
        if (html) {
            container.innerHTML = html;
        }
    }

    function renderSocialTopPosts(posts) {
        const container = document.getElementById('socialTopPosts');
        if (!container) return;

        if (!posts.length) {
            container.innerHTML = `
                <div class="stats-row">
                    <div class="stats-label">No posts during this range</div>
                    <div class="stats-value">—</div>
                </div>
            `;
            return;
        }

        container.innerHTML = posts.slice(0, 3).map((post) => `
            <div class="stats-row">
                <div class="stats-label">${post.title}</div>
                <div class="stats-value">${formatNumber(post.reach)} reach</div>
            </div>
        `).join('');
    }

    function updateSocialCharts(dataPoints) {
        if (!dataPoints.length) return;
        const labels = dataPoints.map((point) => formatChartLabel(point.date));
        const reachValues = dataPoints.map((point) => point.reach || 0);
        const engagementValues = dataPoints.map((point) => point.engagement || 0);

        updateMultiDatasetChart(charts.socialReach, labels, [reachValues, engagementValues]);
        updateLineChart(charts.socialEngagement, labels, engagementValues);
    }

    function renderWebsiteSection(payload, preset) {
        if (!payload?.data) return;

        const { range, data } = payload;
        updateRangeLabel({
            start: range?.start,
            end: range?.end,
            preset,
            targetId: 'websiteDateRange',
        });

        const ga4 = data.ga4 || {};
        const gbp = data.gbp || {};

        if (ga4.sessions !== undefined) {
            setText('totalSessions', formatNumber(ga4.sessions));
            setTargetBadge('totalSessions', ga4.sessions, BENCHMARKS.targetSessions);
        }

        setText('websiteSessions', formatNumber(ga4.sessions));
        setText('websiteUsers', formatNumber(ga4.total_users));
        setText('websiteBounceRate', formatPercent(ga4.bounce_rate));
        setText('websiteAvgSession', ga4.avg_session_duration || '—');

        setText('gbpViews', formatNumber(gbp.views));
        const gbpActions = (gbp.phone_calls || 0) + (gbp.directions || 0) + (gbp.website_clicks || 0);
        setText('gbpActions', formatNumber(gbpActions));

        updateWebsiteCharts(ga4, gbp);
        state.latestGa4Data = ga4;
        state.conversionPaths = Array.isArray(ga4.conversion_paths) ? ga4.conversion_paths : [];
        updateAttributionChart();
        
        // Render new metrics: GA4 User Retention, Geographic Performance
        renderGA4UserRetention(ga4.user_retention);
        renderGA4Geographic(ga4.geographic_performance);
        
        // Render new metrics: GBP Reviews, Search Keywords
        renderGBPReviews(gbp.reviews);
        renderGBPSearchKeywords(gbp.search_keywords);
        
        // Render new GBP insights: Search Query Types, Photo Engagement, Post Engagement
        renderGBPSearchQueryTypes(gbp.search_query_types);
        renderGBPPhotoEngagement(gbp.photo_engagement);
        renderGBPPostEngagement(gbp.post_engagement);
        renderGBPViewsBreakdown(gbp);
    }
    
    function renderGA4UserRetention(retention) {
        if (!retention) return;
        
        const container = document.getElementById('ga4UserRetention');
        if (!container) return;
        
        container.innerHTML = `
            <div class="stats-row">
                <div class="stats-label">New Users</div>
                <div class="stats-value">${formatNumber(retention.new_users)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Returning Users</div>
                <div class="stats-value">${formatNumber(retention.returning_users)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Retention Rate</div>
                <div class="stats-value">${formatPercent(retention.retention_rate)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">New Engagement Rate</div>
                <div class="stats-value">${formatPercent(retention.new_engagement_rate)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Returning Engagement Rate</div>
                <div class="stats-value">${formatPercent(retention.returning_engagement_rate)}</div>
            </div>
        `;
    }
    
    function renderGA4Geographic(geo) {
        if (!geo) return;
        
        const container = document.getElementById('ga4Geographic');
        if (!container) return;
        
        let html = '';
        
        // Top Countries
        if (geo.top_countries && geo.top_countries.length) {
            html += '<div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;"><div class="stats-label" style="font-weight: 600;">Top Countries</div></div>';
            geo.top_countries.slice(0, 5).forEach(country => {
                html += `
                    <div class="stats-row">
                        <div class="stats-label">${country.country}</div>
                        <div class="stats-value">
                            ${formatNumber(country.users)}
                            <span class="stats-change">${formatPercent(country.conversion_rate)} conv</span>
                        </div>
                    </div>
                `;
            });
        }
        
        // Top Cities
        if (geo.top_cities && geo.top_cities.length) {
            html += '<div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;"><div class="stats-label" style="font-weight: 600;">Top Cities</div></div>';
            geo.top_cities.slice(0, 5).forEach(city => {
                html += `
                    <div class="stats-row">
                        <div class="stats-label">${city.city}</div>
                        <div class="stats-value">${formatNumber(city.users)}</div>
                    </div>
                `;
            });
        }
        
        if (html) {
            container.innerHTML = html;
        }
    }
    
    function renderGBPReviews(reviews) {
        if (!reviews || !reviews.total_reviews) return;
        
        const container = document.getElementById('gbpReviews');
        if (!container) return;
        
        let html = `
            <div class="stats-row">
                <div class="stats-label">Total Reviews</div>
                <div class="stats-value">${formatNumber(reviews.total_reviews)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Average Rating</div>
                <div class="stats-value">${reviews.average_rating || '—'}/5.0</div>
            </div>
        `;
        
        // Rating Distribution
        if (reviews.rating_distribution && Object.keys(reviews.rating_distribution).length) {
            html += '<div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;"><div class="stats-label" style="font-weight: 600;">Rating Distribution</div></div>';
            Object.entries(reviews.rating_distribution)
                .sort((a, b) => Number(b[0]) - Number(a[0]))
                .forEach(([rating, count]) => {
                    html += `
                        <div class="stats-row">
                            <div class="stats-label">${rating} ⭐</div>
                            <div class="stats-value">${formatNumber(count)}</div>
                        </div>
                    `;
                });
        }
        
        // Recent Reviews
        if (reviews.recent_reviews && reviews.recent_reviews.length) {
            html += '<div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;"><div class="stats-label" style="font-weight: 600;">Recent Reviews</div></div>';
            reviews.recent_reviews.slice(0, 3).forEach(review => {
                const comment = review.comment ? (review.comment.length > 50 ? review.comment.substring(0, 50) + '...' : review.comment) : 'No comment';
                html += `
                    <div class="stats-row">
                        <div class="stats-label">${review.author} (${review.rating}⭐)</div>
                        <div class="stats-value" style="font-size: 11px; color: #94a3b8;">${comment}</div>
                    </div>
                `;
            });
        }
        
        container.innerHTML = html;
    }
    
    function renderGBPSearchKeywords(keywords) {
        if (!keywords || !keywords.length) return;
        
        const container = document.getElementById('gbpSearchKeywords');
        if (!container) return;
        
        container.innerHTML = keywords.slice(0, 10).map((kw) => {
            return `
                <div class="stats-row">
                    <div class="stats-label" title="${kw.keyword}">${kw.keyword.length > 40 ? kw.keyword.substring(0, 40) + '...' : kw.keyword}</div>
                    <div class="stats-value">${formatNumber(kw.impressions)} impressions</div>
                </div>
            `;
        }).join('');
    }
    
    function renderGBPSearchQueryTypes(queryTypes) {
        if (!queryTypes) return;
        
        const container = document.getElementById('gbpSearchQueryTypes');
        if (!container) return;
        
        const total = queryTypes.direct + queryTypes.indirect + queryTypes.chain;
        if (total === 0) return;
        
        container.innerHTML = `
            <div class="stats-row">
                <div class="stats-label">Direct Searches</div>
                <div class="stats-value">${formatNumber(queryTypes.direct)} <span class="stats-change">(${formatPercent(queryTypes.direct_percentage)})</span></div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Indirect Searches</div>
                <div class="stats-value">${formatNumber(queryTypes.indirect)} <span class="stats-change">(${formatPercent(queryTypes.indirect_percentage)})</span></div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Chain Searches</div>
                <div class="stats-value">${formatNumber(queryTypes.chain)}</div>
            </div>
            <div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px; padding-top: 8px;">
                <div class="stats-label" style="font-size: 11px; color: #94a3b8;">Direct = searching your name<br>Indirect = discovering you</div>
            </div>
        `;
    }
    
    function renderGBPPhotoEngagement(photos) {
        if (!photos || photos.total_views === 0) return;
        
        const container = document.getElementById('gbpPhotoEngagement');
        if (!container) return;
        
        container.innerHTML = `
            <div class="stats-row">
                <div class="stats-label">Total Photo Views</div>
                <div class="stats-value">${formatNumber(photos.total_views)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Your Photos</div>
                <div class="stats-value">${formatNumber(photos.merchant_views)} views (${photos.merchant_photo_count} photos)</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Customer Photos</div>
                <div class="stats-value">${formatNumber(photos.customer_views)} views (${photos.customer_photo_count} photos)</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Avg Views/Photo</div>
                <div class="stats-value">${formatNumber(Math.round(photos.views_per_photo))}</div>
            </div>
        `;
    }
    
    function renderGBPPostEngagement(posts) {
        if (!posts || (posts.post_views === 0 && posts.post_engagement === 0)) return;
        
        const container = document.getElementById('gbpPostEngagement');
        if (!container) return;
        
        container.innerHTML = `
            <div class="stats-row">
                <div class="stats-label">Post Views</div>
                <div class="stats-value">${formatNumber(posts.post_views)}</div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Post Engagement</div>
                <div class="stats-value">${formatNumber(posts.post_engagement)}</div>
            </div>
        `;
    }
    
    function renderGBPViewsBreakdown(gbp) {
        if (!gbp.views_search && !gbp.views_maps) return;
        
        const container = document.getElementById('gbpViewsBreakdown');
        if (!container) return;
        
        const total = (gbp.views_search || 0) + (gbp.views_maps || 0);
        const searchPct = total > 0 ? ((gbp.views_search || 0) / total * 100).toFixed(1) : 0;
        const mapsPct = total > 0 ? ((gbp.views_maps || 0) / total * 100).toFixed(1) : 0;
        
        container.innerHTML = `
            <div class="stats-row">
                <div class="stats-label">Google Search</div>
                <div class="stats-value">${formatNumber(gbp.views_search || 0)} <span class="stats-change">(${searchPct}%)</span></div>
            </div>
            <div class="stats-row">
                <div class="stats-label">Google Maps</div>
                <div class="stats-value">${formatNumber(gbp.views_maps || 0)} <span class="stats-change">(${mapsPct}%)</span></div>
            </div>
        `;
    }

    function renderEmailSection(payload, preset) {
        if (!payload?.data) return;

        const { range, data } = payload;
        updateRangeLabel({
            start: range?.start,
            end: range?.end,
            preset,
            targetId: 'emailDateRange',
        });

        const summary = data.summary || {};
        setText('emailCampaigns', formatNumber(summary.campaigns_sent));
        setText('emailSubscribers', formatNumber(summary.total_contacts));
        setText('emailOpenRate', formatPercent(summary.open_rate));
        setTargetBadge('emailOpenRate', summary.open_rate, BENCHMARKS.targetEmailOpen, true);
        setText('emailClickRate', formatPercent(summary.click_rate));
        setTargetBadge('emailClickRate', summary.click_rate, BENCHMARKS.targetEmailClick, true);
        setText('emailDeliveryRate', formatPercent(summary.delivery_rate));
        setText('emailConversions', formatNumber(summary.conversions));

        renderEmailTopCampaigns(data.top_campaigns || []);
        updateEmailCharts(data.trend || [], data.subscriber_growth || []);
    }

    function renderEmailTopCampaigns(campaigns) {
        const container = document.getElementById('emailTopCampaigns');
        if (!container) return;

        if (!campaigns.length) {
            container.innerHTML = `
                <div class="stats-row">
                    <div class="stats-label">No campaigns sent in this range</div>
                    <div class="stats-value">—</div>
                </div>
            `;
            return;
        }

        container.innerHTML = campaigns
            .map(
                (campaign) => `
                <div class="stats-row">
                    <div class="stats-label">${campaign.title}</div>
                    <div class="stats-value">
                        ${formatPercent(campaign.open_rate, 1)}
                        <span class="stats-change">${formatPercent(campaign.click_rate, 1)} CTR</span>
                    </div>
                </div>
            `,
            )
            .join('');
    }

    function updateEmailCharts(trend, growth) {
        if (charts.emailEngagement && trend.length) {
            const labels = trend.map((entry) => formatChartLabel(entry.date));
            const opens = trend.map((entry) => entry.opens || 0);
            const clicks = trend.map((entry) => entry.clicks || 0);
            updateMultiDatasetChart(charts.emailEngagement, labels, [opens, clicks]);
        }

        if (charts.emailGrowth && growth.length) {
            const labels = growth.map((entry) => formatChartLabel(entry.date));
            const counts = growth.map((entry) => entry.subscribers || 0);
            updateLineChart(charts.emailGrowth, labels, counts);
        }
    }

    function renderEngagementSection(payload, preset) {
        if (!payload?.data) return;

        const { range, data } = payload;
        updateRangeLabel({
            start: range?.start,
            end: range?.end,
            preset,
            targetId: 'engagementDateRange',
        });

        const summary = data.summary || {};
        const attribution = data.attribution || {};
        const sources = data.sources || {};

        // Update KPI cards
        setText('engagementTotal', formatNumber(summary.total_engagements));
        
        // Calculate social engagement (FB + Pinterest + LinkedIn)
        const socialTotal = (sources.social?.facebook || 0) + 
                           (sources.social?.pinterest || 0) + 
                           (sources.social?.linkedin || 0);
        setText('engagementSocial', formatNumber(socialTotal));
        
        // Shares - use referral as proxy
        setText('engagementShares', formatNumber(sources.organic?.referral || 0));
        
        // Comments - placeholder (would need deeper social API access)
        setText('engagementComments', formatNumber(sources.paid?.google_ads || 0));
        
        // Messages - use calls as primary metric
        setText('engagementMessages', formatNumber(sources.local?.calls || 0));
        
        // Saves - directions + website clicks
        setText('engagementSaves', formatNumber((sources.local?.directions || 0) + (sources.local?.website || 0)));

        // Update the Engagement By Type chart (doughnut)
        updateEngagementTypeChart(attribution.by_type || []);

        // Update the Engagement Over Time chart (line)
        updateEngagementTrendChart(data.trend || []);

        // Render attribution breakdown
        renderAttributionBreakdown(attribution.by_source || []);
    }

    function updateEngagementTypeChart(types) {
        if (!charts.engagementType) return;
        
        if (!types.length) {
            charts.engagementType.data.labels = ['No data'];
            charts.engagementType.data.datasets[0].data = [1];
            charts.engagementType.data.datasets[0].backgroundColor = ['#475569'];
            charts.engagementType.update();
            return;
        }

        charts.engagementType.data.labels = types.map((t) => t.type);
        charts.engagementType.data.datasets[0].data = types.map((t) => t.value);
        charts.engagementType.data.datasets[0].backgroundColor = types.map((t) => t.color);
        charts.engagementType.update();
    }

    function updateEngagementTrendChart(trend) {
        if (!charts.engagementTrend || !trend.length) return;

        const labels = trend.map((entry) => formatChartLabel(entry.date));
        const values = trend.map((entry) => entry.engagements || 0);

        charts.engagementTrend.data.labels = labels;
        charts.engagementTrend.data.datasets[0].data = values;
        charts.engagementTrend.update();
    }

    function renderAttributionBreakdown(sources) {
        const container = document.getElementById('attributionBreakdown');
        if (!container) return;

        if (!sources.length) {
            container.innerHTML = `
                <div class="stats-row">
                    <div class="stats-label">No attribution data available</div>
                    <div class="stats-value">—</div>
                </div>
            `;
            return;
        }

        container.innerHTML = sources.slice(0, 6).map((source) => {
            const details = [];
            if (source.calls) details.push(`${source.calls} calls`);
            if (source.conversions) details.push(`${source.conversions} conv`);
            if (source.saves) details.push(`${source.saves} saves`);
            
            const detailText = details.length ? `<span class="stats-change">${details.join(', ')}</span>` : '';
            
            return `
                <div class="stats-row">
                    <div class="stats-label">${source.icon} ${source.source}</div>
                    <div class="stats-value">
                        ${formatNumber(source.engagements)}
                        ${detailText}
                    </div>
                </div>
            `;
        }).join('');
    }

    function updateWebsiteCharts(ga4, gbp) {
        if (Array.isArray(ga4?.users_over_time) && ga4.users_over_time.length) {
            const labels = ga4.users_over_time.map((entry) => formatChartLabel(entry.date));
            updateLineChart(charts.sessions, labels, ga4.users_over_time.map((entry) => entry.users || 0));
        }

        if (Array.isArray(ga4?.sessions_by_medium) && ga4.sessions_by_medium.length) {
            const labels = ga4.sessions_by_medium.map((entry) => formatChartLabel(entry.date));
            const datasetValues = ['none', 'cpc', 'paid', 'referral', 'organic'].map((key) =>
                ga4.sessions_by_medium.map((entry) => entry[key] || 0),
            );
            updateMultiDatasetChart(charts.websiteSessions, labels, datasetValues);
        }

        if (Array.isArray(gbp?.actions_over_time) && gbp.actions_over_time.length) {
            const labels = gbp.actions_over_time.map((entry) => formatChartLabel(entry.date));
            const datasetValues = [
                gbp.actions_over_time.map((entry) => entry.calls || 0),
                gbp.actions_over_time.map((entry) => entry.directions || 0),
                gbp.actions_over_time.map((entry) => entry.website || 0),
            ];
            updateMultiDatasetChart(charts.gbpSearches, labels, datasetValues);
        }
    }

    function updateAttributionChart() {
        if (!charts.attribution) return;
        const google = state.latestGoogleData;
        const ga4 = state.latestGa4Data;
        if (!google?.spend?.daily || !Array.isArray(ga4?.sessions_by_medium)) {
            charts.attribution.data.labels = [];
            charts.attribution.update();
            return;
        }

        const ga4Map = {};
        ga4.sessions_by_medium.forEach((entry) => {
            if (!entry.date) return;
            ga4Map[entry.date] = entry.cpc || 0;
        });

        const labels = google.spend.daily.map((entry) => entry.date);
        const adConversions = google.spend.daily.map((entry) => entry.conversions || 0);
        const ga4Sessions = labels.map((date) => ga4Map[date] || 0);

        charts.attribution.data.labels = labels.map((date) => formatChartLabel(date));
        charts.attribution.data.datasets[0].data = adConversions;
        charts.attribution.data.datasets[1].data = ga4Sessions;
        charts.attribution.update();
    }

    function initCharts() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js failed to load');
            return;
        }

        charts.roas = createLineChart('roasChart', '#34d399', 'ROAS');
        charts.roas.data.datasets.push({
            label: 'Target ROAS',
            data: [],
            borderColor: 'rgba(248, 250, 252, 0.5)',
            borderDash: [6, 4],
            borderWidth: 1,
            pointRadius: 0,
        });
        charts.roas.update();
        charts.costPerf = createLineChart('costPerfChart', '#22c55e', 'Spend');
        charts.costPerf.data.datasets.push({
            label: 'Target Spend',
            data: [],
            borderColor: 'rgba(148, 163, 184, 0.6)',
            borderDash: [6, 4],
            borderWidth: 1,
            pointRadius: 0,
        });
        charts.costPerf.update();
        charts.costConv = createLineChart('costConvChart', '#bef264', 'Cost/Conv.');
        charts.impressions = createLineChart('impressionsChart', '#38bdf8', 'Impressions');
        charts.sessions = createLineChart('sessionsChart', '#818cf8', 'Sessions');
        charts.interactionsClicks = createLineChart('interactionsChart1', '#3b82f6', 'Clicks');
        charts.interactionsConv = createLineChart('interactionsChart2', '#f472b6', 'Conversions');
        charts.paidSpend = createDoughnutChart('paidSpendChart');
        charts.socialReach = createMultiDatasetChart(
            'socialReachChart',
            [
                { label: 'Reach', color: '#22c55e', key: 'reach' },
                { label: 'Engagement', color: '#f97316', key: 'engagement' },
            ],
            { stacked: true, fillOpacity: 0.25 },
        );
        charts.socialEngagement = createLineChart('socialEngagementChart', '#fb923c', 'Engagement');
        charts.paidDaily = createPaidDailyChart('paidDailyChart');
        charts.campaignEfficiency = createCampaignEfficiencyChart('campaignEfficiencyChart');
        charts.emailEngagement = createMultiDatasetChart(
            'emailEngagementChart',
            [
                { label: 'Opens', color: '#38bdf8', key: 'opens' },
                { label: 'Clicks', color: '#f97316', key: 'clicks' },
            ],
            { stacked: false, legend: true, fillOpacity: 0.2 },
        );
        charts.emailGrowth = createLineChart('emailGrowthChart', '#22c55e', 'Subscribers');
        charts.attribution = createAttributionChart('attributionChart');
        charts.websiteSessions = createMultiDatasetChart(
            'websiteSessionsChart',
            [
                { label: 'Direct', color: '#38bdf8', key: 'none' },
                { label: 'CPC', color: '#6366f1', key: 'cpc' },
                { label: 'Paid', color: '#f97316', key: 'paid' },
                { label: 'Referral', color: '#2dd4bf', key: 'referral' },
                { label: 'Organic', color: '#a3e635', key: 'organic' },
            ],
            { stacked: true, legend: true, fillOpacity: 0.18 },
        );
        charts.gbpSearches = createMultiDatasetChart(
            'gbpSearchesChart',
            [
                { label: 'Calls', color: '#c084fc', key: 'calls' },
                { label: 'Directions', color: '#f472b6', key: 'directions' },
                { label: 'Website', color: '#22d3ee', key: 'website' },
            ],
            { stacked: false, legend: true, fillOpacity: 0.18 },
        );
        
        // Engagement tab charts
        charts.engagementType = createEngagementTypeChart('engagementTypeChart');
        charts.engagementTrend = createLineChart('engagementTrendChart', '#22c55e', 'Engagements');
    }

    function createEngagementTypeChart(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        return new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Loading...'],
                datasets: [
                    {
                        data: [1],
                        backgroundColor: ['#475569'],
                        borderWidth: 0,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                cutout: '60%',
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#cbd5f5',
                            font: { size: 11 },
                            padding: 12,
                            usePointStyle: true,
                        },
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const label = context.label || '';
                                const value = context.raw || 0;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total ? ((value / total) * 100).toFixed(1) : 0;
                                return `${label}: ${formatNumber(value)} (${percentage}%)`;
                            },
                        },
                    },
                },
            },
        });
    }

    function createAttributionChart(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        return new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label: 'Ad Conversions',
                        data: [],
                        borderColor: '#fbbf24',
                        backgroundColor: withAlpha('#fbbf24', 0.15),
                        borderWidth: 2,
                        tension: 0.35,
                        pointRadius: 0,
                    },
                    {
                        label: 'GA4 CPC Sessions',
                        data: [],
                        borderColor: '#22d3ee',
                        backgroundColor: withAlpha('#22d3ee', 0.15),
                        borderWidth: 2,
                        tension: 0.35,
                        pointRadius: 0,
                    },
                ],
            },
            options: buildChartOptions({ legend: true }),
        });
    }

    function createLineChart(canvasId, color, label) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        return new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: [
                    {
                        label,
                        data: [],
                        borderColor: color,
                        backgroundColor: withAlpha(color, 0.18),
                        borderWidth: 2,
                        tension: 0.35,
                        pointRadius: 0,
                        fill: false,
                    },
                ],
            },
            options: buildChartOptions(),
        });
    }

    function createDoughnutChart(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        return new Chart(canvas.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Google Ads', 'Facebook Ads'],
                datasets: [
                    {
                        data: [0, 0],
                        backgroundColor: ['#22c55e', '#3b82f6'],
                        borderWidth: 0,
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        labels: {
                            color: '#cbd5f5',
                            font: { size: 10 },
                        },
                    },
                },
            },
        });
    }

    function createMultiDatasetChart(canvasId, datasetConfigs, options = {}) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        const chart = new Chart(canvas.getContext('2d'), {
            type: 'line',
            data: {
                labels: [],
                datasets: datasetConfigs.map((dataset) => ({
                    label: dataset.label,
                    data: [],
                    borderColor: dataset.color,
                    backgroundColor: withAlpha(dataset.color, options.fillOpacity ?? 0.2),
                    borderWidth: 2,
                    tension: 0.35,
                    pointRadius: 0,
                    fill: options.stacked ?? false,
                })),
            },
            options: buildChartOptions({ stacked: options.stacked, legend: options.legend }),
        });

        chart.__datasetKeys = datasetConfigs.map((dataset) => dataset.key || dataset.label);
        return chart;
    }

    function createPaidDailyChart(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        return new Chart(canvas.getContext('2d'), {
            data: {
                labels: [],
                datasets: [
                    {
                        type: 'bar',
                        label: 'Google Spend',
                        backgroundColor: 'rgba(34, 197, 94, 0.55)',
                        borderRadius: 4,
                        data: [],
                    },
                    {
                        type: 'bar',
                        label: 'Facebook Spend',
                        backgroundColor: 'rgba(59, 130, 246, 0.5)',
                        borderRadius: 4,
                        data: [],
                    },
                    {
                        type: 'line',
                        label: 'Google Conversions',
                        borderColor: '#fbbf24',
                        backgroundColor: 'transparent',
                        yAxisID: 'y1',
                        tension: 0.35,
                        borderWidth: 2,
                        pointRadius: 0,
                        data: [],
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                scales: {
                    x: {
                        stacked: true,
                        ticks: { color: '#94a3b8' },
                        grid: { display: false },
                    },
                    y: {
                        stacked: true,
                        ticks: { color: '#94a3b8', callback: (value) => `$${value}` },
                        grid: { color: 'rgba(148, 163, 184, 0.12)' },
                    },
                    y1: {
                        position: 'right',
                        ticks: { color: '#fbbf24' },
                        grid: { drawOnChartArea: false },
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#cbd5f5', font: { size: 10 } },
                    },
                },
            },
        });
    }

    function createCampaignEfficiencyChart(canvasId) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return null;

        return new Chart(canvas.getContext('2d'), {
            type: 'bubble',
            data: {
                datasets: [
                    {
                        label: 'Google Campaigns',
                        backgroundColor: 'rgba(34, 197, 94, 0.6)',
                        borderColor: '#22c55e',
                        data: [],
                    },
                    {
                        label: 'Facebook Campaigns',
                        backgroundColor: 'rgba(59, 130, 246, 0.6)',
                        borderColor: '#3b82f6',
                        data: [],
                    },
                ],
            },
            options: {
                maintainAspectRatio: false,
                scales: {
                    x: {
                        title: { display: true, text: 'Spend ($)', color: '#94a3b8', font: { size: 11 } },
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148, 163, 184, 0.12)' },
                    },
                    y: {
                        title: { display: true, text: 'Conversions', color: '#94a3b8', font: { size: 11 } },
                        ticks: { color: '#94a3b8' },
                        grid: { color: 'rgba(148, 163, 184, 0.12)' },
                    },
                },
                plugins: {
                    legend: {
                        labels: { color: '#cbd5f5', font: { size: 10 } },
                    },
                    tooltip: {
                        callbacks: {
                            label(context) {
                                const { raw } = context;
                                const spend = formatCurrency(raw.x, 2);
                                const conversions = raw.y.toFixed(2);
                                return `${raw.campaign}: Spend ${spend}, Conversions ${conversions}, Clicks ~ ${Math.round(raw.r ** 2)}`;
                            },
                        },
                    },
                },
                onClick(event, elements) {
                    if (!elements.length) return;
                    const element = elements[0];
                    const dataset = this.data.datasets[element.datasetIndex];
                    const point = dataset.data[element.index];
                    if (!point) return;
                    if (point.source === 'google') {
                        const campaign = state.googleCampaigns[point.campaignIndex];
                        if (campaign) {
                            openCampaignDrilldown('Google Ads', campaign);
                        }
                    } else if (point.source === 'facebook') {
                        const campaign = state.facebookCampaigns[point.campaignIndex];
                        if (campaign) {
                            openCampaignDrilldown('Facebook Ads', campaign);
                        }
                    }
                },
            },
        });
    }

    function initDrilldownPanel() {
        const panel = document.getElementById('campaignDrilldown');
        const closeBtn = document.getElementById('drilldownClose');
        if (!panel || !closeBtn) return;
        closeBtn.addEventListener('click', () => {
            panel.classList.remove('active');
            state.selectedCampaign = null;
        });
    }

    function openCampaignDrilldown(sourceLabel, campaign) {
        const panel = document.getElementById('campaignDrilldown');
        const title = document.getElementById('drilldownTitle');
        const body = document.getElementById('drilldownBody');
        if (!panel || !title || !body) return;
        title.textContent = `${sourceLabel}: ${campaign.name || 'Campaign'}`;

        const fields = [
            { label: 'Spend', value: formatCurrency(campaign.spend, 2) },
            { label: 'Clicks', value: formatNumber(campaign.clicks) },
            { label: 'Impressions', value: formatNumber(campaign.impressions) },
            { label: 'Conversions', value: formatNumber(campaign.conversions) },
            { label: 'Cost / Conv.', value: campaign.cost_per_conversion ? formatCurrency(campaign.cost_per_conversion, 2) : '—' },
            { label: 'ROAS', value: campaign.roas ? `${campaign.roas.toFixed(2)}x` : '—' },
            { label: 'CTR', value: campaign.ctr ? `${campaign.ctr.toFixed(2)}%` : '—' },
        ];

        let html = fields
            .map(
                (field) => `
                    <div class="stats-row">
                        <div class="stats-label">${field.label}</div>
                        <div class="stats-value">${field.value}</div>
                    </div>
                `,
            )
            .join('');

        if (state.conversionPaths?.length) {
            html += `
                <div class="stats-row" style="border-top: 1px solid #334155; margin-top: 6px;"></div>
                <div class="stats-label" style="margin-top:6px;">GA4 Conversion Paths</div>
            `;
            html += state.conversionPaths
                .slice(0, 3)
                .map(
                    (entry) => `
                        <div class="stats-row">
                            <div class="stats-label">${entry.path}</div>
                            <div class="stats-value">${formatNumber(entry.conversions)}</div>
                        </div>
                    `,
                )
                .join('');
        }

        body.innerHTML = html;

        panel.classList.add('active');
        recordRecentCampaign(sourceLabel, campaign);
    }

    function recordRecentCampaign(sourceLabel, campaign) {
        const entry = {
            source: sourceLabel,
            name: campaign.name || 'Campaign',
            timestamp: Date.now(),
        };
        state.recentCampaigns = [entry, ...state.recentCampaigns.filter((item) => item.name !== entry.name)].slice(0, 5);
        renderRecentCampaigns();
    }

    function renderRecentCampaigns() {
        const container = document.getElementById('recentCampaigns');
        if (!container) return;
        if (!state.recentCampaigns.length) {
            container.innerHTML = `<div class="stats-row"><div class="stats-label">No recent campaigns</div></div>`;
            return;
        }
        container.innerHTML = state.recentCampaigns
            .map(
                (entry) => `
                    <div class="stats-row">
                        <div class="stats-label">${entry.source}</div>
                        <div class="stats-value">${entry.name}</div>
                    </div>
                `,
            )
            .join('');
    }

    function filterCampaignsBySegment(campaigns = []) {
        if (state.segment === 'all') return campaigns;
        return campaigns.filter((campaign) => {
            const segment = campaign.segment || determineSegment(campaign.name || '');
            campaign.segment = segment;
            return segment === state.segment;
        });
    }

    function determineSegment(name = '') {
        const lower = name.toLowerCase();
        if (SEGMENT_KEYWORDS.recruiting.some((keyword) => lower.includes(keyword))) {
            return 'recruiting';
        }
        if (SEGMENT_KEYWORDS.client.some((keyword) => lower.includes(keyword))) {
            return 'client';
        }
        return 'client';
    }

    function buildGoogleMetricsFromCampaigns(campaigns, days = 30, base) {
        const totals = aggregateCampaigns(campaigns);
        const perDay = days ? totals.spend / days : totals.spend;
        return {
            currency_code: base?.currency_code || 'USD',
            spend: {
                total: roundNumber(totals.spend, 2),
                per_day: roundNumber(perDay, 2),
                daily: [],
            },
            performance: {
                clicks: Math.round(totals.clicks),
                impressions: Math.round(totals.impressions),
                conversions: roundNumber(totals.conversions, 2),
                conversion_value: roundNumber(totals.conversion_value, 2),
            },
            efficiency: {
                ctr: roundNumber(totals.impressions ? (totals.clicks / totals.impressions) * 100 : 0, 2),
                cpc: roundNumber(totals.clicks ? totals.spend / totals.clicks : 0, 2),
                cpm: roundNumber(totals.impressions ? (totals.spend / totals.impressions) * 1000 : 0, 2),
                cost_per_conversion: roundNumber(totals.conversions ? totals.spend / totals.conversions : 0, 2),
                roas: roundNumber(totals.spend ? totals.conversion_value / totals.spend : 0, 2),
                conversion_rate: roundNumber(totals.clicks ? (totals.conversions / totals.clicks) * 100 : 0, 2),
            },
            campaigns,
        };
    }

    function buildFacebookMetricsFromCampaigns(campaigns) {
        const totals = aggregateCampaigns(campaigns);
        return {
            spend: roundNumber(totals.spend, 2),
            impressions: Math.round(totals.impressions),
            clicks: Math.round(totals.clicks),
            reach: Math.round(totals.impressions),
            cpc: roundNumber(totals.clicks ? totals.spend / totals.clicks : 0, 2),
            cpm: roundNumber(totals.impressions ? (totals.spend / totals.impressions) * 1000 : 0, 2),
            ctr: roundNumber(totals.impressions ? (totals.clicks / totals.impressions) * 100 : 0, 2),
            conversions: Math.round(totals.conversions),
            daily: [],
            delivery_rate: null,
        };
    }

    function aggregateCampaigns(campaigns = []) {
        return campaigns.reduce(
            (acc, campaign) => {
                acc.spend += safeNumber(campaign.spend) ?? 0;
                acc.clicks += safeNumber(campaign.clicks) ?? 0;
                acc.impressions += safeNumber(campaign.impressions) ?? 0;
                acc.conversions += safeNumber(campaign.conversions) ?? 0;
                acc.conversion_value += safeNumber(campaign.conversion_value) ?? 0;
                return acc;
            },
            { spend: 0, clicks: 0, impressions: 0, conversions: 0, conversion_value: 0 },
        );
    }

    function buildChartOptions({ stacked = false, legend = false } = {}) {
        return {
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: legend,
                    labels: {
                        color: '#cbd5f5',
                        font: { size: 10 },
                    },
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                },
            },
            interaction: {
                mode: 'index',
                intersect: false,
            },
            scales: {
                x: {
                    ticks: {
                        color: '#94a3b8',
                        maxTicksLimit: 7,
                    },
                    grid: {
                        display: false,
                    },
                },
                y: {
                    ticks: {
                        color: '#94a3b8',
                        callback: (value) => formatAxisValue(value),
                    },
                    grid: {
                        color: 'rgba(148, 163, 184, 0.12)',
                    },
                    stacked,
                },
            },
        };
    }

    function updateLineChart(chart, labels, datasetValues) {
        if (!chart) return;
        chart.data.labels = labels;
        chart.data.datasets[0].data = datasetValues;
        chart.update();
    }

    function updateMultiDatasetChart(chart, labels, datasetValues) {
        if (!chart) return;
        chart.data.labels = labels;
        chart.data.datasets.forEach((dataset, index) => {
            dataset.data = datasetValues[index] || [];
        });
        chart.update();
    }

    function calculateDateRange(preset) {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        
        const end = new Date(today);
        const start = new Date(today);

        switch (preset) {
            case 'today':
                // Today only
                start.setTime(today.getTime());
                end.setTime(today.getTime());
                break;
            case 'yesterday': {
                // Yesterday only
                start.setDate(today.getDate() - 1);
                end.setDate(today.getDate() - 1);
                break;
            }
            case 'last_7_days':
                // Last 7 days including today
                start.setDate(today.getDate() - 6);
                end.setTime(today.getTime());
                break;
            case 'last_30_days':
                // Last 30 days including today
                start.setDate(today.getDate() - 29);
                end.setTime(today.getTime());
                break;
            case 'month_to_date':
                // From first day of current month to today
                start.setDate(1);
                end.setTime(today.getTime());
                break;
            case 'quarter_to_date': {
                // From first day of current quarter to today
                const quarter = Math.floor(today.getMonth() / 3);
                start.setMonth(quarter * 3, 1);
                end.setTime(today.getTime());
                break;
            }
            case 'year_to_date':
                // From first day of current year to today
                start.setMonth(0, 1);
                end.setTime(today.getTime());
                break;
            case 'last_12_months':
                // Last 12 months including current month
                start.setMonth(today.getMonth() - 11, 1);
                end.setTime(today.getTime());
                break;
            default:
                // Default to last 30 days
                start.setDate(today.getDate() - 29);
                end.setTime(today.getTime());
        }

        return {
            start: formatDateForApi(start),
            end: formatDateForApi(end),
        };
    }

    function updateDateRangeDisplay(start, end, preset) {
        updateRangeLabel({
            start,
            end,
            preset,
            targetId: 'dateRangeDisplay',
            updateCardLabels: true,
        });
    }

    function updateRangeLabel({ start, end, preset, targetId, updateCardLabels = false }) {
        if (!targetId) return;

        const label = PRESET_LABELS[preset] || 'Custom range';
        let displayText = label;

        if (start && end) {
            const startDate = new Date(start);
            const endDate = new Date(end);
            displayText = `${label} (${formatShortDate(startDate)} - ${formatShortDate(endDate)})`;
        }

        const target = document.getElementById(targetId);
        if (target) {
            target.textContent = displayText;
        }

        if (updateCardLabels) {
            document.querySelectorAll('.card-label').forEach((element) => {
                const text = element.textContent.toLowerCase();
                if (text.includes('last') || text.includes('days')) {
                    element.textContent = label;
                }
            });
        }
    }

    function setText(id, value = '—') {
        const element = document.getElementById(id);
        if (!element) return;
        element.textContent = value ?? '—';
    }

    function setTargetBadge(id, metricValue, targetValue, isPercent = false) {
        const element = document.getElementById(id);
        if (!element || targetValue === undefined || metricValue === null || metricValue === undefined) return;

        const diff = metricValue - targetValue;
        const badge = document.createElement('span');
        badge.className = 'target-badge';
        const formattedDiff = isPercent ? `${diff >= 0 ? '+' : ''}${diff.toFixed(1)}% vs target` : `${diff >= 0 ? '+' : ''}${formatCurrency(diff, 0)}`;
        badge.textContent = formattedDiff;

        const existingBadge = element.querySelector('.target-badge');
        if (existingBadge) {
            existingBadge.textContent = formattedDiff;
        } else {
            element.appendChild(badge);
        }
    }

    function updatePill(id, text = '—') {
        const element = document.getElementById(id);
        if (!element) return;
        element.textContent = text;
    }

    function setChangeValue(id, changeValue) {
        const element = document.getElementById(id);
        if (!element) return;

        if (changeValue === undefined || changeValue === null || Number.isNaN(changeValue)) {
            element.className = 'metric-change';
            element.textContent = '—';
            return;
        }

        const isPositive = changeValue >= 0;
        element.className = `metric-change ${isPositive ? 'positive' : 'negative'}`;
        const symbol = isPositive ? '▲' : '▼';
        element.textContent = `${symbol} ${Math.abs(changeValue).toFixed(1)}%`;
    }

    function formatCurrency(value, digits = 0, currency = 'USD') {
        if (value === undefined || value === null || Number.isNaN(Number(value))) return '—';
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency,
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(Number(value));
    }

    function formatNumber(value, options = {}) {
        if (value === undefined || value === null || Number.isNaN(Number(value))) return '—';
        return Number(value).toLocaleString('en-US', options);
    }

    function formatPercent(value, digits = 2) {
        if (value === undefined || value === null || Number.isNaN(Number(value))) return '—';
        return `${Number(value).toFixed(digits)}%`;
    }

    function formatShortDate(date) {
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    }

    function formatTimelineTime(timestamp) {
        const date = new Date(timestamp);
        if (Number.isNaN(date.getTime())) {
            return '';
        }
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    function formatChartLabel(date) {
        if (!date) return '';
        const parsed = new Date(date);
        if (Number.isNaN(parsed.getTime())) {
            return date;
        }
        return `${parsed.getMonth() + 1}/${parsed.getDate()}`;
    }

    function formatDateForApi(date) {
        if (!date) return null;
        const tzOffset = date.getTimezoneOffset() * 60000;
        return new Date(date.getTime() - tzOffset).toISOString().split('T')[0];
    }

    function formatAxisValue(value) {
        if (value === 0) return '0';
        if (Math.abs(value) >= 1000) {
            return `${(value / 1000).toFixed(1)}k`;
        }
        return value;
    }

    function roundNumber(value, digits = 2) {
        if (value === undefined || value === null || Number.isNaN(Number(value))) return 0;
        const factor = 10 ** digits;
        return Math.round(Number(value) * factor) / factor;
    }

    function safeNumber(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : null;
    }

    function withAlpha(color, alpha) {
        if (!color || color.startsWith('rgba')) return color;
        const hex = color.replace('#', '');
        if (hex.length !== 6) return color;
        const r = parseInt(hex.slice(0, 2), 16);
        const g = parseInt(hex.slice(2, 4), 16);
        const b = parseInt(hex.slice(4, 6), 16);
        return `rgba(${r}, ${g}, ${b}, ${alpha})`;
    }

    function calculateDailyTrend(daily = []) {
        if (!Array.isArray(daily) || daily.length < 4) return null;
        const midpoint = Math.floor(daily.length / 2);
        if (midpoint < 1) return null;

        const firstSlice = daily.slice(0, midpoint);
        const secondSlice = daily.slice(midpoint);

        const firstAverage = average(firstSlice.map((entry) => Number(entry.spend) || 0));
        const secondAverage = average(secondSlice.map((entry) => Number(entry.spend) || 0));

        if (!firstAverage) return null;
        return ((secondAverage - firstAverage) / firstAverage) * 100;
    }

    function average(values) {
        if (!values.length) return 0;
        const total = values.reduce((sum, value) => sum + value, 0);
        return total / values.length;
    }
})();

