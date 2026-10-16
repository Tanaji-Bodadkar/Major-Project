/**
 * Carbon Intelligence Platform — Analytics Page JS
 */

let powerAnalyticsChart = null;
let resourceAnalyticsChart = null;
let sessionEnergyChart = null;
let sessionCo2eChart = null;

async function loadAnalytics() {
    const window_m = document.getElementById('analytics-window').value;
    const data = await apiFetch(`/api/analytics?window_minutes=${window_m}`);
    if (!data) return;

    // Power trend chart
    const pt = data.power_trend || {};
    updatePowerChart(pt.timestamps || [], pt.power_values || []);

    // Telemetry trend chart
    const tt = data.telemetry_trend || {};
    updateResourceChart(tt.timestamps || [], tt.cpu_values || [], tt.ram_values || []);

    // Session comparison text
    renderComparison(data.session_comparison);

    // Load sessions for bar charts
    loadSessionCharts();
}

const DARK_GRID  = 'rgba(105,115,107,0.16)';
const DARK_TICKS = { color: '#68716b', font: { size: 10 } };

function updatePowerChart(labels, values) {
    const ctx = document.getElementById('analytics-power-chart');
    if (!ctx) return;
    const shortLabels = labels.map(l => fmtTimestamp(l));
    if (powerAnalyticsChart) {
        powerAnalyticsChart.data.labels = shortLabels;
        powerAnalyticsChart.data.datasets[0].data = values;
        powerAnalyticsChart.update();
        return;
    }
    powerAnalyticsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: shortLabels,
            datasets: [{
                label: 'Estimated Power (W)',
                data: values,
                borderColor: '#68c184',
                backgroundColor: 'rgba(104,193,132,0.08)',
                borderWidth: 2, pointRadius: 0, fill: true, tension: 0.45,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            elements: { point: { radius: 0 } },
            scales: {
                x: { ticks: { ...DARK_TICKS, maxTicksLimit: 8 }, grid: { color: DARK_GRID } },
                y: { title: { display: true, text: 'W', color: '#68716b', font:{size:10} },
                     beginAtZero: false, ticks: DARK_TICKS, grid: { color: DARK_GRID } }
            }
        }
    });
}

function updateResourceChart(labels, cpuVals, ramVals) {
    const ctx = document.getElementById('analytics-resource-chart');
    if (!ctx) return;
    const shortLabels = labels.map(l => fmtTimestamp(l));
    if (resourceAnalyticsChart) {
        resourceAnalyticsChart.data.labels = shortLabels;
        resourceAnalyticsChart.data.datasets[0].data = cpuVals;
        resourceAnalyticsChart.data.datasets[1].data = ramVals;
        resourceAnalyticsChart.update();
        return;
    }
    resourceAnalyticsChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: shortLabels,
            datasets: [
                {
                    label: 'CPU %',
                    data: cpuVals,
                    borderColor: '#dce3de',
                    backgroundColor: 'rgba(220,227,222,0.025)',
                    borderWidth: 2, pointRadius: 0, fill: true, tension: 0.4,
                },
                {
                    label: 'RAM %',
                    data: ramVals,
                    borderColor: '#68c184',
                    backgroundColor: 'rgba(104,193,132,0.06)',
                    borderWidth: 2, pointRadius: 0, fill: true, tension: 0.4,
                }
            ]
        },
        options: {
            responsive: true,
            plugins: { legend: { position: 'top', labels: { boxWidth: 12 } } },
            scales: {
                x: { ticks: { maxTicksLimit: 8 } },
                y: { min: 0, max: 100, title: { display: true, text: '%' } }
            }
        }
    });
}

async function loadSessionCharts() {
    const data = await apiFetch('/api/sessions');
    if (!data || !data.sessions) return;

    const sessions = data.sessions.filter(s => s.status === 'completed').slice(-10);

    const labels = sessions.map(s => s.name || s.session_id);
    const energyVals = sessions.map(s => s.total_energy_kwh || 0);
    const co2eVals = sessions.map(s => s.total_co2e_g || 0);

    renderSessionEnergyChart(labels, energyVals);
    renderSessionCo2eChart(labels, co2eVals);
}

function renderSessionEnergyChart(labels, values) {
    const ctx = document.getElementById('analytics-session-chart');
    if (!ctx) return;
    if (sessionEnergyChart) {
        sessionEnergyChart.data.labels = labels;
        sessionEnergyChart.data.datasets[0].data = values;
        sessionEnergyChart.update();
        return;
    }
    sessionEnergyChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'Energy (kWh)',
                data: values,
                backgroundColor: 'rgba(56,142,60,0.7)',
                borderColor: '#388e3c',
                borderWidth: 1,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxRotation: 30 } },
                y: { title: { display: true, text: 'kWh' }, beginAtZero: true }
            }
        }
    });
}

function renderSessionCo2eChart(labels, values) {
    const ctx = document.getElementById('analytics-co2e-chart');
    if (!ctx) return;
    if (sessionCo2eChart) {
        sessionCo2eChart.data.labels = labels;
        sessionCo2eChart.data.datasets[0].data = values;
        sessionCo2eChart.update();
        return;
    }
    sessionCo2eChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels,
            datasets: [{
                label: 'CO₂e (g)',
                data: values,
                backgroundColor: 'rgba(230,81,0,0.7)',
                borderColor: '#e65100',
                borderWidth: 1,
            }]
        },
        options: {
            responsive: true,
            plugins: { legend: { display: false } },
            scales: {
                x: { ticks: { maxRotation: 30 } },
                y: { title: { display: true, text: 'gCO₂e' }, beginAtZero: true }
            }
        }
    });
}

function renderComparison(comparison) {
    const el = document.getElementById('comparison-content');
    if (!el) return;
    if (!comparison) {
        el.innerHTML = '<p class="muted">Not enough session history for comparison (need at least 1 completed session ≥ 5 minutes).</p>';
        return;
    }
    const dir = comparison.direction === 'higher' ? '▲' : '▼';
    const color = comparison.direction === 'higher' ? '#c62828' : '#2e7d32';
    el.innerHTML = `
        <p style="font-size:0.9rem;line-height:1.6;">${comparison.note}</p>
        <p style="font-size:1.1rem;font-weight:700;color:${color};margin-top:0.5rem;">
            ${dir} ${Math.abs(comparison.percentage_difference).toFixed(1)}%
            vs. previous session
        </p>
        <p class="muted" style="font-size:0.75rem;margin-top:0.25rem;">
            Current: ${(comparison.current_kwh_per_hour * 1000).toFixed(2)} Wh/hr vs.
            Previous: ${(comparison.previous_kwh_per_hour * 1000).toFixed(2)} Wh/hr
        </p>
    `;
}

// Initial load + auto-refresh
loadAnalytics();
setInterval(loadAnalytics, 30000);

