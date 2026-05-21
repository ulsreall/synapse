/* ────────────────────────────────────────────────────────────
   SYNAPSE Dashboard — Main JavaScript
   ──────────────────────────────────────────────────────────── */

// Chart.js global defaults for dark theme
if (typeof Chart !== 'undefined') {
    Chart.defaults.color = '#8b949e';
    Chart.defaults.borderColor = '#21262d';
    Chart.defaults.font.family = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif";
    Chart.defaults.font.size = 12;
    Chart.defaults.plugins.legend.labels.usePointStyle = true;
    Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
    Chart.defaults.plugins.tooltip.backgroundColor = '#161b22';
    Chart.defaults.plugins.tooltip.borderColor = '#30363d';
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.titleColor = '#e6edf3';
    Chart.defaults.plugins.tooltip.bodyColor = '#8b949e';
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 8;
}

// ─── Chart Rendering Functions ───

function renderTokenTrendChart(canvasId, dailyStats) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyStats.map(d => d.date.slice(5)),
            datasets: [{
                label: 'Tokens',
                data: dailyStats.map(d => d.total_tokens),
                borderColor: '#58a6ff',
                backgroundColor: 'rgba(88,166,255,.08)',
                fill: true,
                tension: 0.35,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: '#58a6ff',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    grid: { color: '#21262d' },
                    ticks: {
                        callback: v => v >= 1000 ? (v/1000).toFixed(0) + 'K' : v
                    }
                }
            }
        }
    });
}

function renderAgentWorkloadChart(canvasId, agents) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const colors = ['#58a6ff','#3fb950','#f85149','#bc8cff','#d29922','#f0883e','#a5d6ff','#7ee787','#ffa198','#d2a8ff'];
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: agents.map(a => a.name),
            datasets: [{
                data: agents.map(a => a.tokens_used),
                backgroundColor: colors,
                borderColor: '#161b22',
                borderWidth: 2,
                hoverOffset: 8,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '60%',
            plugins: {
                legend: {
                    position: 'right',
                    labels: {
                        padding: 12,
                        font: { size: 11 },
                        boxWidth: 12,
                        boxHeight: 12,
                    }
                }
            }
        }
    });
}

function renderDailyTokensChart(canvasId, dailyStats) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: dailyStats.map(d => d.date.slice(5)),
            datasets: [{
                label: 'Tokens',
                data: dailyStats.map(d => d.total_tokens),
                backgroundColor: 'rgba(88,166,255,.6)',
                borderColor: '#58a6ff',
                borderWidth: 1,
                borderRadius: 4,
                hoverBackgroundColor: '#58a6ff',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    grid: { color: '#21262d' },
                    ticks: {
                        callback: v => v >= 1000 ? (v/1000).toFixed(0) + 'K' : v
                    }
                }
            }
        }
    });
}

function renderAgentTokensChart(canvasId, agents) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    const sorted = [...agents].sort((a, b) => b.tokens_used - a.tokens_used);
    const colors = sorted.map((_, i) => {
        const palette = ['#58a6ff','#3fb950','#bc8cff','#d29922','#f0883e','#f85149','#a5d6ff','#7ee787','#d2a8ff','#ffa198'];
        return palette[i % palette.length];
    });
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: sorted.map(a => a.name.split(' ')[0]),
            datasets: [{
                label: 'Tokens',
                data: sorted.map(a => a.tokens_used),
                backgroundColor: colors.map(c => c + 'aa'),
                borderColor: colors,
                borderWidth: 1,
                borderRadius: 4,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            indexAxis: 'y',
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    beginAtZero: true,
                    grid: { color: '#21262d' },
                    ticks: {
                        callback: v => v >= 1000000 ? (v/1000000).toFixed(1) + 'M' : v >= 1000 ? (v/1000).toFixed(0) + 'K' : v
                    }
                },
                y: { grid: { display: false } }
            }
        }
    });
}

function renderHourlyChart(canvasId, hourlyStats) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: hourlyStats.map(h => h.hour),
            datasets: [{
                label: 'Tokens',
                data: hourlyStats.map(h => h.tokens),
                backgroundColor: 'rgba(188,140,255,.5)',
                borderColor: '#bc8cff',
                borderWidth: 1,
                borderRadius: 3,
                hoverBackgroundColor: '#bc8cff',
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxRotation: 45 }
                },
                y: {
                    beginAtZero: true,
                    grid: { color: '#21262d' },
                    ticks: {
                        callback: v => v >= 1000 ? (v/1000).toFixed(0) + 'K' : v
                    }
                }
            }
        }
    });
}

function renderDailyCostChart(canvasId, dailyStats) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return;
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: dailyStats.map(d => d.date.slice(5)),
            datasets: [{
                label: 'Cost ($)',
                data: dailyStats.map(d => d.cost_usd),
                borderColor: '#3fb950',
                backgroundColor: 'rgba(63,185,80,.08)',
                fill: true,
                tension: 0.35,
                pointRadius: 3,
                pointHoverRadius: 6,
                pointBackgroundColor: '#3fb950',
                borderWidth: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                x: { grid: { display: false } },
                y: {
                    beginAtZero: true,
                    grid: { color: '#21262d' },
                    ticks: {
                        callback: v => '$' + v.toFixed(2)
                    }
                }
            }
        }
    });
}

// ─── Code Editor Enhancements ───

function initCodeEditor() {
    const editor = document.getElementById('codeEditor');
    if (!editor) return;

    // Tab key support
    editor.addEventListener('keydown', function(e) {
        if (e.key === 'Tab') {
            e.preventDefault();
            const start = this.selectionStart;
            const end = this.selectionEnd;
            this.value = this.value.substring(0, start) + '    ' + this.value.substring(end);
            this.selectionStart = this.selectionEnd = start + 4;
            this.dispatchEvent(new Event('input'));
        }
    });
}

// ─── Real-time Stats Polling ───

function pollStats() {
    fetch('/api/stats')
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('agent-count');
            if (el) el.textContent = data.active_agents + ' agents active';
        })
        .catch(() => {});
}

// ─── Init ───

document.addEventListener('DOMContentLoaded', function() {
    initCodeEditor();
    // Poll every 30 seconds
    setInterval(pollStats, 30000);
});
