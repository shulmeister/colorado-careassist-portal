/* global Chart */
(function () {
    'use strict';

    const API_BASE = '/api/marketing';
    const PRESET_LABELS = {
        last_7_days: 'Last 7 days',
        last_30_days: 'Last 30 days',
        month_to_date: 'Month to date',
        quarter_to_date: 'Quarter to date',
        year_to_date: 'Year to date',
        last_12_months: 'Last 12 months',
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
    };

    const state = {
        preset: 'last_30_days',
        selectedCampaign: null,
        latestGoogleData: null,
        latestGa4Data: null,
        googleCampaigns: [],
        facebookCampaigns: [],
        conversionPaths: [],
    };

    document.addEventListener('DOMContentLoaded', () => {
        initTabNavigation();
        initCharts();
        initDrilldownPanel();
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
            const [adsResult, socialResult, websiteResult, emailResult] = await Promise.allSettled([
                fetchJson(`${API_BASE}/ads?from=${start}&to=${end}`),
                fetchJson(`${API_BASE}/social?from=${start}&to=${end}`),
                fetchJson(`${API_BASE}/website?from=${start}&to=${end}`),
                fetchJson(`${API_BASE}/email?from=${start}&to=${end}`),
            ]);

            const ads = adsResult.status === 'fulfilled' ? adsResult.value : null;
            const social = socialResult.status === 'fulfilled' ? socialResult.value : null;
            const website = websiteResult.status === 'fulfilled' ? websiteResult.value : null;
            const email = emailResult.status === 'fulfilled' ? emailResult.value : null;

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

            renderDashboard({
                ads,
                social,
                website,
                email,
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

    function renderDashboard({ ads, social, website, email, preset, fallbackRange }) {
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
    }

    function renderAdsSection(payload, preset) {
        if (!payload?.data) return;

        const google = payload.data.google_ads;
        const facebookAccount = payload.data.facebook_ads?.account;
        const facebookCampaigns = payload.data.facebook_ads?.campaigns || [];

        renderGoogleOverview(google);
        renderFacebookOverview(facebookAccount);
        renderCampaignTables(google?.campaigns || [], facebookCampaigns);
        renderPaidSummary(google, facebookAccount, payload.range, preset);
        updateAdsCharts(google);
        updatePaidDailyChart(google, facebookAccount);
        updateCampaignEfficiencyChart(google?.campaigns || [], facebookCampaigns);
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

        const costPerConv = safeNumber(google.efficiency?.cost_per_conversion);
        updatePill(
            'googleCostPerConvPill',
            costPerConv !== null ? `Cost/Conv ${formatCurrency(costPerConv, 2, currency)}` : 'Cost/Conv —',
        );

        setText('totalImpressions', formatNumber(google.performance?.impressions));
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
                googleBody.innerHTML = `<tr><td colspan="6" class="empty-state-text">No Google Ads campaigns found</td></tr>`;
            } else {
                googleBody.innerHTML = googleCampaigns.slice(0, 6).map((campaign, index) => {
                    const roasText = campaign.roas ? `${campaign.roas.toFixed(2)}x` : '—';
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
                            <td>${roasText}</td>
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
        renderPaidAlerts(evaluatePaidAlerts({
            roasValue,
            conversionRate,
            blendedCpc,
            blendedCostPerConv,
            blendedCpm,
            facebookDelivery: facebookAccount?.delivery_rate,
            facebookCtr: facebookAccount?.ctr,
        }));
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
        const end = new Date();
        end.setHours(0, 0, 0, 0);
        const start = new Date(end);

        const shiftDays = (days) => {
            start.setDate(end.getDate() - (days - 1));
        };

        switch (preset) {
            case 'last_7_days':
                shiftDays(7);
                break;
            case 'last_30_days':
                shiftDays(30);
                break;
            case 'month_to_date':
                start.setDate(1);
                break;
            case 'quarter_to_date': {
                const quarter = Math.floor(end.getMonth() / 3);
                start.setMonth(quarter * 3, 1);
                break;
            }
            case 'year_to_date':
                start.setMonth(0, 1);
                break;
            case 'last_12_months':
                start.setMonth(end.getMonth() - 11, 1);
                break;
            default:
                shiftDays(30);
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

