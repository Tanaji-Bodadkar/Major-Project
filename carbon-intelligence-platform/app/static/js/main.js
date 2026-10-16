/**
 * Carbon Intelligence Platform — Shared JS Utilities
 * Runs on every page.
 */

// ── Connection indicator ──
let _connectionOk = false;

function setConnectionStatus(ok) {
    const dot = document.getElementById('connection-indicator');
    const label = document.getElementById('connection-label');
    if (!dot || !label) return;
    if (ok) {
        dot.className = 'status-dot status-live';
        label.textContent = 'Live';
    } else {
        dot.className = 'status-dot status-error';
        label.textContent = 'Offline';
    }
    _connectionOk = ok;
}

// ── Footer clock ──
function updateFooterTime() {
    const el = document.getElementById('footer-time');
    if (el) {
        el.textContent = new Date().toLocaleTimeString();
    }
}
setInterval(updateFooterTime, 1000);
updateFooterTime();

// ── API helper ──
async function apiFetch(url) {
    try {
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        setConnectionStatus(true);
        return await res.json();
    } catch (e) {
        setConnectionStatus(false);
        console.warn(`API error [${url}]:`, e.message);
        return null;
    }
}

async function apiPost(url, body) {
    try {
        const res = await fetch(url, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        setConnectionStatus(true);
        return await res.json();
    } catch (e) {
        setConnectionStatus(false);
        console.warn(`API POST error [${url}]:`, e.message);
        return null;
    }
}

// ── Formatting helpers ──
function fmt(value, unit, decimals = 1, fallback = '—') {
    if (value === null || value === undefined) return fallback;
    return `${parseFloat(value).toFixed(decimals)} ${unit}`.trim();
}

function fmtDuration(s) {
    if (s === null || s === undefined) return '—';
    const total = Math.floor(s);
    const h = Math.floor(total / 3600);
    const m = Math.floor((total % 3600) / 60);
    const sec = total % 60;
    return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(sec).padStart(2,'0')}`;
}

function fmtTimestamp(iso) {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleTimeString();
    } catch {
        return iso;
    }
}

function fmtDate(iso) {
    if (!iso) return '—';
    try {
        return new Date(iso).toLocaleString();
    } catch {
        return iso;
    }
}

// ── Chart.js shared defaults ──
if (typeof Chart !== 'undefined') {
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.color = '#555';
}

// ── Rolling data buffer for charts ──
class RollingBuffer {
    constructor(maxPoints = 60) {
        this.maxPoints = maxPoints;
        this.labels = [];
        this.datasets = {};
    }
    push(label, values) {
        this.labels.push(label);
        if (this.labels.length > this.maxPoints) {
            this.labels.shift();
        }
        for (const [key, val] of Object.entries(values)) {
            if (!this.datasets[key]) this.datasets[key] = [];
            this.datasets[key].push(val);
            if (this.datasets[key].length > this.maxPoints) {
                this.datasets[key].shift();
            }
        }
    }
}

