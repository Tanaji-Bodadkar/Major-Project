/**
 * Carbon Intelligence Platform — Recommendations Page JS
 */

async function loadRecommendations() {
    const data = await apiFetch('/api/recommendations');
    const container = document.getElementById('recommendations-container');
    if (!container) return;

    if (!data) {
        container.innerHTML = '<div class="alert alert-error">Failed to load recommendations.</div>';
        return;
    }

    const recs = data.recommendations || [];

    if (recs.length === 0) {
        container.innerHTML = `
            <div class="panel">
                <p class="no-recs">✅ No recommendations at this time. Start a session to receive live insights.</p>
            </div>`;
        return;
    }

    let html = '';
    recs.forEach(rec => {
        const severityClass = rec.severity === 'warning' ? 'rec-warning' :
                              rec.severity === 'critical' ? 'rec-warning' :
                              rec.category === 'comparison' && rec.id.includes('positive') ? 'rec-success' :
                              'rec-info';
        html += `
        <div class="rec-card ${severityClass}">
            <div class="rec-header">
                <span class="rec-icon">${rec.icon || 'ℹ'}</span>
                <span class="rec-title">${rec.title}</span>
            </div>
            <p class="rec-body">${rec.body}</p>
            ${rec.action ? `<p class="rec-action">💬 ${rec.action}</p>` : ''}
        </div>`;
    });

    container.innerHTML = html;
}

// What-if on recommendations page
async function runWhatIfRecs() {
    const power = parseFloat(document.getElementById('wi-power-recs').value);
    const hours = parseFloat(document.getElementById('wi-hours-recs').value);
    const intensity = parseFloat(document.getElementById('wi-intensity-recs').value);

    if (isNaN(power) || isNaN(hours) || isNaN(intensity)) {
        alert('Please fill in all three fields.');
        return;
    }

    const result = await apiPost('/api/what-if', {
        power_w: power,
        additional_hours: hours,
        carbon_intensity_g_per_kwh: intensity,
    });
    if (!result) return;

    document.getElementById('wi-energy-recs').textContent =
        `${result.projected_additional_energy_wh?.toFixed(1)} Wh (${result.projected_additional_energy_kwh?.toFixed(4)} kWh)`;
    document.getElementById('wi-co2e-recs').textContent =
        `${result.projected_additional_co2e_g?.toFixed(2)} g CO₂e`;
    document.getElementById('wi-duration-recs').textContent = result.duration_display;
    document.getElementById('wi-disclaimer-recs').textContent = result.disclaimer;
    document.getElementById('whatif-results-recs').classList.remove('hidden');
}

// Prefill what-if from current session
async function prefillWhatIf() {
    const energyData = await apiFetch('/api/energy/current');
    if (energyData && energyData.current_power_w) {
        const el = document.getElementById('wi-power-recs');
        if (el && !el.value) el.value = energyData.current_power_w.toFixed(1);
    }
    const carbonData = await apiFetch('/api/carbon/current');
    if (carbonData && carbonData.intensity) {
        const intensity = carbonData.intensity.carbon_intensity_g_per_kwh;
        const el = document.getElementById('wi-intensity-recs');
        if (el && !el.value && intensity) el.value = intensity.toFixed(0);
    }
}

loadRecommendations();
prefillWhatIf();
setInterval(loadRecommendations, 15000);

