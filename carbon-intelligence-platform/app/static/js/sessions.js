/**
 * Carbon Intelligence Platform — Sessions Page JS v2
 */

async function loadSessions() {
  const container = document.getElementById('sessions-container');
  if (!container) return;
  container.innerHTML = '<div class="loading-spinner"></div>';

  const data = await apiFetch('/api/sessions');
  if (!data) {
    container.innerHTML = '<div class="alert alert-error">Failed to load sessions.</div>';
    return;
  }

  const sessions = (data.sessions || []).reverse();

  if (sessions.length === 0) {
    container.innerHTML = `
      <div class="panel" style="text-align:center;padding:3rem;">
        <p style="font-size:2rem;margin-bottom:1rem;">📋</p>
        <p class="muted">No completed sessions yet.</p>
        <p class="muted" style="font-size:0.8rem;margin-top:0.5rem;">Start a session from the Dashboard to begin tracking.</p>
      </div>`;
    return;
  }

  let html = `
  <div class="panel" style="padding:0;overflow:hidden;">
    <div class="table-wrap">
      <table class="sessions-table">
        <thead>
          <tr>
            <th>Session</th>
            <th>Started</th>
            <th>Duration</th>
            <th>Avg Power</th>
            <th>Peak Power</th>
            <th>Energy</th>
            <th>CO₂e</th>
            <th>Source</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>`;

  sessions.forEach(s => {
    const durStr = fmtDuration(s.duration_s);
    const avgP   = s.average_power_w  != null ? s.average_power_w.toFixed(1)  + ' W'    : '—';
    const peakP  = s.peak_power_w     != null ? s.peak_power_w.toFixed(1)     + ' W'    : '—';
    const energy = s.total_energy_kwh != null ? s.total_energy_kwh.toFixed(4) + ' kWh'  : '—';
    const co2    = s.total_co2e_g     != null ? s.total_co2e_g.toFixed(2)     + ' g'    : '—';

    html += `
      <tr>
        <td>
          <div style="font-weight:700;color:var(--text-primary)">${s.name || s.session_id}</div>
          <div style="font-size:0.68rem;font-family:var(--font-mono);color:var(--text-dim)">${s.session_id}</div>
        </td>
        <td class="mono" style="font-size:0.75rem;">${fmtDate(s.start_time)}</td>
        <td class="mono">${durStr}</td>
        <td class="val-power">${avgP}</td>
        <td class="val-power">${peakP}</td>
        <td class="val-energy">${energy}</td>
        <td class="val-co2">${co2}</td>
        <td style="font-size:0.72rem;color:var(--text-dim)">${s.carbon_source || '—'}</td>
        <td>
          <div style="display:flex;gap:0.4rem;flex-wrap:wrap;">
            <a href="/report-view/${s.session_id}" class="btn btn-secondary" style="font-size:0.7rem;padding:0.3rem 0.6rem;">View</a>
            <a href="/api/report/${s.session_id}" class="btn btn-primary"    style="font-size:0.7rem;padding:0.3rem 0.6rem;" download>PDF</a>
          </div>
        </td>
      </tr>`;
  });

  html += `
        </tbody>
      </table>
    </div>
    <div style="padding:0.75rem 1rem;border-top:1px solid var(--border);">
      <p class="muted" style="font-size:0.7rem;">
        All power, energy, and CO₂e values are <strong style="color:var(--green-400)">estimates</strong>
        — not direct electrical measurements. See methodology docs for details.
      </p>
    </div>
  </div>`;

  container.innerHTML = html;
}

loadSessions();

