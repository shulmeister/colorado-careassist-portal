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
        openShifts: [],
        callOuts: [],
        isLoading: false,
        clientSortField: 'name',
        clientSortAsc: true,
        clientFilter: '',
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

                sidebarLinks.forEach((l) => l.classList.remove('active'));
                link.classList.add('active');

                tabSections.forEach((section) => {
                    section.classList.toggle('active', section.id === `tab-${tabId}`);
                });

                // Load call-outs when switching to shifts tab
                if (tabId === 'shifts') {
                    fetchCallOuts();
                }
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

        const clientStatusCtx = document.getElementById('clientStatusChart');
        if (clientStatusCtx) {
            charts.clientStatus = new Chart(clientStatusCtx, {
                type: 'doughnut',
                data: {
                    labels: ['Low Risk', 'Medium Risk', 'High Risk'],
                    datasets: [{
                        data: [0, 0, 0],
                        backgroundColor: [
                            'rgba(34, 197, 94, 0.8)',
                            'rgba(245, 158, 11, 0.8)',
                            'rgba(239, 68, 68, 0.8)',
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
            const [summary, clients, openShifts] = await Promise.all([
                fetchAPI('/summary'),
                fetchAPI('/clients'),
                fetchAPI('/open-shifts'),
            ]);

            state.summary = summary;
            state.clients = clients?.clients || [];
            state.openShifts = openShifts?.shifts || [];

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
        updateShiftsTable();
        updateWellSkyBanner();
    }

    // Update KPI cards
    function updateKPIs() {
        const s = state.summary;
        if (!s) return;

        setKPI('kpi-active-clients', s.active_clients || 0);
        setKPI('kpi-active-caregivers', s.active_caregivers || 0);
        setKPI('kpi-open-shifts', s.open_shifts || 0, s.open_shifts > 5 ? 'warning' : '');

        const weeklyHrs = s.weekly_hours || 0;
        setKPI('kpi-weekly-hours', weeklyHrs.toLocaleString());
        const goalEl = document.getElementById('kpi-hours-goal');
        if (goalEl) {
            const pct = s.hours_pct_goal || 0;
            goalEl.textContent = `${pct}% of 10k goal`;
        }

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
        if (prof.revenue_per_hour != null) setKPI('kpi-revenue-per-hour', `$${prof.revenue_per_hour.toFixed(2)}`);
        if (prof.payroll_per_hour != null) setKPI('kpi-payroll-per-hour', `$${prof.payroll_per_hour.toFixed(2)}`);
        if (prof.profit_per_hour != null) setKPI('kpi-profit-per-hour-detail', `$${prof.profit_per_hour.toFixed(2)}`, 'positive');
        if (prof.total_billing_mtd != null) setKPI('kpi-billing-mtd', `$${Math.round(prof.total_billing_mtd).toLocaleString()}`);
        if (prof.total_payroll_mtd != null) setKPI('kpi-payroll-mtd', `$${Math.round(prof.total_payroll_mtd).toLocaleString()}`);
        if (prof.total_profit_mtd != null) setKPI('kpi-profit-mtd', `$${Math.round(prof.total_profit_mtd).toLocaleString()}`, 'positive');
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
        if (charts.shifts && state.summary?.shifts_by_day) {
            const shiftData = state.summary.shifts_by_day;
            charts.shifts.data.datasets[0].data = shiftData.scheduled || [0, 0, 0, 0, 0, 0, 0];
            charts.shifts.data.datasets[1].data = shiftData.open || [0, 0, 0, 0, 0, 0, 0];
            charts.shifts.update();
        }

        if (charts.clientStatus && state.clients.length > 0) {
            let low = 0, med = 0, high = 0;
            state.clients.forEach((c) => {
                if (c.risk_score >= 50) high++;
                else if (c.risk_score >= 25) med++;
                else low++;
            });
            charts.clientStatus.data.datasets[0].data = [low, med, high];
            charts.clientStatus.update();
        }
    }

    // ============================================
    // CLIENTS TABLE WITH EXPAND/COLLAPSE & SORTING
    // ============================================

    function getFilteredSortedClients() {
        let clients = [...state.clients];

        // Filter
        if (state.clientFilter) {
            const q = state.clientFilter.toLowerCase();
            clients = clients.filter(c =>
                (c.name || '').toLowerCase().includes(q) ||
                (c.caregivers || []).some(cg => cg.toLowerCase().includes(q))
            );
        }

        // Sort
        const field = state.clientSortField;
        const asc = state.clientSortAsc;
        clients.sort((a, b) => {
            let va, vb;
            switch (field) {
                case 'name': va = (a.name || '').toLowerCase(); vb = (b.name || '').toLowerCase(); break;
                case 'status': va = a.status || ''; vb = b.status || ''; break;
                case 'hours': va = a.actual_hours_weekly || 0; vb = b.actual_hours_weekly || 0; break;
                case 'profitability': va = a.profitability_pct ?? -999; vb = b.profitability_pct ?? -999; break;
                case 'mv_date': va = a.mv_date || ''; vb = b.mv_date || ''; break;
                case 'care_plan_review': va = a.care_plan_review_date || ''; vb = b.care_plan_review_date || ''; break;
                case 'last_visit': va = a.last_visit || ''; vb = b.last_visit || ''; break;
                case 'risk': va = a.risk_score || 0; vb = b.risk_score || 0; break;
                default: va = (a.name || '').toLowerCase(); vb = (b.name || '').toLowerCase();
            }
            if (va < vb) return asc ? -1 : 1;
            if (va > vb) return asc ? 1 : -1;
            return 0;
        });

        return clients;
    }

    function updateClientsTable() {
        const tbody = document.getElementById('clients-table-body');
        if (!tbody) return;

        const clients = getFilteredSortedClients();

        if (clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="empty-state"><div class="icon">👥</div>No clients found</td></tr>';
            return;
        }

        let html = '';
        clients.forEach((client) => {
            const riskClass = getRiskClass(client.risk_score);
            const profClass = client.profitability_pct != null
                ? (client.profitability_pct >= 30 ? 'profit-positive' : client.profitability_pct >= 0 ? 'profit-neutral' : 'profit-negative')
                : 'profit-neutral';
            const hoursDisplay = client.authorized_hours_weekly
                ? `${client.actual_hours_weekly}/${client.authorized_hours_weekly}`
                : `${client.actual_hours_weekly || '--'}`;

            html += `
                <tr class="client-row" data-client-id="${client.id}" onclick="toggleClientDetail(${client.id})" style="cursor:pointer">
                    <td><button class="expand-btn" id="expand-btn-${client.id}">&#9654;</button></td>
                    <td><strong>${escapeHtml(client.name)}</strong></td>
                    <td><span class="status-badge status-${getStatusClass(client.status)}">${client.status || 'Active'}</span></td>
                    <td>${hoursDisplay}</td>
                    <td class="${profClass}">${client.profitability_pct != null ? client.profitability_pct + '%' : '--'}</td>
                    <td>${formatDate(client.mv_date)}</td>
                    <td>${formatDate(client.care_plan_review_date)}</td>
                    <td>${formatDate(client.last_visit)}</td>
                    <td>
                        <div class="risk-score ${riskClass}">
                            <div class="risk-bar"><div class="risk-fill" style="width: ${Math.min(client.risk_score || 0, 100)}%"></div></div>
                            <span>${client.risk_label || 'Low'}</span>
                        </div>
                    </td>
                </tr>
                <tr class="client-detail-row" id="detail-${client.id}" style="display:none">
                    <td colspan="9">
                        <div class="client-detail">
                            <div class="detail-block">
                                <div class="detail-block-title">Care Plan</div>
                                <div class="detail-block-content">${escapeHtml(client.care_plan_summary) || 'No care plan data available'}</div>
                            </div>
                            <div class="detail-block">
                                <div class="detail-block-title">Authorized Hours & Schedule</div>
                                <div class="detail-block-content">
                                    <div><strong>Authorized:</strong> ${client.authorized_hours_weekly || '--'} hrs/week</div>
                                    <div><strong>Actual (7d):</strong> ${client.actual_hours_weekly || 0} hrs</div>
                                    <div><strong>Start Date:</strong> ${formatDate(client.start_date)}</div>
                                </div>
                            </div>
                            <div class="detail-block">
                                <div class="detail-block-title">Caregivers & Notes</div>
                                <div class="detail-block-content">
                                    <div style="margin-bottom: 8px;">
                                        ${(client.caregivers || []).length > 0
                                            ? client.caregivers.map(cg => `<span class="caregiver-tag">${escapeHtml(cg)}</span>`).join('')
                                            : '<span style="color:#64748b">No caregivers assigned</span>'}
                                    </div>
                                    <div style="color:#94a3b8; font-size:12px;">${escapeHtml(client.notes) || 'No notes'}</div>
                                </div>
                            </div>
                        </div>
                    </td>
                </tr>
            `;
        });

        tbody.innerHTML = html;
    }

    // Toggle client detail row
    window.toggleClientDetail = function(clientId) {
        const detailRow = document.getElementById(`detail-${clientId}`);
        const expandBtn = document.getElementById(`expand-btn-${clientId}`);
        if (!detailRow) return;

        const isVisible = detailRow.style.display !== 'none';
        detailRow.style.display = isVisible ? 'none' : 'table-row';
        if (expandBtn) expandBtn.classList.toggle('expanded', !isVisible);
    };

    // Sort clients by column
    window.sortClients = function(field) {
        if (state.clientSortField === field) {
            state.clientSortAsc = !state.clientSortAsc;
        } else {
            state.clientSortField = field;
            state.clientSortAsc = true;
        }
        updateClientsTable();
    };

    // Filter clients by search
    window.filterClients = function(query) {
        state.clientFilter = query;
        updateClientsTable();
    };

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

    // ============================================
    // CALL-OUT LOG (merged into Shifts tab)
    // ============================================

    async function fetchCallOuts() {
        try {
            const response = await fetch('/api/gigi/callouts?limit=20');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            state.callOuts = data.callouts || [];
            updateCallOutsTable();
        } catch (error) {
            console.error('Failed to fetch call-outs:', error);
            // Show empty state on error
            const tbody = document.getElementById('callouts-table-body');
            if (tbody) tbody.innerHTML = '<tr><td colspan="6" class="empty-state"><div class="icon">✅</div>No recent call-outs</td></tr>';
        }
    }

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

    // Load hours breakdown data
    async function loadHoursBreakdown() {
        try {
            const data = await fetchAPI('/hours-breakdown');
            if (!data) return;

            if (data.weekly) {
                setKPI('weekly-total-hours', data.weekly.total_hours || 0);
                setKPI('weekly-shifts', data.weekly.shifts || 0);
                setKPI('weekly-clients', data.weekly.clients || 0);
                setKPI('weekly-avg-client', data.weekly.avg_per_client ? `${data.weekly.avg_per_client} hrs` : '--');
            }
            if (data.monthly) {
                setKPI('monthly-total-hours', data.monthly.total_hours || 0);
                setKPI('monthly-shifts', data.monthly.shifts || 0);
                setKPI('monthly-clients', data.monthly.clients || 0);
                setKPI('monthly-avg-client', data.monthly.avg_per_client ? `${data.monthly.avg_per_client} hrs` : '--');
            }
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

    function formatDateTime(dateStr) {
        if (!dateStr) return '--';
        const date = new Date(dateStr);
        if (isNaN(date.getTime())) return dateStr;
        return date.toLocaleString('en-US', {
            month: 'short', day: 'numeric',
            hour: 'numeric', minute: '2-digit', hour12: true
        });
    }

    function getRiskClass(score) {
        if (!score) return 'risk-low';
        if (score >= 50) return 'risk-high';
        if (score >= 25) return 'risk-medium';
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

    // Global functions
    window.refreshData = function () { fetchAllData(); };
    window.loadHoursBreakdown = loadHoursBreakdown;
    window.refreshCallOuts = function() { fetchCallOuts(); };
})();
