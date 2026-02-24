/* global Chart */
(function () {
    'use strict';

    const API_BASE = '/api/operations';

    const charts = {
        shifts: null,
        clientStatus: null,
    };

    const state = {
        summary: null,
        clients: [],
        carePlans: [],
        openShifts: [],
        atRiskClients: [],
        isLoading: false,
        // Gigi state
        gigiSettings: {
            sms_autoreply: false,
            operations_sms: false,
        },
        gigiActivity: [],
        callOuts: [],
    };

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', () => {
        initTabNavigation();
        initCharts();
        fetchAllData();
    });

    // Tab navigation
    function initTabNavigation() {
        const sidebarLinks = Array.from(document.querySelectorAll('.sidebar-link'));
        const tabSections = Array.from(document.querySelectorAll('.tab-content'));

        sidebarLinks.forEach((link) => {
            link.addEventListener('click', (event) => {
                event.preventDefault();
                const tabId = link.getAttribute('data-tab');
                if (!tabId) return;

                // Update active states
                sidebarLinks.forEach((l) => l.classList.remove('active'));
                link.classList.add('active');

                // Show corresponding tab
                tabSections.forEach((section) => {
                    section.classList.toggle('active', section.id === `tab-${tabId}`);
                });
            });
        });
    }

    // Initialize charts
    function initCharts() {
        const chartDefaults = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    labels: { color: '#94a3b8', font: { size: 11 } },
                },
            },
            scales: {
                x: {
                    ticks: { color: '#64748b', font: { size: 10 } },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                },
                y: {
                    ticks: { color: '#64748b', font: { size: 10 } },
                    grid: { color: 'rgba(51, 65, 85, 0.5)' },
                },
            },
        };

        // Shifts bar chart
        const shiftsCtx = document.getElementById('shiftsChart');
        if (shiftsCtx) {
            charts.shifts = new Chart(shiftsCtx, {
                type: 'bar',
                data: {
                    labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                    datasets: [
                        {
                            label: 'Scheduled',
                            data: [0, 0, 0, 0, 0, 0, 0],
                            backgroundColor: 'rgba(59, 130, 246, 0.7)',
                            borderRadius: 4,
                        },
                        {
                            label: 'Open',
                            data: [0, 0, 0, 0, 0, 0, 0],
                            backgroundColor: 'rgba(239, 68, 68, 0.7)',
                            borderRadius: 4,
                        },
                    ],
                },
                options: {
                    ...chartDefaults,
                    plugins: {
                        ...chartDefaults.plugins,
                        legend: { position: 'bottom', labels: { color: '#94a3b8' } },
                    },
                },
            });
        }

        // Client status doughnut chart
        const clientStatusCtx = document.getElementById('clientStatusChart');
        if (clientStatusCtx) {
            charts.clientStatus = new Chart(clientStatusCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Active', 'On Hold', 'At Risk', 'Pending'],
                    datasets: [{
                        data: [0, 0, 0, 0],
                        backgroundColor: [
                            'rgba(34, 197, 94, 0.8)',
                            'rgba(59, 130, 246, 0.8)',
                            'rgba(239, 68, 68, 0.8)',
                            'rgba(245, 158, 11, 0.8)',
                        ],
                        borderWidth: 0,
                    }],
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    cutout: '60%',
                    plugins: {
                        legend: { position: 'right', labels: { color: '#94a3b8', padding: 12 } },
                    },
                },
            });
        }
    }

    // Fetch all data
    async function fetchAllData() {
        state.isLoading = true;

        try {
            const [summary, clients, carePlans, openShifts, atRisk] = await Promise.all([
                fetchAPI('/summary'),
                fetchAPI('/clients'),
                fetchAPI('/care-plans'),
                fetchAPI('/open-shifts'),
                fetchAPI('/at-risk'),
            ]);

            state.summary = summary;
            state.clients = clients?.clients || [];
            state.carePlans = carePlans?.care_plans || [];
            state.openShifts = openShifts?.shifts || [];
            state.atRiskClients = atRisk?.clients || [];

            updateDashboard();
            loadHoursBreakdown();
        } catch (error) {
            console.error('Failed to fetch data:', error);
        } finally {
            state.isLoading = false;
        }
    }

    // API fetch helper
    async function fetchAPI(endpoint) {
        try {
            const response = await fetch(`${API_BASE}${endpoint}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`API error (${endpoint}):`, error);
            return null;
        }
    }

    // Update all dashboard components
    function updateDashboard() {
        updateKPIs();
        updateCharts();
        updateClientsTable();
        updateCarePlansTable();
        updateShiftsTable();
        updateAtRiskTable();
        updateWellSkyBanner();
    }

    // Update KPI cards
    function updateKPIs() {
        const s = state.summary;
        if (!s) return;

        setKPI('kpi-active-clients', s.active_clients || 0);
        setKPI('kpi-active-caregivers', s.active_caregivers || 0);
        setKPI('kpi-open-shifts', s.open_shifts || 0, s.open_shifts > 5 ? 'warning' : '');

        // Weekly hours + % to goal
        const weeklyHrs = s.weekly_hours || 0;
        setKPI('kpi-weekly-hours', weeklyHrs.toLocaleString());
        const goalEl = document.getElementById('kpi-hours-goal');
        if (goalEl) {
            const pct = s.hours_pct_goal || 0;
            goalEl.textContent = `${pct}% of 10k goal`;
        }

        // Profit per hour
        const prof = s.profitability || {};
        if (prof.profit_per_hour != null) {
            setKPI('kpi-profit-per-hour', `$${prof.profit_per_hour.toFixed(2)}`, 'positive');
        }
        const profPctEl = document.getElementById('kpi-profit-pct');
        if (profPctEl && prof.profit_pct != null) {
            profPctEl.textContent = `${prof.profit_pct}% margin`;
        }

        setKPI('kpi-at-risk', s.at_risk_clients || 0, s.at_risk_clients > 0 ? 'negative' : 'positive');

        // Profitability detail cards
        if (prof.revenue_per_hour != null) {
            setKPI('kpi-revenue-per-hour', `$${prof.revenue_per_hour.toFixed(2)}`);
        }
        if (prof.payroll_per_hour != null) {
            setKPI('kpi-payroll-per-hour', `$${prof.payroll_per_hour.toFixed(2)}`);
        }
        if (prof.profit_per_hour != null) {
            setKPI('kpi-profit-per-hour-detail', `$${prof.profit_per_hour.toFixed(2)}`, 'positive');
        }
        if (prof.total_billing_mtd != null) {
            setKPI('kpi-billing-mtd', `$${Math.round(prof.total_billing_mtd).toLocaleString()}`);
        }
        if (prof.total_payroll_mtd != null) {
            setKPI('kpi-payroll-mtd', `$${Math.round(prof.total_payroll_mtd).toLocaleString()}`);
        }
        if (prof.total_profit_mtd != null) {
            setKPI('kpi-profit-mtd', `$${Math.round(prof.total_profit_mtd).toLocaleString()}`, 'positive');
        }
    }

    function setKPI(id, value, className = '') {
        const el = document.getElementById(id);
        if (el) {
            el.textContent = value;
            el.className = 'kpi-value' + (className ? ` ${className}` : '');
        }
    }

    // Update charts
    function updateCharts() {
        // Update shifts chart with weekly data
        if (charts.shifts && state.summary?.shifts_by_day) {
            const shiftData = state.summary.shifts_by_day;
            charts.shifts.data.datasets[0].data = shiftData.scheduled || [0, 0, 0, 0, 0, 0, 0];
            charts.shifts.data.datasets[1].data = shiftData.open || [0, 0, 0, 0, 0, 0, 0];
            charts.shifts.update();
        }

        // Update client status chart
        if (charts.clientStatus && state.clients.length > 0) {
            const statusCounts = { active: 0, on_hold: 0, at_risk: 0, pending: 0 };
            state.clients.forEach((client) => {
                const status = (client.status || 'active').toLowerCase().replace(' ', '_');
                if (statusCounts.hasOwnProperty(status)) {
                    statusCounts[status]++;
                } else {
                    statusCounts.active++;
                }
            });
            charts.clientStatus.data.datasets[0].data = [
                statusCounts.active,
                statusCounts.on_hold,
                statusCounts.at_risk,
                statusCounts.pending,
            ];
            charts.clientStatus.update();
        }
    }

    // Update clients table
    function updateClientsTable() {
        const tbody = document.getElementById('clients-table-body');
        if (!tbody) return;

        if (state.clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="icon">👥</div>No clients found</td></tr>';
            return;
        }

        tbody.innerHTML = state.clients.map((client) => {
            const riskClass = getRiskClass(client.risk_score);
            return `
                <tr>
                    <td><strong>${escapeHtml(client.name)}</strong></td>
                    <td><span class="status-badge status-${getStatusClass(client.status)}">${client.status || 'Active'}</span></td>
                    <td>${client.hours_per_week || '--'}</td>
                    <td>${escapeHtml(client.payer || 'N/A')}</td>
                    <td>
                        <div class="risk-score ${riskClass}">
                            <div class="risk-bar"><div class="risk-fill" style="width: ${client.risk_score || 0}%"></div></div>
                            <span>${client.risk_score || 0}</span>
                        </div>
                    </td>
                    <td>${formatDate(client.last_visit)}</td>
                </tr>
            `;
        }).join('');
    }

    // Update care plans table
    function updateCarePlansTable() {
        const tbody = document.getElementById('care-plans-table-body');
        if (!tbody) return;

        if (state.carePlans.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state"><div class="icon">📋</div>No care plans due for review</td></tr>';
            return;
        }

        tbody.innerHTML = state.carePlans.map((plan) => {
            const daysUntil = plan.days_until_review || 0;
            const urgencyClass = daysUntil <= 7 ? 'danger' : daysUntil <= 14 ? 'warning' : 'info';
            return `
                <tr>
                    <td><strong>${escapeHtml(plan.client_name)}</strong></td>
                    <td><span class="status-badge status-${urgencyClass}">${plan.status || 'Active'}</span></td>
                    <td>${formatDate(plan.review_date)}</td>
                    <td><span class="status-badge status-${urgencyClass}">${daysUntil} days</span></td>
                    <td>${plan.authorized_hours || '--'} hrs/week</td>
                </tr>
            `;
        }).join('');
    }

    // Update shifts table
    function updateShiftsTable() {
        const tbody = document.getElementById('shifts-table-body');
        if (!tbody) return;

        if (state.openShifts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="icon">✅</div>No open shifts - all coverage filled!</td></tr>';
            return;
        }

        tbody.innerHTML = state.openShifts.map((shift) => {
            return `
                <tr>
                    <td>${formatDate(shift.date)}</td>
                    <td>${shift.start_time} - ${shift.end_time}</td>
                    <td><strong>${escapeHtml(shift.client_name)}</strong></td>
                    <td>${escapeHtml(shift.location || 'N/A')}</td>
                    <td>${shift.hours || '--'}</td>
                    <td><span class="status-badge status-open">Open</span></td>
                </tr>
            `;
        }).join('');
    }

    // Update at-risk table
    function updateAtRiskTable() {
        const tbody = document.getElementById('at-risk-table-body');
        if (!tbody) return;

        if (state.atRiskClients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state"><div class="icon">🎉</div>No at-risk clients!</td></tr>';
            return;
        }

        tbody.innerHTML = state.atRiskClients.map((client) => {
            const riskClass = getRiskClass(client.risk_score);
            return `
                <tr>
                    <td><strong>${escapeHtml(client.name)}</strong></td>
                    <td>
                        <div class="risk-score ${riskClass}">
                            <div class="risk-bar"><div class="risk-fill" style="width: ${client.risk_score || 0}%"></div></div>
                            <span>${client.risk_score || 0}</span>
                        </div>
                    </td>
                    <td>${(client.risk_factors || []).map(f => `<span class="status-badge status-warning">${escapeHtml(f)}</span>`).join(' ')}</td>
                    <td>${(client.recommendations || []).map(r => `<div>• ${escapeHtml(r)}</div>`).join('')}</td>
                </tr>
            `;
        }).join('');
    }

    // Update WellSky connection banner
    function updateWellSkyBanner() {
        const banner = document.getElementById('wellskyBanner');
        if (!banner || !state.summary) return;

        if (state.summary.wellsky_connected) {
            banner.classList.add('connected');
            banner.innerHTML = `
                <span class="icon">✅</span>
                <span class="text">Connected to WellSky - Live data</span>
            `;
        } else {
            banner.classList.remove('connected');
            banner.innerHTML = `
                <span class="icon">⏳</span>
                <span class="text">Using mock data - WellSky API not connected</span>
            `;
        }
    }

    // Helper functions
    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function formatDate(dateStr) {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;
        return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    }

    function getRiskClass(score) {
        if (!score) return 'risk-low';
        if (score >= 60) return 'risk-high';
        if (score >= 40) return 'risk-medium';
        return 'risk-low';
    }

    function getStatusClass(status) {
        if (!status) return 'active';
        const s = status.toLowerCase();
        if (s === 'active') return 'active';
        if (s === 'on hold' || s === 'on_hold') return 'info';
        if (s === 'at risk' || s === 'at_risk') return 'danger';
        if (s === 'pending') return 'warning';
        return 'active';
    }

    // Load hours breakdown data
    async function loadHoursBreakdown() {
        try {
            const data = await fetchAPI('/hours-breakdown');
            if (!data) return;

            // Weekly
            if (data.weekly) {
                setKPI('weekly-total-hours', data.weekly.total_hours || 0);
                setKPI('weekly-shifts', data.weekly.shifts || 0);
                setKPI('weekly-clients', data.weekly.clients || 0);
                setKPI('weekly-avg-client', data.weekly.avg_per_client ? `${data.weekly.avg_per_client} hrs` : '--');
            }

            // Monthly
            if (data.monthly) {
                setKPI('monthly-total-hours', data.monthly.total_hours || 0);
                setKPI('monthly-shifts', data.monthly.shifts || 0);
                setKPI('monthly-clients', data.monthly.clients || 0);
                setKPI('monthly-avg-client', data.monthly.avg_per_client ? `${data.monthly.avg_per_client} hrs` : '--');
            }

            // Quarterly
            if (data.quarterly) {
                setKPI('quarterly-total-hours', data.quarterly.total_hours || 0);
                setKPI('quarterly-shifts', data.quarterly.shifts || 0);
                setKPI('quarterly-clients', data.quarterly.clients || 0);
                setKPI('quarterly-avg-client', data.quarterly.avg_per_client ? `${data.quarterly.avg_per_client} hrs` : '--');
            }
        } catch (error) {
            console.error('Failed to load hours breakdown:', error);
        }
    }

    // Global refresh function
    window.refreshData = function () {
        fetchAllData();
    };

    // Global hours refresh
    window.loadHoursBreakdown = loadHoursBreakdown;

    // ============================================
    // GIGI AI AGENT CONTROL FUNCTIONS
    // ============================================

    // Fetch Gigi settings from API
    async function fetchGigiSettings() {
        try {
            const response = await fetch('/api/gigi/settings');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            state.gigiSettings = data;
            updateGigiToggles();
            updateGigiStatus();
        } catch (error) {
            console.error('Failed to fetch Gigi settings:', error);
        }
    }

    // Toggle a Gigi setting
    window.toggleGigiSetting = async function(setting, enabled) {
        const toggle = document.getElementById(`gigi-${setting.replace('_', '-')}`);
        const originalState = toggle ? toggle.checked : !enabled;

        try {
            const response = await fetch('/api/gigi/settings', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ [setting]: enabled }),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const data = await response.json();
            state.gigiSettings = data.settings;

            // Show success notification
            showNotification(`Gigi ${setting.replace('_', ' ')} ${enabled ? 'enabled' : 'disabled'}`, 'success');
            updateGigiStatus();
        } catch (error) {
            console.error('Failed to update Gigi setting:', error);
            // Revert toggle on error
            if (toggle) toggle.checked = originalState;
            showNotification('Failed to update setting', 'error');
        }
    };

    // Update toggle states from current settings
    function updateGigiToggles() {
        const smsToggle = document.getElementById('toggle-sms-autoreply');
        const opsToggle = document.getElementById('toggle-ops-sms');

        if (smsToggle) smsToggle.checked = state.gigiSettings.sms_autoreply;
        if (opsToggle) opsToggle.checked = state.gigiSettings.operations_sms;
    }

    // Update Gigi status displays
    function updateGigiStatus() {
        // Update status indicator
        const statusIndicator = document.getElementById('gigi-status-indicator');
        const statusText = document.getElementById('gigi-status-text');

        const anyEnabled = state.gigiSettings.sms_autoreply || state.gigiSettings.operations_sms;

        if (statusIndicator) {
            statusIndicator.classList.toggle('online', anyEnabled);
            statusIndicator.classList.toggle('offline', !anyEnabled);
        }
        if (statusText) {
            statusText.textContent = anyEnabled ? 'Active' : 'Disabled';
        }

        // Update WellSky status
        const wellskyStatus = document.getElementById('wellsky-status');
        const wellskyApiStatus = document.getElementById('wellsky-api-status');
        if (wellskyStatus && state.gigiSettings) {
            if (state.gigiSettings.wellsky_connected) {
                wellskyStatus.classList.add('online');
                wellskyStatus.classList.remove('partial', 'offline');
                wellskyStatus.querySelector('span:last-child').textContent = 'Connected';
                if (wellskyApiStatus) wellskyApiStatus.textContent = 'Live WellSky API connection';
            } else {
                wellskyStatus.classList.add('partial');
                wellskyStatus.classList.remove('online', 'offline');
                wellskyStatus.querySelector('span:last-child').textContent = 'Mock Mode';
                if (wellskyApiStatus) wellskyApiStatus.textContent = 'Using mock data for testing';
            }
        }
    }

    // Fetch Gigi activity log
    async function fetchGigiActivity() {
        try {
            const response = await fetch('/api/gigi/activity?limit=10');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            state.gigiActivity = data.activities || [];
            updateGigiActivityTable();
        } catch (error) {
            console.error('Failed to fetch Gigi activity:', error);
        }
    }

    // Update Gigi activity log
    function updateGigiActivityTable() {
        const activityLog = document.getElementById('gigi-activity-log');
        if (!activityLog) return;

        if (state.gigiActivity.length === 0) {
            activityLog.innerHTML = '<div class="empty-state"><div class="icon">📭</div>No recent activity</div>';
            return;
        }

        activityLog.innerHTML = state.gigiActivity.map((activity) => {
            const typeIcon = getActivityIcon(activity.type);
            const statusClass = activity.status === 'success' ? 'success' : activity.status === 'failed' ? 'error' : 'warning';
            return `
                <div class="activity-item">
                    <div class="activity-icon">${typeIcon}</div>
                    <div class="activity-content">
                        <div class="activity-title">${escapeHtml(activity.type.replace('_', ' '))}</div>
                        <div class="activity-desc">${escapeHtml(activity.description)}</div>
                    </div>
                    <div class="activity-meta">
                        <span class="status-badge status-${statusClass}">${activity.status}</span>
                        <span class="activity-time">${formatDateTime(activity.timestamp)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    // Fetch call-out log
    async function fetchCallOuts() {
        try {
            const response = await fetch('/api/gigi/callouts?limit=20');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            state.callOuts = data.callouts || [];
            updateCallOutsTable();
        } catch (error) {
            console.error('Failed to fetch call-outs:', error);
        }
    }

    // Update call-outs table
    function updateCallOutsTable() {
        const tbody = document.getElementById('callouts-table-body');
        if (!tbody) return;

        if (state.callOuts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="icon">✅</div>No recent call-outs</td></tr>';
            return;
        }

        tbody.innerHTML = state.callOuts.map((callout) => {
            const statusClass = callout.status === 'covered' ? 'active' :
                               callout.status === 'open' ? 'danger' : 'warning';
            return `
                <tr>
                    <td>${formatDateTime(callout.timestamp)}</td>
                    <td><strong>${escapeHtml(callout.caregiver_name)}</strong></td>
                    <td>${escapeHtml(callout.client_name)}</td>
                    <td>${formatDate(callout.shift_date)} ${callout.shift_time || ''}</td>
                    <td>${escapeHtml(callout.reason)}</td>
                    <td><span class="status-badge status-${statusClass}">${callout.status}</span></td>
                </tr>
            `;
        }).join('');
    }

    // Helper functions for Gigi
    function getActivityIcon(type) {
        const icons = {
            'sms_received': '📨',
            'sms_sent': '📤',
            'voice_call': '📞',
            'callout': '🚨',
            'clock_in': '🟢',
            'clock_out': '🔴',
            'shift_update': '📋',
            'error': '⚠️',
        };
        return icons[type] || '📝';
    }

    function formatDateTime(dateStr) {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;
        return date.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: 'numeric',
            minute: '2-digit',
            hour12: true
        });
    }

    function showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span class="notification-icon">${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span>
            <span class="notification-message">${escapeHtml(message)}</span>
        `;

        // Add to page
        document.body.appendChild(notification);

        // Animate in
        setTimeout(() => notification.classList.add('show'), 10);

        // Remove after delay
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }, 3000);
    }

    // Global Gigi refresh functions
    window.refreshGigiActivity = function() {
        fetchGigiActivity();
    };

    window.refreshCallOuts = function() {
        fetchCallOuts();
    };

    // Load Gigi data when tab is activated
    function loadGigiData() {
        fetchGigiSettings();
        fetchGigiActivity();
    }

    function loadCallOutData() {
        fetchCallOuts();
    }

    // Extend tab navigation to load data on tab switch
    const originalInitTabNavigation = initTabNavigation;
    initTabNavigation = function() {
        const sidebarLinks = Array.from(document.querySelectorAll('.sidebar-link'));
        const tabSections = Array.from(document.querySelectorAll('.tab-content'));

        sidebarLinks.forEach((link) => {
            link.addEventListener('click', (event) => {
                event.preventDefault();
                const tabId = link.getAttribute('data-tab');
                if (!tabId) return;

                // Update active states
                sidebarLinks.forEach((l) => l.classList.remove('active'));
                link.classList.add('active');

                // Show corresponding tab
                tabSections.forEach((section) => {
                    section.classList.toggle('active', section.id === `tab-${tabId}`);
                });

                // Load data for specific tabs
                if (tabId === 'gigi') {
                    loadGigiData();
                } else if (tabId === 'callouts') {
                    loadCallOutData();
                }
            });
        });
    };
})();
