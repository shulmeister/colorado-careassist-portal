/**
 * Operations Dashboard - Colorado CareAssist
 * Handles data fetching and UI updates for the operations dashboard.
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize navigation
    initNavigation();

    // Initial data fetch
    refreshData();
    loadHoursBreakdown();

    // Set up auto-refresh (every 5 minutes)
    setInterval(refreshData, 300000);
    setInterval(loadHoursBreakdown, 300000);
});

function initNavigation() {
    const links = document.querySelectorAll('.sidebar-link');
    links.forEach(link => {
        link.addEventListener('click', function() {
            // Update active link
            links.forEach(l => l.classList.remove('active'));
            this.classList.add('active');
            
            // Show corresponding tab content
            const tabId = this.dataset.tab;
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(`tab-${tabId}`).classList.add('active');
            
            // Load tab specific data if needed
            if (tabId === 'clients') loadClients();
            if (tabId === 'care-plans') loadCarePlans();
            if (tabId === 'shifts') loadShifts();
            if (tabId === 'at-risk') loadAtRiskClients();
            if (tabId === 'gigi') refreshGigiActivity();
            if (tabId === 'call-outs') refreshCallOuts();
        });
    });
}

function refreshData() {
    loadSummaryKPIs();
    // Load data for the currently active tab
    const activeTab = document.querySelector('.sidebar-link.active').dataset.tab;
    if (activeTab === 'overview') {
        // Overview also has charts
        loadCharts();
    } else if (activeTab === 'clients') {
        loadClients();
    } else if (activeTab === 'care-plans') {
        loadCarePlans();
    } else if (activeTab === 'shifts') {
        loadShifts();
    } else if (activeTab === 'at-risk') {
        loadAtRiskClients();
    }
}

async function loadSummaryKPIs() {
    try {
        const response = await fetch('/api/operations/summary?days=30');
        const data = await response.json();
        
        // Update KPIs
        document.getElementById('kpi-active-clients').textContent = data.active_clients || 0;
        document.getElementById('kpi-active-caregivers').textContent = data.active_caregivers || 0;
        document.getElementById('kpi-open-shifts').textContent = data.open_shifts || 0;
        document.getElementById('kpi-evv-rate').textContent = (data.evv_compliance || 0) + '%';
        document.getElementById('kpi-plans-due').textContent = data.plans_due_review || 0;
        document.getElementById('kpi-at-risk').textContent = data.at_risk_clients || 0;
        
        // Update WellSky Banner
        const banner = document.getElementById('wellskyBanner');
        const bannerText = banner.querySelector('.text');
        const bannerIcon = banner.querySelector('.icon');
        
        if (data.wellsky_connected) {
            banner.classList.add('connected');
            bannerText.textContent = 'Connected to WellSky API';
            bannerIcon.textContent = '✅';
            
            // Update WellSky Status in Gigi tab too
            const wsStatus = document.getElementById('wellsky-status');
            if (wsStatus) {
                wsStatus.className = 'status-indicator online';
                wsStatus.innerHTML = '<span class="status-dot"></span><span>Connected</span>';
                document.getElementById('wellsky-api-status').textContent = 'Live API Connection Active';
            }
        } else {
            banner.classList.remove('connected');
            bannerText.textContent = 'Using mock data - WellSky API not connected';
            bannerIcon.textContent = '⏳';
        }
        
    } catch (error) {
        console.error('Error loading summary KPIs:', error);
    }
}

async function loadCharts() {
    // Placeholder for chart implementation
    // Ideally use Chart.js if available
    console.log('Loading charts...');
}

async function loadClients() {
    const tbody = document.getElementById('clients-table-body');
    tbody.innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div> Loading clients...</td></tr>';
    
    try {
        const response = await fetch('/api/operations/clients');
        const data = await response.json();
        const clients = data.clients || [];
        
        if (clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No active clients found</td></tr>';
            return;
        }
        
        tbody.innerHTML = clients.map(client => `
            <tr>
                <td>${client.name}</td>
                <td><span class="status-badge status-${client.status.toLowerCase()}">${client.status}</span></td>
                <td>${client.hours_per_week || 0}</td>
                <td>${client.payer || 'Private Pay'}</td>
                <td>
                    <div class="risk-score">
                        <div class="risk-bar">
                            <div class="risk-fill" style="width: ${client.risk_score || 0}%"></div>
                        </div>
                        <span>${client.risk_score || 0}</span>
                    </div>
                </td>
                <td>${client.last_visit ? new Date(client.last_visit).toLocaleDateString() : 'N/A'}</td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error loading clients:', error);
        tbody.innerHTML = `<tr><td colspan="6" class="error">Error loading data: ${error.message}</td></tr>`;
    }
}

async function loadCarePlans() {
    const tbody = document.getElementById('care-plans-table-body');
    tbody.innerHTML = '<tr><td colspan="5" class="loading"><div class="spinner"></div> Loading care plans...</td></tr>';
    
    try {
        const response = await fetch('/api/operations/care-plans?days=30');
        const data = await response.json();
        const plans = data.care_plans || [];
        
        if (plans.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No care plans due for review</td></tr>';
            return;
        }
        
        tbody.innerHTML = plans.map(plan => `
            <tr>
                <td>${plan.client_name}</td>
                <td><span class="status-badge status-warning">${plan.status}</span></td>
                <td>${plan.review_date ? new Date(plan.review_date).toLocaleDateString() : 'N/A'}</td>
                <td>${plan.days_until_review || 0} days</td>
                <td>${plan.authorized_hours} hrs</td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error loading care plans:', error);
        tbody.innerHTML = `<tr><td colspan="5" class="error">Error loading data: ${error.message}</td></tr>`;
    }
}

async function loadShifts() {
    const tbody = document.getElementById('shifts-table-body');
    tbody.innerHTML = '<tr><td colspan="6" class="loading"><div class="spinner"></div> Loading shifts...</td></tr>';
    
    try {
        // Fetch open shifts for the next 7 days
        const response = await fetch('/api/operations/open-shifts?days=7');
        const data = await response.json();
        const shifts = data.shifts || [];
        
        if (shifts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No open shifts found</td></tr>';
            return;
        }
        
        tbody.innerHTML = shifts.map(shift => `
            <tr>
                <td>${shift.date ? new Date(shift.date).toLocaleDateString() : 'N/A'}</td>
                <td>${shift.start_time} - ${shift.end_time}</td>
                <td>${shift.client_name}</td>
                <td>${shift.location || shift.city || 'Unknown'}</td>
                <td>${shift.hours || '0'} hrs</td>
                <td><span class="status-badge status-open">Open</span></td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error loading shifts:', error);
        tbody.innerHTML = `<tr><td colspan="6" class="error">Error loading data: ${error.message}</td></tr>`;
    }
}

async function loadAtRiskClients() {
    const tbody = document.getElementById('at-risk-table-body');
    tbody.innerHTML = '<tr><td colspan="4" class="loading"><div class="spinner"></div> Loading at-risk clients...</td></tr>';
    
    try {
        const response = await fetch('/api/operations/at-risk?threshold=40');
        const data = await response.json();
        const clients = data.clients || [];
        
        if (clients.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="empty-state">No high-risk clients found</td></tr>';
            return;
        }
        
        tbody.innerHTML = clients.map(client => `
            <tr>
                <td>${client.name}</td>
                <td>
                    <span class="status-badge status-danger">Score: ${client.risk_score}</span>
                </td>
                <td>${(client.risk_factors || []).join(', ')}</td>
                <td>${(client.recommendations || []).length > 0 ? client.recommendations[0] : 'Monitor closely'}</td>
            </tr>
        `).join('');
        
    } catch (error) {
        console.error('Error loading at-risk clients:', error);
        tbody.innerHTML = `<tr><td colspan="4" class="error">Error loading data: ${error.message}</td></tr>`;
    }
}

// Gigi Tab Functions
function refreshGigiActivity() {
    // Placeholder for Gigi activity log fetching
    const logContainer = document.getElementById('gigi-activity-log');
    if (logContainer) {
        logContainer.innerHTML = '<div class="empty-state">Activity log connecting...</div>';
    }
}

function toggleGigiSetting(setting, enabled) {
    console.log(`Toggling ${setting} to ${enabled}`);
    // Call API to update setting
    fetch('/api/gigi/settings', {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({[setting]: enabled})
    }).then(res => res.json())
      .then(data => {
          if (data.success) showNotification('Setting updated', 'success');
          else showNotification('Failed to update setting', 'error');
      })
      .catch(err => showNotification('Error updating setting', 'error'));
}

function refreshCallOuts() {
    // Placeholder for call-outs fetching
    console.log('Refreshing call-outs...');
}

function showNotification(message, type = 'info') {
    // Simple notification logic
    console.log(`[${type.toUpperCase()}] ${message}`);
}

async function loadHoursBreakdown() {
    try {
        const response = await fetch('/api/operations/hours-breakdown');
        const data = await response.json();

        if (!data) {
            console.error('No hours breakdown data received');
            return;
        }

        // Update Weekly Hours
        if (data.weekly) {
            document.getElementById('weekly-total-hours').textContent = data.weekly.total_hours.toFixed(1);
            document.getElementById('weekly-billing-total').textContent = data.weekly.billing.total.toFixed(1);
            document.getElementById('weekly-billing-split').textContent =
                `Regular: ${data.weekly.billing.regular.toFixed(1)} | OT: ${data.weekly.billing.overtime.toFixed(1)}`;
            document.getElementById('weekly-payroll-total').textContent = data.weekly.payroll.total.toFixed(1);
            document.getElementById('weekly-payroll-split').textContent =
                `Regular: ${data.weekly.payroll.regular.toFixed(1)} | OT: ${data.weekly.payroll.overtime.toFixed(1)}`;
            document.getElementById('weekly-avg-client').textContent = data.weekly.averages.per_client.toFixed(1);
        }

        // Update Monthly Hours
        if (data.monthly) {
            document.getElementById('monthly-total-hours').textContent = data.monthly.total_hours.toFixed(1);
            document.getElementById('monthly-billing-total').textContent = data.monthly.billing.total.toFixed(1);
            document.getElementById('monthly-billing-split').textContent =
                `Regular: ${data.monthly.billing.regular.toFixed(1)} | OT: ${data.monthly.billing.overtime.toFixed(1)}`;
            document.getElementById('monthly-payroll-total').textContent = data.monthly.payroll.total.toFixed(1);
            document.getElementById('monthly-payroll-split').textContent =
                `Regular: ${data.monthly.payroll.regular.toFixed(1)} | OT: ${data.monthly.payroll.overtime.toFixed(1)}`;
            document.getElementById('monthly-avg-client').textContent = data.monthly.averages.per_client.toFixed(1);
        }

        // Update Quarterly Hours
        if (data.quarterly) {
            document.getElementById('quarterly-total-hours').textContent = data.quarterly.total_hours.toFixed(1);
            document.getElementById('quarterly-billing-total').textContent = data.quarterly.billing.total.toFixed(1);
            document.getElementById('quarterly-billing-split').textContent =
                `Regular: ${data.quarterly.billing.regular.toFixed(1)} | OT: ${data.quarterly.billing.overtime.toFixed(1)}`;
            document.getElementById('quarterly-payroll-total').textContent = data.quarterly.payroll.total.toFixed(1);
            document.getElementById('quarterly-payroll-split').textContent =
                `Regular: ${data.quarterly.payroll.regular.toFixed(1)} | OT: ${data.quarterly.payroll.overtime.toFixed(1)}`;
            document.getElementById('quarterly-avg-client').textContent = data.quarterly.averages.per_client.toFixed(1);
        }

    } catch (error) {
        console.error('Error loading hours breakdown:', error);
    }
}