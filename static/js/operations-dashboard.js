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
        setKPI('kpi-evv-rate', `${s.evv_compliance || 0}%`, s.evv_compliance < 85 ? 'warning' : 'positive');
        setKPI('kpi-plans-due', s.plans_due_review || 0, s.plans_due_review > 3 ? 'warning' : '');
        setKPI('kpi-at-risk', s.at_risk_clients || 0, s.at_risk_clients > 0 ? 'negative' : 'positive');
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

    // Global refresh function
    window.refreshData = function () {
        fetchAllData();
    };
})();
