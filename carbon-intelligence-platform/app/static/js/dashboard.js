/**
 * Carbon Intelligence Platform — Dashboard JS v2
 * Drives animated cards, progress bars, and Chart.js charts.
 */

const POLL_INTERVAL_MS = 5000;
const MAX_CHART_POINTS = 60;

let powerChart = null;
let resourceChart = null;

const powerBuffer    = new RollingBuffer(MAX_CHART_POINTS);
const resourceBuffer = new RollingBuffer(MAX_CHART_POINTS);

// ── Chart.js shared config ──────────────────────────────────────────
const CHART_DEFAULTS = {
  responsive: true,
  animation: { duration: 400 },
  plugins: { legend: { display: false } },
  elements: { point: { radius: 0 } },
};

function initCharts() {
  const powerCtx = document.getElementById('chart-power');
  if (powerCtx) {
    powerChart = new Chart(powerCtx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Estimated Power (W)',
          data: [],
          borderColor: '#68c184',
          backgroundColor: 'rgba(104,193,132,0.08)',
          borderWidth: 2,
          fill: true,
          tension: 0.45,
          pointRadius: 0,
        }]
      },
      options: {
        ...CHART_DEFAULTS,
        scales: {
          x: {
            display: false,
            grid: { color: 'rgba(105,115,107,0.16)' },
          },
          y: {
            title: { display: true, text: 'W', color: '#68716b', font: { size: 10 } },
            beginAtZero: false,
            grid: { color: 'rgba(105,115,107,0.16)' },
            ticks: { color: '#68716b', font: { size: 10 } },
          }
        }
      }
    });
  }

  const resCtx = document.getElementById('chart-resources');
  if (resCtx) {
    resourceChart = new Chart(resCtx, {
      type: 'line',
      data: {
        labels: [],
        datasets: [
          {
            label: 'CPU %',
            data: [],
            borderColor: '#dce3de',
            backgroundColor: 'rgba(220,227,222,0.025)',
            borderWidth: 2, fill: true, tension: 0.45, pointRadius: 0,
          },
          {
            label: 'RAM %',
            data: [],
            borderColor: '#68c184',
            backgroundColor: 'rgba(104,193,132,0.06)',
            borderWidth: 2, fill: true, tension: 0.45, pointRadius: 0,
          }
        ]
      },
      options: {
        ...CHART_DEFAULTS,
        plugins: { legend: { display: true, position: 'top', labels: { color: '#68716b', boxWidth: 10, font: { size: 10 } } } },
        scales: {
          x: { display: false, grid: { color: 'rgba(105,115,107,0.16)' } },
          y: {
            min: 0, max: 100,
            title: { display: true, text: '%', color: '#68716b', font: { size: 10 } },
            grid: { color: 'rgba(105,115,107,0.16)' },
            ticks: { color: '#68716b', font: { size: 10 } },
          }
        }
      }
    });
  }
}

// ── Animated value updater ──────────────────────────────────────────
function setBar(id, pct) {
  const el = document.getElementById(id);
  if (el) el.style.width = Math.min(Math.max(pct, 0), 100) + '%';
}

// ── Poll telemetry ──────────────────────────────────────────────────
async function pollTelemetry() {
  const data = await apiFetch('/api/telemetry/current');
  if (!data) return;

  const ts  = fmtTimestamp(data.timestamp);
  const cpu = data.cpu    || {};
  const mem = data.memory || {};
  const disk= data.disk   || {};
  const net = data.network|| {};
  const gpu = data.gpu    || {};

  // Cards
  const cpuVal = cpu.utilization_pct || 0;
  document.getElementById('card-cpu').textContent  = cpuVal.toFixed(1);
  document.getElementById('card-cpu-freq').textContent =
    cpu.frequency_mhz ? cpu.frequency_mhz.toFixed(0) + ' MHz' : '—';
  setBar('bar-cpu', cpuVal);

  // Telemetry panel
  document.getElementById('telem-cpu-util').textContent  = fmt(cpu.utilization_pct, '%', 1);
  document.getElementById('telem-cpu-freq').textContent  = cpu.frequency_mhz ? cpu.frequency_mhz.toFixed(0) + ' MHz' : '—';
  document.getElementById('telem-ram-used').textContent  = mem.used_mb      ? (mem.used_mb / 1024).toFixed(2) + ' GB' : '—';
  document.getElementById('telem-ram-avail').textContent = mem.available_mb ? (mem.available_mb / 1024).toFixed(2) + ' GB' : '—';
  document.getElementById('telem-disk-read').textContent  = fmt(disk.read_mb_s,  'MB/s', 2);
  document.getElementById('telem-disk-write').textContent = fmt(disk.write_mb_s, 'MB/s', 2);
  document.getElementById('telem-net-recv').textContent   = fmt(net.recv_mb_s,   'MB/s', 3);
  document.getElementById('telem-net-sent').textContent   = fmt(net.sent_mb_s,   'MB/s', 3);

  // Mini bars
  setBar('mbar-cpu', cpuVal);
  setBar('mbar-ram', mem.utilization_pct || 0);

  // GPU
  if (gpu.available) {
    document.getElementById('telem-gpu').textContent = fmt(gpu.utilization_pct, '%', 1);
    document.getElementById('telem-gpu').style.color = 'var(--teal-400)';
  } else {
    document.getElementById('telem-gpu').textContent = 'Unavailable';
    document.getElementById('telem-gpu').style.color = 'var(--text-dim)';
    document.getElementById('telem-gpu').title = gpu.unavailability_reason || '';
  }

  document.getElementById('telem-timestamp').textContent = ts;
  const liveTime = document.getElementById('dashboard-live-time');
  if (liveTime) liveTime.textContent = `Updated ${ts}`;

  // Resource chart
  resourceBuffer.push(ts, { cpu: cpuVal, ram: mem.utilization_pct || 0 });
  if (resourceChart) {
    resourceChart.data.labels             = [...resourceBuffer.labels];
    resourceChart.data.datasets[0].data  = [...(resourceBuffer.datasets.cpu || [])];
    resourceChart.data.datasets[1].data  = [...(resourceBuffer.datasets.ram || [])];
    resourceChart.update('none');
  }

  // Processes
  const procs = (data.processes || {}).top || [];
  const list  = document.getElementById('process-list');
  if (list) {
    let html = `<div class="process-header"><span>Process</span><span>CPU %</span><span>RAM</span></div>`;
    procs.forEach(p => {
      const cpuPct = (p.cpu_pct || 0);
      const color  = cpuPct > 50 ? 'var(--danger-color)' : cpuPct > 25 ? 'var(--warning-color)' : 'var(--cpu-color)';
      html += `<div class="process-row">
        <span class="process-name" title="${p.name}">${p.name.length > 24 ? p.name.substring(0,22) + '…' : p.name}</span>
        <span class="process-cpu" style="color:${color}">${cpuPct.toFixed(1)}%</span>
        <span class="process-mem">${(p.memory_mb || 0).toFixed(0)} MB</span>
      </div>`;
    });
    list.innerHTML = html;
  }
}

// ── Poll prediction & energy ─────────────────────────────────────────
async function pollPrediction() {
  const data = await apiFetch('/api/prediction/current');
  if (!data) return;

  const pred   = data.prediction || {};
  const energy = data.energy     || {};
  const pw     = pred.predicted_power_w;

  // Power card + bar (max assumed 250W)
  document.getElementById('card-power').textContent =
    pw !== null && pw !== undefined ? pw.toFixed(1) : '—';
  setBar('bar-power', pw ? (pw / 250) * 100 : 0);

  // Energy card + bar (max assumed 1 kWh per session)
  const kwh = energy.session_energy_kwh;
  document.getElementById('card-energy').textContent =
    kwh !== undefined ? kwh.toFixed(4) : '—';
  setBar('bar-energy', kwh ? Math.min(kwh / 0.5 * 100, 100) : 0);

  // Energy detail panel
  document.getElementById('energy-current').textContent = fmt(pw, 'W', 1);
  document.getElementById('energy-peak').textContent    = fmt(energy.peak_power_w,    'W', 1);
  document.getElementById('energy-avg').textContent     = fmt(energy.average_power_w, 'W', 1);
  document.getElementById('energy-wh').textContent      = fmt(energy.session_energy_wh,  'Wh',  2);
  document.getElementById('energy-kwh').textContent     = fmt(energy.session_energy_kwh, 'kWh', 4);

  // Model banner
  const banner = document.getElementById('model-status-banner');
  const predictionWarnings = Array.isArray(pred.warnings) ? pred.warnings : [];
  if (pred.error || predictionWarnings.length || pred.dataset_type === 'synthetic_model_generated') {
    banner.classList.remove('hidden');
    const syntheticNotice = pred.dataset_type === 'synthetic_model_generated'
      ? 'Prototype model trained on synthetic formula-generated targets; real-world power accuracy is unknown.'
      : '';
    document.getElementById('model-status-text').textContent = [...new Set([syntheticNotice, ...predictionWarnings, pred.error].filter(Boolean))].join(' ');
  } else {
    banner.classList.add('hidden');
  }

  // Power chart
  if (pw !== null && pw !== undefined) {
    const ts = fmtTimestamp(pred.timestamp);
    powerBuffer.push(ts, { power: pw });
    if (powerChart) {
      powerChart.data.labels            = [...powerBuffer.labels];
      powerChart.data.datasets[0].data = [...(powerBuffer.datasets.power || [])];
      powerChart.update('none');
    }
  }

  // Prefill what-if
  const wiP = document.getElementById('wi-power');
  if (wiP && !wiP.value && pw) wiP.value = pw.toFixed(1);
}

// ── Poll carbon ──────────────────────────────────────────────────────
async function pollCarbon() {
  const data = await apiFetch('/api/carbon/current');
  if (!data) return;

  const intensity = data.intensity || {};
  const co2e      = data.co2e      || {};
  const iv = intensity.carbon_intensity_g_per_kwh;

  // Carbon intensity card (max ~900 gCO₂e/kWh)
  if (iv !== null && iv !== undefined) {
    document.getElementById('card-intensity').textContent = iv.toFixed(0);
    document.getElementById('card-intensity-source').textContent =
      (intensity.source || '?') + ' · ' + (intensity.zone || '?');
    setBar('bar-intensity', (iv / 900) * 100);
  } else {
    document.getElementById('card-intensity').textContent = '—';
    document.getElementById('card-intensity-source').textContent =
      intensity.status === 'unavailable' ? '⚠ Unavailable' : (intensity.error || 'Error');
  }

  // CO₂e card + bar
  const co2g = co2e.co2e_g;
  if (co2g !== null && co2g !== undefined) {
    if (co2g >= 1000) {
      document.getElementById('card-co2').textContent      = (co2g / 1000).toFixed(3);
      document.getElementById('card-co2-unit').textContent = 'kg CO₂e';
    } else {
      document.getElementById('card-co2').textContent      = co2g.toFixed(2);
      document.getElementById('card-co2-unit').textContent = 'g CO₂e';
    }
    setBar('bar-co2', Math.min(co2g / 500 * 100, 100));
  } else {
    document.getElementById('card-co2').textContent = '—';
  }

  // Energy panel details
  document.getElementById('co2e-full').textContent =
    co2g !== null && co2g !== undefined
      ? co2g.toFixed(2) + ' g  (' + (co2g/1000).toFixed(4) + ' kg)'
      : '—';
  document.getElementById('intensity-full').textContent =
    iv !== null && iv !== undefined ? iv.toFixed(0) + ' gCO₂e/kWh' : '—';
  document.getElementById('intensity-source-full').textContent = intensity.source || '—';
  document.getElementById('intensity-zone').textContent        = intensity.zone   || '—';

  // Fallback notice
  const fn = document.getElementById('carbon-fallback-notice');
  if (intensity.fallback_notice) {
    fn.classList.remove('hidden');
    fn.textContent = '⚠ ' + intensity.fallback_notice;
  } else {
    fn.classList.add('hidden');
  }

  // Prefill what-if
  const wiI = document.getElementById('wi-intensity');
  if (wiI && !wiI.value && iv) wiI.value = iv.toFixed(0);
}

// ── Poll session ─────────────────────────────────────────────────────
async function pollSession() {
  const data = await apiFetch('/api/session/current');
  if (!data) return;

  const badge    = document.getElementById('session-status-badge');
  const btnStart = document.getElementById('btn-start-session');
  const btnStop  = document.getElementById('btn-stop-session');
  const durCard  = document.getElementById('card-duration');
  const durNote  = document.getElementById('card-duration-note');

  if (data.session_active && data.session) {
    badge.className   = 'session-badge session-active';
    badge.textContent = '⬤ ' + data.session.name;
    btnStart.classList.add('hidden');
    btnStop.classList.remove('hidden');
    durCard.textContent = fmtDuration(data.session.duration_s);
    durNote.textContent = 'Session running';
    const dur = data.session.duration_s || 0;
    setBar('bar-duration', Math.min(dur / 3600 * 100, 100)); // full at 1 hour
  } else {
    badge.className   = 'session-badge session-inactive';
    badge.textContent = '⬤ No Session';
    btnStart.classList.remove('hidden');
    btnStop.classList.add('hidden');
    durCard.textContent = '—';
    durNote.textContent = 'No active session';
    setBar('bar-duration', 0);
  }
}

// ── Session controls ─────────────────────────────────────────────────
async function startSession() {
  const name = prompt('Session name (press Enter for default):', 'Session ' + new Date().toLocaleTimeString());
  if (name === null) return;
  const result = await apiPost('/api/session/start', { name });
  if (result && result.session) await pollSession();
}

async function stopSession() {
  if (!confirm('Stop the current monitoring session?')) return;
  const result = await apiPost('/api/session/stop', {});
  if (result && result.session) {
    await pollSession();
    const s = result.session;
    alert(
      '✅ Session complete!\n\n' +
      'Energy:  ' + ((s.total_energy_kwh || 0).toFixed(4)) + ' kWh\n' +
      'CO₂e:    ' + ((s.total_co2e_g || 0).toFixed(2)) + ' g\n' +
      'Duration: ' + fmtDuration(s.duration_s)
    );
  }
}

// ── What-If ──────────────────────────────────────────────────────────
async function runWhatIf() {
  const power     = parseFloat(document.getElementById('wi-power').value);
  const hours     = parseFloat(document.getElementById('wi-hours').value);
  const intensity = parseFloat(document.getElementById('wi-intensity').value);
  if (isNaN(power) || isNaN(hours) || isNaN(intensity)) {
    alert('Please fill in all three fields.'); return;
  }
  const result = await apiPost('/api/what-if', {
    power_w: power, additional_hours: hours, carbon_intensity_g_per_kwh: intensity,
  });
  if (!result) return;

  document.getElementById('wi-energy').textContent =
    (result.projected_additional_energy_wh?.toFixed(1)) + ' Wh  (' +
    (result.projected_additional_energy_kwh?.toFixed(4)) + ' kWh)';
  document.getElementById('wi-co2e').textContent =
    (result.projected_additional_co2e_g?.toFixed(2)) + ' g CO₂e';
  document.getElementById('wi-duration').textContent  = result.duration_display;
  document.getElementById('wi-disclaimer').textContent = result.disclaimer;
  document.getElementById('whatif-results').classList.remove('hidden');
}

// ── Model check ──────────────────────────────────────────────────────
async function checkModelStatus() {
  const data = await apiFetch('/api/model/status');
  if (!data) return;
  const banner = document.getElementById('model-status-banner');
  if (!data.model_ready) {
    banner.classList.remove('hidden');
    document.getElementById('model-status-text').textContent =
      data.error || 'Model not loaded — run: python -m app.ml.train';
  } else if (data.dataset_type === 'synthetic_model_generated') {
    banner.classList.remove('hidden');
    document.getElementById('model-status-text').textContent =
      'Prototype model trained on synthetic formula-generated targets; real-world power accuracy is unknown.';
  }
}

// ── Main loop ────────────────────────────────────────────────────────
async function pollAll() {
  await Promise.all([pollTelemetry(), pollPrediction(), pollCarbon(), pollSession()]);
}

initCharts();
checkModelStatus();
pollAll();
setInterval(pollAll, POLL_INTERVAL_MS);

